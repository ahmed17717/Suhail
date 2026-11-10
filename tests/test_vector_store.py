import pytest

from suhail.errors import IndexMismatchError
from suhail.knowledge.vector_store import VectorStore
from tests.fakes import FakeEmbedding, OtherFakeEmbedding


def test_query_on_empty_store_returns_nothing(store):
    assert store.query("anything") == []


def test_closest_chunk_ranks_first_and_carries_metadata(store):
    store.add_document(
        "d1", "leave.pdf", ["annual leave is thirty days", "office hours start at eight"], [3, 4]
    )
    top = store.query("how many days of annual leave", top_k=2)[0]
    assert top.text == "annual leave is thirty days"
    assert (top.doc_name, top.page, top.doc_id) == ("leave.pdf", 3, "d1")


def test_page_is_none_for_pageless_documents(store):
    store.add_document("d1", "notes", ["hello world"], [None])
    assert store.query("hello")[0].page is None


def test_top_k_is_capped_to_collection_size(store):
    store.add_document("d1", "n", ["a b", "c d"])
    assert len(store.query("a", top_k=10)) == 2


def test_reindexing_with_fewer_chunks_prunes_stale_ones(store):
    store.add_document("d1", "n", ["one", "two", "three", "four"])
    store.add_document("d1", "n", ["one", "two"])
    assert store.count() == 2


def test_delete_only_removes_that_document(store):
    store.add_document("d1", "a", ["alpha text"])
    store.add_document("d2", "b", ["beta text"])
    store.delete_document("d1")
    assert {c.doc_id for c in store.query("text", top_k=5)} == {"d2"}


def test_large_documents_are_written_in_batches(settings):
    small = VectorStore(settings.chroma_path / "batched", FakeEmbedding(), batch_size=7)
    chunks = [f"chunk number {i}" for i in range(50)]
    small.add_document("big", "big.pdf", chunks)
    assert small.count() == 50


def test_reset_empties_the_collection(store):
    store.add_document("d1", "a", ["x y"])
    store.reset()
    assert store.count() == 0
    store.add_document("d2", "b", ["z"])
    assert store.count() == 1


def test_opening_an_index_built_with_another_model_is_refused(settings):
    VectorStore(settings.chroma_path, FakeEmbedding()).add_document("d", "n", ["some text"])
    with pytest.raises(IndexMismatchError, match="reindex"):
        VectorStore(settings.chroma_path, OtherFakeEmbedding())


def test_rebuild_mode_discards_the_incompatible_index(settings):
    VectorStore(settings.chroma_path, FakeEmbedding()).add_document("d", "n", ["some text"])
    rebuilt = VectorStore(settings.chroma_path, OtherFakeEmbedding(), allow_rebuild=True)
    assert rebuilt.count() == 0
    rebuilt.add_document("d", "n", ["new text"])
    assert rebuilt.count() == 1
