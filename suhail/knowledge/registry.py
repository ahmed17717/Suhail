"""Catalogue of ingested documents (what the admin sees and can edit/delete).

The vector store holds the searchable chunks; this registry holds the *document-level*
facts the store can't: display name, type, original text of manual entries, and
which file on disk a document came from (needed to re-index).

Storage is one small JSON file. Writes are atomic (temp file + rename), so a crash
or power loss mid-write can never leave a truncated registry. A corrupt file raises
`RegistryError` instead of silently resetting to empty.

The on-disk format is backward compatible with the first version
(`{doc_id: {"name", "type", "raw_text"}}`): new fields are optional.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path

from suhail.errors import RegistryError
from suhail.models import DocumentRecord


class DocumentRegistry:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._lock = threading.RLock()

    # ---- persistence ------------------------------------------------------
    def _load(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}
        try:
            with self._path.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            raise RegistryError(f"Cannot read registry {self._path}: {exc}") from exc
        if not isinstance(data, dict):
            raise RegistryError(f"Registry {self._path} has an unexpected structure")
        return data

    def _save(self, data: dict[str, dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(dir=self._path.parent, prefix=".registry-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, self._path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise

    @staticmethod
    def _to_record(doc_id: str, raw: dict) -> DocumentRecord:
        return DocumentRecord(
            doc_id=doc_id,
            name=raw["name"],
            doc_type=raw.get("type", "file"),
            raw_text=raw.get("raw_text"),
            stored_as=raw.get("stored_as"),
            chunk_count=int(raw.get("chunk_count", 0)),
            created_at=raw.get("created_at", ""),
        )

    @staticmethod
    def _to_raw(record: DocumentRecord) -> dict:
        return {
            "name": record.name,
            "type": record.doc_type,
            "raw_text": record.raw_text,
            "stored_as": record.stored_as,
            "chunk_count": record.chunk_count,
            "created_at": record.created_at,
        }

    # ---- API --------------------------------------------------------------
    def add(self, record: DocumentRecord) -> DocumentRecord:
        if not record.created_at:
            record.created_at = datetime.now(UTC).isoformat(timespec="seconds")
        with self._lock:
            data = self._load()
            data[record.doc_id] = self._to_raw(record)
            self._save(data)
        return record

    def get(self, doc_id: str) -> DocumentRecord | None:
        raw = self._load().get(doc_id)
        return self._to_record(doc_id, raw) if raw else None

    def all(self) -> list[DocumentRecord]:
        return [self._to_record(doc_id, raw) for doc_id, raw in self._load().items()]

    def update_text(self, doc_id: str, text: str, chunk_count: int) -> None:
        with self._lock:
            data = self._load()
            if doc_id in data:
                data[doc_id]["raw_text"] = text
                data[doc_id]["chunk_count"] = chunk_count
                self._save(data)

    def set_chunk_count(self, doc_id: str, chunk_count: int) -> None:
        with self._lock:
            data = self._load()
            if doc_id in data:
                data[doc_id]["chunk_count"] = chunk_count
                self._save(data)

    def remove(self, doc_id: str) -> None:
        with self._lock:
            data = self._load()
            if data.pop(doc_id, None) is not None:
                self._save(data)

    def find_by_name(self, name: str) -> str | None:
        for record in self.all():
            if record.name == name:
                return record.doc_id
        return None
