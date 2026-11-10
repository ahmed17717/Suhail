"""The question-answering use case: retrieve → ground → generate → cite.

This is the only place that knows the *order* of those steps. It depends on two small
interfaces (a vector store and a generator), so it is tested without any ML model.

Privacy: logs record metadata (sizes, distances, latency) but never the question or
answer text — questions asked on a government network can be sensitive.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence

from suhail.knowledge.vector_store import VectorStore
from suhail.llm.generator import Generator
from suhail.llm.prompts import NO_ANSWER_TEXT, build_messages, clean_answer
from suhail.models import Answer, RetrievedChunk, Source, Turn
from suhail.rag.retrieval import merge_relevant

logger = logging.getLogger(__name__)

MAX_QUESTION_CHARS = 1000
MAX_HISTORY_TURNS = 2


class RagPipeline:
    def __init__(
        self,
        store: VectorStore,
        generator: Generator,
        *,
        assistant_name: str,
        top_k: int,
        similarity_threshold: float,
    ) -> None:
        self._store = store
        self._generator = generator
        self._assistant_name = assistant_name
        self._top_k = top_k
        self._threshold = similarity_threshold

    def answer(self, question: str, history: Sequence[Turn] = ()) -> Answer:
        question = question.strip()
        if not question:
            raise ValueError("Question must not be empty.")
        if len(question) > MAX_QUESTION_CHARS:
            raise ValueError(f"Question is longer than {MAX_QUESTION_CHARS} characters.")

        started = time.perf_counter()
        recent = list(history)[-MAX_HISTORY_TURNS:]
        previous_question = recent[-1].question if recent else None

        plain = self._store.query(question, self._top_k)
        augmented = (
            self._store.query(f"{previous_question} {question}", self._top_k)
            if previous_question
            else []
        )
        relevant = merge_relevant(plain, augmented, top_k=self._top_k, max_distance=self._threshold)
        # Nearest distance overall (even when nothing passed): the number to look at
        # when tuning SIMILARITY_THRESHOLD.
        nearest = min((c.distance for c in [*plain, *augmented]), default=None)

        if not relevant:
            answer = Answer(text=NO_ANSWER_TEXT, grounded=False)
        else:
            messages = build_messages(
                self._assistant_name, question, [c.text for c in relevant], recent
            )
            text = clean_answer(self._generator.generate(messages))
            answer = Answer(text=text, sources=_unique_sources(relevant), grounded=True)

        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "answer question_chars=%d relevant=%d nearest_distance=%s grounded=%s ms=%d",
            len(question),
            len(relevant),
            f"{nearest:.3f}" if nearest is not None else "n/a",
            answer.grounded,
            latency_ms,
        )
        return Answer(
            text=answer.text,
            sources=answer.sources,
            grounded=answer.grounded,
            latency_ms=latency_ms,
        )


def _unique_sources(chunks: Sequence[RetrievedChunk]) -> tuple[Source, ...]:
    """Distinct (document, page) pairs, closest match first."""
    seen: set[tuple[str, int | None]] = set()
    sources: list[Source] = []
    for chunk in chunks:
        key = (chunk.doc_name, chunk.page)
        if key not in seen:
            seen.add(key)
            sources.append(Source(doc_name=chunk.doc_name, page=chunk.page))
    return tuple(sources)
