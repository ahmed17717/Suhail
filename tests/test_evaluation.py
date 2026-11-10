import json

from suhail.evaluation import EvalCase, evaluate, load_cases


def seeded(store):
    store.add_document(
        "d",
        "d.txt",
        ["annual leave is thirty days", "office hours start at eight", "password reset via portal"],
    )
    return store


def test_hits_mrr_and_abstention(store):
    cases = [
        EvalCase("how many days annual leave", "thirty days"),
        EvalCase("when do office hours start", "start at eight"),
        EvalCase("quantum chromodynamics lagrangian", None),
        EvalCase("annual leave", "this text is nowhere"),
    ]
    report = evaluate(seeded(store), cases, top_k=3, threshold=1.2)
    assert report.cases == 4 and report.answerable == 3
    assert report.hit_rate == 2 / 3  # the fourth expectation can never be found
    assert report.mrr == (1 + 1 + 0) / 3
    assert report.abstain_rate == 1.0


def test_threshold_advice_names_a_separating_range(store):
    cases = [EvalCase("annual leave days", "thirty days"), EvalCase("zzz yyy xxx", None)]
    advice = evaluate(seeded(store), cases, top_k=3, threshold=1.2).threshold_advice()
    assert advice.startswith("Any SIMILARITY_THRESHOLD between")


def test_advice_when_only_one_kind_of_case_exists(store):
    report = evaluate(
        seeded(store), [EvalCase("annual leave", "thirty days")], top_k=3, threshold=1
    )
    assert "both answerable and unanswerable" in report.threshold_advice()


def test_load_cases_skips_blank_lines_and_reads_nulls(tmp_path):
    path = tmp_path / "g.jsonl"
    rows = [{"question": "q1", "expect": "x"}, {"question": "q2", "expect": None}]
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n\n", "utf-8")
    assert load_cases(path) == [EvalCase("q1", "x"), EvalCase("q2", None)]


def test_shipped_golden_set_is_well_formed():
    cases = load_cases("evals/golden.jsonl")
    assert any(c.expect is None for c in cases) and any(c.expect for c in cases)
