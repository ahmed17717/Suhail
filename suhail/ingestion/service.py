"""Ingestion use cases: add a file, add/edit manual text, delete, re-index.

Consistency model
-----------------
A document lives in three places: the original file on disk, its chunks in the vector
store, and a record in the registry. Every operation here either completes all three
or rolls back to the previous state:

* a failed ingest leaves nothing behind (chunks and file are removed);
* replacing a document ingests the new version *first* and deletes the old one only
  on success, so a bad upload can never destroy the document it was meant to replace;
* editing re-indexes via upsert + prune, never delete-then-add.

Uploaded files are stored under a generated UUID. The user-supplied name is used for
display and duplicate detection only, so it can never influence a filesystem path.
"""

from __future__ import annotations

import contextlib
import logging
import uuid
from pathlib import Path

from suhail.errors import (
    EmptyDocumentError,
    FileTooLargeError,
    IngestionError,
    UnsupportedFileTypeError,
)
from suhail.ingestion.chunking import chunk_text
from suhail.ingestion.extract import SUPPORTED_EXTENSIONS, extract_text
from suhail.knowledge.registry import DocumentRegistry
from suhail.knowledge.vector_store import VectorStore
from suhail.models import DocumentRecord, PageText
from suhail.security import safe_display_name

logger = logging.getLogger(__name__)
audit = logging.getLogger("suhail.audit")

DEFAULT_MANUAL_TITLE = "نص يدوي"


def find_unreindexable(registry: DocumentRegistry, uploads_dir: Path) -> list[str]:
    """Names of documents whose original can't be found, i.e. can't be rebuilt.

    A manual entry is rebuildable from its stored text; a file needs its original on
    disk (files ingested by the very first version did not keep one).
    """
    missing = []
    for record in registry.all():
        if record.doc_type == "manual" and record.raw_text:
            continue
        stored = Path(record.stored_as).name if record.stored_as else None
        if not stored or not (Path(uploads_dir) / stored).is_file():
            missing.append(record.name)
    return missing


class IngestionService:
    def __init__(
        self,
        store: VectorStore,
        registry: DocumentRegistry,
        uploads_dir: Path,
        *,
        chunk_size: int,
        chunk_overlap: int,
        fix_rtl: bool,
        max_upload_bytes: int,
    ) -> None:
        self._store = store
        self._registry = registry
        self._uploads_dir = Path(uploads_dir)
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._fix_rtl = fix_rtl
        self._max_bytes = max_upload_bytes

    # ---- helpers ----------------------------------------------------------
    def _chunk_pages(self, pages: list[PageText]) -> tuple[list[str], list[int | None]]:
        chunks: list[str] = []
        page_numbers: list[int | None] = []
        for page in pages:
            page_chunks = chunk_text(page.text, self._chunk_size, self._chunk_overlap)
            chunks.extend(page_chunks)
            page_numbers.extend([page.page] * len(page_chunks))
        return chunks, page_numbers

    def _stored_path(self, record: DocumentRecord) -> Path | None:
        if not record.stored_as:
            return None
        return self._uploads_dir / Path(record.stored_as).name  # .name: never trust a path

    def find_duplicate(self, filename: str) -> str | None:
        return self._registry.find_by_name(safe_display_name(filename))

    # ---- files ------------------------------------------------------------
    def ingest_file(self, filename: str, data: bytes, *, replace: bool = False) -> DocumentRecord:
        """Ingest an uploaded file. With `replace=True`, swap out a same-named document."""
        name = safe_display_name(filename)
        ext = Path(name).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFileTypeError(f"Unsupported file type: {ext or '(none)'}")
        if len(data) > self._max_bytes:
            raise FileTooLargeError(f"File exceeds the {self._max_bytes // (1024 * 1024)} MB limit")
        if not data:
            raise EmptyDocumentError("The file is empty")

        old_id = self._registry.find_by_name(name) if replace else None
        doc_id = str(uuid.uuid4())
        stored_as = f"{doc_id}{ext}"
        path = self._uploads_dir / stored_as
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

        try:
            pages = extract_text(path, fix_rtl=self._fix_rtl)
            chunks, page_numbers = self._chunk_pages(pages)
            if not chunks:
                raise EmptyDocumentError(
                    f"No extractable text in {name} (scanned PDF? OCR is not supported)"
                )
            self._store.add_document(doc_id, name, chunks, page_numbers)
            record = self._registry.add(
                DocumentRecord(
                    doc_id=doc_id,
                    name=name,
                    doc_type="file",
                    stored_as=stored_as,
                    chunk_count=len(chunks),
                )
            )
        except BaseException:
            # Roll back everything this call may have created.
            with contextlib.suppress(Exception):
                self._store.delete_document(doc_id)
            path.unlink(missing_ok=True)
            raise

        if old_id:
            self.delete(old_id, _audit=False)
        audit.info(
            "action=upload name=%r doc_id=%s chunks=%d replaced=%s",
            name,
            doc_id,
            len(chunks),
            bool(old_id),
        )
        return record

    # ---- manual text ------------------------------------------------------
    def ingest_text(self, title: str, text: str) -> DocumentRecord:
        title = (
            safe_display_name(title, fallback=DEFAULT_MANUAL_TITLE)
            if title.strip()
            else DEFAULT_MANUAL_TITLE
        )
        if len(text.encode("utf-8")) > self._max_bytes:
            raise FileTooLargeError("Text exceeds the size limit")
        chunks = chunk_text(text, self._chunk_size, self._chunk_overlap)
        if not chunks:
            raise EmptyDocumentError("The text is empty")

        doc_id = str(uuid.uuid4())
        try:
            self._store.add_document(doc_id, title, chunks)
            record = self._registry.add(
                DocumentRecord(
                    doc_id=doc_id,
                    name=title,
                    doc_type="manual",
                    raw_text=text,
                    chunk_count=len(chunks),
                )
            )
        except BaseException:
            with contextlib.suppress(Exception):
                self._store.delete_document(doc_id)
            raise
        audit.info("action=add_text name=%r doc_id=%s chunks=%d", title, doc_id, len(chunks))
        return record

    def update_text(self, doc_id: str, text: str) -> DocumentRecord:
        record = self._registry.get(doc_id)
        if record is None or record.doc_type != "manual":
            raise IngestionError("Only manual text entries can be edited")
        chunks = chunk_text(text, self._chunk_size, self._chunk_overlap)
        if not chunks:
            raise EmptyDocumentError("The text is empty")
        self._store.add_document(doc_id, record.name, chunks)  # upsert + prune stale chunks
        self._registry.update_text(doc_id, text, len(chunks))
        audit.info("action=edit_text name=%r doc_id=%s chunks=%d", record.name, doc_id, len(chunks))
        record.raw_text, record.chunk_count = text, len(chunks)
        return record

    # ---- delete / re-index ------------------------------------------------
    def delete(self, doc_id: str, *, _audit: bool = True) -> None:
        record = self._registry.get(doc_id)
        self._store.delete_document(doc_id)
        self._registry.remove(doc_id)
        if record:
            path = self._stored_path(record)
            if path:
                path.unlink(missing_ok=True)
            if _audit:
                audit.info("action=delete name=%r doc_id=%s", record.name, doc_id)

    def reindex_all(self) -> int:
        """Rebuild the whole vector index from the stored originals.

        Needed after changing the embedding model or the chunking settings. Refuses to
        start (touching nothing) if any document can't be rebuilt, e.g. a file ingested
        by an early version that did not keep the original.
        """
        missing = find_unreindexable(self._registry, self._uploads_dir)
        if missing:
            raise IngestionError(
                "Cannot re-index; original missing for: "
                + ", ".join(missing)
                + ". Re-upload them first."
            )

        # Extract everything *before* dropping the index, so a bad file aborts cleanly.
        sources: list[tuple[DocumentRecord, list[PageText]]] = []
        for record in self._registry.all():
            if record.doc_type == "manual" and record.raw_text:
                sources.append((record, [PageText(None, record.raw_text)]))
            else:
                path = self._stored_path(record)
                sources.append((record, extract_text(path, fix_rtl=self._fix_rtl)))

        self._store.reset()
        for record, pages in sources:
            chunks, page_numbers = self._chunk_pages(pages)
            self._store.add_document(record.doc_id, record.name, chunks, page_numbers)
            self._registry.set_chunk_count(record.doc_id, len(chunks))
        audit.info("action=reindex documents=%d", len(sources))
        return len(sources)
