from suhail.models import RetrievedChunk
from suhail.rag.retrieval import merge_relevant


def chunk(cid: str, distance: float) -> RetrievedChunk:
    return RetrievedChunk(id=cid, text=cid, distance=distance, doc_id="d", doc_name="d.pdf")


def ids(chunks):
    return [c.id for c in chunks]


def test_self_contained_question_is_not_crowded_out_by_history():
    # The previous question was about "the judge": six judge chunks sit very close in
    # the history-augmented search. The new, self-contained question ("who is the
    # defendant?") has exactly one good match in the plain search, further away.
    plain = [chunk("defendant", 0.80), chunk("j1", 1.30)]
    augmented = [chunk(f"j{i}", 0.30 + i * 0.02) for i in range(1, 7)]

    # A plain distance-sorted union cut to top_k (the naive approach) loses it:
    naive = sorted([*plain, *augmented], key=lambda c: c.distance)[:6]
    assert "defendant" not in ids(naive)

    result = merge_relevant(plain, augmented, top_k=6, max_distance=1.2)
    assert "defendant" in ids(result)
    assert len(result) == 6


def test_follow_up_is_served_by_the_augmented_search():
    # "and the amount?" alone matches nothing; with the previous question it does.
    plain = [chunk("noise1", 1.35), chunk("noise2", 1.40)]
    augmented = [chunk("fine", 0.45), chunk("fine-2", 0.60)]
    assert ids(merge_relevant(plain, augmented, top_k=6, max_distance=1.2)) == ["fine", "fine-2"]


def test_irrelevant_plain_results_do_not_reserve_slots():
    plain = [chunk(f"n{i}", 1.4) for i in range(6)]
    augmented = [chunk(f"a{i}", 0.4 + i * 0.01) for i in range(6)]
    assert ids(merge_relevant(plain, augmented, top_k=6, max_distance=1.2)) == [
        f"a{i}" for i in range(6)
    ]


def test_nothing_relevant_returns_empty():
    assert merge_relevant([chunk("a", 1.5)], [chunk("b", 1.9)], top_k=4, max_distance=1.2) == []


def test_duplicates_collapse_keeping_the_best_distance():
    result = merge_relevant([chunk("x", 0.9)], [chunk("x", 0.5)], top_k=4, max_distance=1.2)
    assert [(c.id, c.distance) for c in result] == [("x", 0.5)]


def test_result_is_sorted_closest_first_and_capped():
    plain = [chunk(f"p{i}", 0.2 + i * 0.1) for i in range(5)]
    result = merge_relevant(plain, [], top_k=3, max_distance=1.2)
    assert ids(result) == ["p0", "p1", "p2"]


def test_threshold_is_exclusive():
    assert merge_relevant([chunk("edge", 1.2)], [], top_k=3, max_distance=1.2) == []
