import pytest
from reportlab.pdfgen import canvas

from suhail.errors import (
    EmptyDocumentError,
    ExtractionError,
    FileTooLargeError,
    IngestionError,
    UnsupportedFileTypeError,
)


def txt(text: str) -> bytes:
    return text.encode("utf-8")


def pdf_bytes(tmp_path, text: str) -> bytes:
    path = tmp_path / "_tmp.pdf"
    c = canvas.Canvas(str(path))
    if text:
        c.drawString(72, 750, text)
    c.showPage()
    c.save()
    return path.read_bytes()


def test_ingest_text_file_end_to_end(ingestion, store, registry, settings):
    record = ingestion.ingest_file("policy.txt", txt("annual leave is thirty days " * 40))
    assert record.chunk_count == store.count() > 1
    assert registry.get(record.doc_id).name == "policy.txt"
    assert (settings.uploads_dir / record.stored_as).is_file()


def test_pdf_chunks_remember_their_page(ingestion, store, tmp_path):
    ingestion.ingest_file("a.pdf", pdf_bytes(tmp_path, "vacation policy details"))
    assert store.query("vacation")[0].page == 1


def test_files_are_stored_under_uuid_never_the_user_supplied_name(ingestion, settings):
    record = ingestion.ingest_file("../../etc/passwd.txt", txt("hello there"))
    assert record.name == "passwd.txt"
    stored = list(settings.uploads_dir.iterdir())
    assert [p.name for p in stored] == [record.stored_as]
    assert not (settings.data_dir.parent / "etc").exists()


@pytest.mark.parametrize("name", ["virus.exe", "noextension", "sheet.xlsx"])
def test_unsupported_types_are_rejected_before_touching_disk(ingestion, settings, name):
    with pytest.raises(UnsupportedFileTypeError):
        ingestion.ingest_file(name, b"data")
    assert not settings.uploads_dir.exists() or not list(settings.uploads_dir.iterdir())


def test_oversized_and_empty_files_are_rejected(ingestion):
    with pytest.raises(FileTooLargeError):
        ingestion.ingest_file("big.txt", b"x" * (1024 * 1024 + 1))
    with pytest.raises(EmptyDocumentError):
        ingestion.ingest_file("empty.txt", b"")


def test_scanned_pdf_is_reported_instead_of_silently_indexing_nothing(ingestion, store, tmp_path):
    with pytest.raises(EmptyDocumentError, match="No extractable text"):
        ingestion.ingest_file("scan.pdf", pdf_bytes(tmp_path, ""))
    assert store.count() == 0


def test_corrupt_file_leaves_no_trace(ingestion, store, registry, settings):
    with pytest.raises(ExtractionError):
        ingestion.ingest_file("bad.pdf", b"not a pdf")
    assert store.count() == 0 and registry.all() == []
    assert list(settings.uploads_dir.iterdir()) == []


def test_failure_after_indexing_rolls_back_chunks_and_file(
    ingestion, store, registry, settings, monkeypatch
):
    def boom(_record):
        raise OSError("registry unavailable")

    monkeypatch.setattr(registry, "add", boom)
    with pytest.raises(OSError):
        ingestion.ingest_file("a.txt", txt("some indexed content here"))
    assert store.count() == 0
    assert list(settings.uploads_dir.iterdir()) == []


def test_duplicate_detection_uses_the_sanitised_name(ingestion):
    first = ingestion.ingest_file("report.txt", txt("version one"))
    assert ingestion.find_duplicate("some/dir/report.txt") == first.doc_id
    assert ingestion.find_duplicate("other.txt") is None


def test_replace_swaps_old_version_for_new(ingestion, store, registry, settings):
    old = ingestion.ingest_file("r.txt", txt("old alpha content"))
    new = ingestion.ingest_file("r.txt", txt("new beta content"), replace=True)
    assert [r.doc_id for r in registry.all()] == [new.doc_id]
    assert not (settings.uploads_dir / old.stored_as).exists()
    assert {c.doc_id for c in store.query("content", top_k=5)} == {new.doc_id}


def test_failed_replacement_keeps_the_original_document(ingestion, store, registry):
    old = ingestion.ingest_file("r.txt", txt("precious original content"))
    with pytest.raises(ExtractionError):
        ingestion.ingest_file("r.pdf", b"broken")  # different name: sanity
    with pytest.raises(EmptyDocumentError):
        ingestion.ingest_file("r.txt", b"   \n  ", replace=True)  # blank text -> no chunks
    assert [r.doc_id for r in registry.all()] == [old.doc_id]
    assert store.query("precious")[0].doc_id == old.doc_id


def test_manual_text_lifecycle(ingestion, store, registry):
    record = ingestion.ingest_text("FAQ", "working hours start at eight " * 20)
    assert registry.get(record.doc_id).doc_type == "manual"

    updated = ingestion.update_text(record.doc_id, "short new text")
    assert updated.chunk_count == store.count() == 1
    assert registry.get(record.doc_id).raw_text == "short new text"

    ingestion.delete(record.doc_id)
    assert store.count() == 0 and registry.all() == []


def test_blank_manual_title_gets_a_default(ingestion):
    assert ingestion.ingest_text("   ", "content").name == "نص يدوي"


def test_only_manual_entries_are_editable(ingestion):
    file_doc = ingestion.ingest_file("a.txt", txt("hello"))
    with pytest.raises(IngestionError):
        ingestion.update_text(file_doc.doc_id, "new")
    with pytest.raises(IngestionError):
        ingestion.update_text("missing-id", "new")


def test_delete_removes_chunks_record_and_original(ingestion, store, registry, settings):
    record = ingestion.ingest_file("a.txt", txt("to be deleted"))
    ingestion.delete(record.doc_id)
    assert store.count() == 0 and registry.all() == []
    assert list(settings.uploads_dir.iterdir()) == []


def test_reindex_rebuilds_everything_from_originals(ingestion, store, registry):
    ingestion.ingest_file("a.txt", txt("alpha document text"))
    ingestion.ingest_text("note", "beta manual text")
    before = store.count()
    store.reset()
    assert store.count() == 0
    assert ingestion.reindex_all() == 2
    assert store.count() == before


def test_reindex_refuses_when_an_original_is_missing_and_changes_nothing(
    ingestion, store, registry, settings
):
    ok = ingestion.ingest_file("a.txt", txt("alpha text"))
    gone = ingestion.ingest_file("b.txt", txt("beta text"))
    (settings.uploads_dir / gone.stored_as).unlink()
    count_before = store.count()
    with pytest.raises(IngestionError, match=r"b\.txt"):
        ingestion.reindex_all()
    assert store.count() == count_before
    assert registry.get(ok.doc_id) is not None
