"""Offline retrieval evaluation — measure, don't guess.

Given a small "golden set" of questions and a text snippet that must appear in the
retrieved context, report how often retrieval finds it (hit@k), how high it ranks
(MRR), and whether out-of-scope questions are correctly rejected by the similarity
threshold. The distance statistics tell you where to put `SIMILARITY_THRESHOLD`.

It evaluates *retrieval only* (no LLM), so it is fast, deterministic, and runs on a
laptop. Use it before/after changing the embedding model, chunk size, or threshold.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

from suhail.knowledge.vector_store import VectorStore


@dataclass(frozen=True)
class EvalCase:
    question: str
    expect: str | None  # snippet that must be retrieved; None = should be unanswerable


@dataclass(frozen=True)
class EvalReport:
    cases: int
    answerable: int
    hit_rate: float  # share of answerable questions whose snippet is in the top-k
    mrr: float  # mean reciprocal rank of the first matching chunk
    abstain_rate: float | None  # share of unanswerable questions correctly rejected
    best_hit_distance_max: float | None  # farthest distance at which a correct hit still sits
    nearest_miss_distance_min: float | None  # closest any unanswerable question got

    def threshold_advice(self) -> str:
        hi, lo = self.best_hit_distance_max, self.nearest_miss_distance_min
        if hi is None or lo is None:
            return "Add both answerable and unanswerable cases to get threshold advice."
        if hi < lo:
            return f"Any SIMILARITY_THRESHOLD between {hi:.2f} and {lo:.2f} separates them."
        return (
            f"Overlap: correct hits reach {hi:.2f} but a no-answer question got as close "
            f"as {lo:.2f}; no single threshold is perfect."
        )


def load_cases(path: Path) -> list[EvalCase]:
    cases = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            cases.append(EvalCase(row["question"], row.get("expect")))
    return cases


def evaluate(
    store: VectorStore, cases: list[EvalCase], *, top_k: int, threshold: float
) -> EvalReport:
    reciprocal_ranks: list[float] = []
    hit_distances: list[float] = []
    abstained = unanswerable = 0
    miss_distances: list[float] = []

    for case in cases:
        results = store.query(case.question, top_k)
        if case.expect is None:
            unanswerable += 1
            nearest = min((c.distance for c in results), default=float("inf"))
            miss_distances.append(nearest)
            abstained += nearest >= threshold
            continue
        rank = next((i for i, c in enumerate(results, 1) if case.expect in c.text), None)
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        if rank:
            hit_distances.append(results[rank - 1].distance)

    answerable = len(reciprocal_ranks)
    return EvalReport(
        cases=len(cases),
        answerable=answerable,
        hit_rate=(sum(r > 0 for r in reciprocal_ranks) / answerable) if answerable else 0.0,
        mrr=mean(reciprocal_ranks) if reciprocal_ranks else 0.0,
        abstain_rate=(abstained / unanswerable) if unanswerable else None,
        best_hit_distance_max=max(hit_distances) if hit_distances else None,
        nearest_miss_distance_min=min(miss_distances) if miss_distances else None,
    )
