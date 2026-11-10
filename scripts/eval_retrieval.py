"""Evaluate retrieval quality against a golden set.

python -m scripts.manage ingest examples
python -m scripts.eval_retrieval                    # uses evals/golden.jsonl
python -m scripts.eval_retrieval --cases my.jsonl
"""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts._common import load_settings
from suhail.bootstrap import build_knowledge
from suhail.evaluation import evaluate, load_cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cases", type=Path, default=Path("evals/golden.jsonl"))
    args = parser.parse_args()

    settings = load_settings()
    knowledge = build_knowledge(settings)
    if knowledge.store.count() == 0:
        print("The knowledge base is empty. Ingest documents first (see --help).")
        return 1

    cases = load_cases(args.cases)
    report = evaluate(
        knowledge.store, cases, top_k=settings.top_k, threshold=settings.similarity_threshold
    )
    print(f"cases:            {report.cases} ({report.answerable} answerable)")
    print(f"hit@{settings.top_k}:           {report.hit_rate:.0%}")
    print(f"MRR:              {report.mrr:.3f}")
    if report.abstain_rate is not None:
        print(
            print(
                f"correct no-answer:{report.abstain_rate:>6.0%}  "
                f"(threshold {settings.similarity_threshold})"
            )
        )
    print(report.threshold_advice())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
