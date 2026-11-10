from itertools import pairwise

import pytest

from suhail.ingestion.chunking import chunk_text, split_into_paragraphs


def test_empty_and_whitespace_only_produce_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  \t ") == []


def test_short_text_is_a_single_chunk():
    assert chunk_text("نص قصير جدا") == ["نص قصير جدا"]


def test_single_newlines_are_wrap_not_breaks_but_blank_lines_are():
    assert split_into_paragraphs("a\nb\n\nc") == ["a b", "c"]


def test_chunks_respect_size_limit():
    text = " ".join(f"كلمة{i}" for i in range(500))
    chunks = chunk_text(text, chunk_size=120, overlap=30)
    assert len(chunks) > 5
    assert all(len(c) <= 120 for c in chunks)


def test_no_word_is_ever_cut_in_half():
    words = [f"word{i}" for i in range(300)]
    chunks = chunk_text(" ".join(words), chunk_size=100, overlap=25)
    valid = set(words)
    for chunk in chunks:
        assert set(chunk.split()) <= valid


def test_every_word_is_covered_and_neighbours_overlap():
    words = [f"w{i}" for i in range(400)]
    chunks = chunk_text(" ".join(words), chunk_size=90, overlap=30)
    assert {w for c in chunks for w in c.split()} == set(words)
    for a, b in pairwise(chunks):
        assert set(a.split()) & set(b.split()), "consecutive chunks must share text"


def test_fact_straddling_a_cut_survives_intact_in_some_chunk():
    filler = "x " * 60
    text = f"{filler}القضية رقم 123/2024 تجارية كلية {filler}"
    chunks = chunk_text(text, chunk_size=80, overlap=40)
    assert any("القضية رقم 123/2024" in c for c in chunks)


def test_unbroken_text_falls_back_to_hard_cut_and_terminates():
    chunks = chunk_text("a" * 1000, chunk_size=100, overlap=20)
    assert len(chunks) >= 10
    assert all(len(c) <= 100 for c in chunks)


def test_overlap_must_be_smaller_than_chunk_size():
    with pytest.raises(ValueError):
        chunk_text("text", chunk_size=50, overlap=50)
