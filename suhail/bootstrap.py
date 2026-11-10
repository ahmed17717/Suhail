"""Composition root: the one place where concrete implementations are wired together.

Everything else receives its collaborators through constructors, which is what makes
the rest of the code testable without GPUs, model downloads, or a browser.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass

from suhail.config import Settings
from suhail.ingestion.service import IngestionService
from suhail.knowledge.embeddings import build_embedding_function
from suhail.knowledge.registry import DocumentRegistry
from suhail.knowledge.vector_store import VectorStore
from suhail.llm.generator import Generator, LlamaCppGenerator, SamplingParams
from suhail.rag.pipeline import RagPipeline
from suhail.security import LoginThrottle


@dataclass(frozen=True)
class Services:
    settings: Settings
    pipeline: RagPipeline
    ingestion: IngestionService
    registry: DocumentRegistry
    login_throttle: LoginThrottle


def configure_logging(level: str = "INFO") -> None:
    """Idempotent: Streamlit re-runs the script on every interaction."""
    root = logging.getLogger()
    if any(getattr(h, "_suhail", False) for h in root.handlers):
        root.setLevel(level)
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    handler._suhail = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level)


@dataclass(frozen=True)
class Knowledge:
    """Everything that does NOT need the LLM — enough for CLI ingestion and evaluation."""

    store: VectorStore
    registry: DocumentRegistry
    ingestion: IngestionService


def build_knowledge(
    settings: Settings, *, embedding_function=None, allow_rebuild: bool = False
) -> Knowledge:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    embedding_function = embedding_function or build_embedding_function(
        settings.embedding_model, settings.embedding_device
    )
    store = VectorStore(settings.chroma_path, embedding_function, allow_rebuild=allow_rebuild)
    registry = DocumentRegistry(settings.registry_path)
    ingestion = IngestionService(
        store,
        registry,
        settings.uploads_dir,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        fix_rtl=settings.pdf_rtl_fix,
        max_upload_bytes=settings.max_upload_bytes,
    )
    return Knowledge(store, registry, ingestion)


def build_services(
    settings: Settings,
    *,
    embedding_function=None,
    generator: Generator | None = None,
) -> Services:
    """Create the full object graph. Pass fakes in tests."""
    knowledge = build_knowledge(settings, embedding_function=embedding_function)
    generator = generator or LlamaCppGenerator(
        settings.llm_model_path,
        n_ctx=settings.llm_n_ctx,
        n_threads=settings.llm_n_threads,
        n_gpu_layers=settings.llm_n_gpu_layers,
        max_tokens=settings.llm_max_tokens,
        sampling=SamplingParams(temperature=settings.llm_temperature),
    )
    pipeline = RagPipeline(
        knowledge.store,
        generator,
        assistant_name=settings.assistant_name,
        top_k=settings.top_k,
        similarity_threshold=settings.similarity_threshold,
    )
    return Services(settings, pipeline, knowledge.ingestion, knowledge.registry, LoginThrottle())
