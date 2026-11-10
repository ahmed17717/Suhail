"""Vector store: a thin, testable wrapper around a persistent Chroma collection.

Design notes
------------
* The embedding function is *injected*, so tests (and any future model swap) don't
  touch this class, and importing it never loads a neural network.
* Distances are Chroma's default **L2**; `SIMILARITY_THRESHOLD` is calibrated for it.
* Writes are upserts followed by pruning stale chunks, so re-indexing a document
  (edit, replace) can never leave it half-written or empty.
* Anonymous telemetry is disabled — this runs on an internal network.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from suhail.errors import IndexMismatchError
from suhail.models import RetrievedChunk

logger = logging.getLogger(__name__)

COLLECTION_NAME = "knowledge_base"


class VectorStore:
    def __init__(
        self,
        path: Path,
        embedding_function,
        *,
        collection_name: str = COLLECTION_NAME,
        batch_size: int = 256,
        allow_rebuild: bool = False,
    ) -> None:
        Path(path).mkdir(parents=True, exist_ok=True)
        self._collection_name = collection_name
        self._embedding_function = embedding_function
        self._client = chromadb.PersistentClient(
            path=str(path), settings=ChromaSettings(anonymized_telemetry=False)
        )
        self._collection = self._open_collection(allow_rebuild)
        # Chroma rejects batches above its SQLite-derived limit (a big PDF easily
        # exceeds it), so always write in bounded batches.
        self._batch = max(1, min(batch_size, self._client.get_max_batch_size()))
        self._write_lock = threading.Lock()

    def _open_collection(self, allow_rebuild: bool):
        try:
            return self._client.get_or_create_collection(
                name=self._collection_name, embedding_function=self._embedding_function
            )
        except ValueError as exc:
            # Chroma pins the embedding function in the collection. Opening an index built
            # with another model would silently mix incompatible vectors, so it refuses.
            if "conflict" not in str(exc).lower():
                raise
            if not allow_rebuild:
                raise IndexMismatchError(
                    "The vector index was built with a different embedding model. "
                    "Rebuild it with: python -m scripts.manage reindex"
                ) from exc
            logger.warning("Embedding model changed: discarding the old index for re-indexing")
            self._client.delete_collection(self._collection_name)
            return self._client.get_or_create_collection(
                name=self._collection_name, embedding_function=self._embedding_function
            )

    # ---- writes -----------------------------------------------------------
    def add_document(
        self,
        doc_id: str,
        doc_name: str,
        chunks: Sequence[str],
        pages: Sequence[int | None] | None = None,
    ) -> None:
        """Index (or re-index) a document. Idempotent for a given `doc_id`."""
        if not chunks:
            return
        ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
        metadatas: list[dict] = []
        for i in range(len(chunks)):
            meta: dict = {"doc_id": doc_id, "doc_name": doc_name}
            if pages is not None and i < len(pages) and pages[i] is not None:
                meta["page"] = pages[i]
            metadatas.append(meta)

        with self._write_lock:
            for lo in range(0, len(ids), self._batch):
                hi = lo + self._batch
                self._collection.upsert(
                    ids=ids[lo:hi], documents=list(chunks[lo:hi]), metadatas=metadatas[lo:hi]
                )
            self._prune_stale(doc_id, keep=set(ids))

    def _prune_stale(self, doc_id: str, keep: set[str]) -> None:
        existing = self._collection.get(where={"doc_id": doc_id}, include=[])["ids"]
        stale = [chunk_id for chunk_id in existing if chunk_id not in keep]
        for lo in range(0, len(stale), self._batch):
            self._collection.delete(ids=stale[lo : lo + self._batch])

    def delete_document(self, doc_id: str) -> None:
        with self._write_lock:
            self._collection.delete(where={"doc_id": doc_id})

    def reset(self) -> None:
        """Drop every chunk. Needed after changing the embedding model (new dimensions)."""
        with self._write_lock:
            self._client.delete_collection(self._collection_name)
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name, embedding_function=self._embedding_function
            )

    # ---- reads ------------------------------------------------------------
    def count(self) -> int:
        return self._collection.count()

    def query(self, question: str, top_k: int = 4) -> list[RetrievedChunk]:
        total = self._collection.count()
        if total == 0:
            return []
        result = self._collection.query(
            query_texts=[question],
            n_results=min(top_k, total),
            include=["documents", "distances", "metadatas"],
        )
        return [
            RetrievedChunk(
                id=chunk_id,
                text=text,
                distance=float(distance),
                doc_id=meta["doc_id"],
                doc_name=meta["doc_name"],
                page=meta.get("page"),
            )
            for chunk_id, text, distance, meta in zip(
                result["ids"][0],
                result["documents"][0],
                result["distances"][0],
                result["metadatas"][0],
                strict=True,
            )
        ]
