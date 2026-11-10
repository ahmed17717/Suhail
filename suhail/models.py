"""Plain data objects passed between layers (no behaviour, no I/O)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

DocType = Literal["file", "manual"]


@dataclass(frozen=True)
class PageText:
    """Text extracted from one page. `page` is None for page-less formats (docx/txt)."""

    page: int | None
    text: str


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    text: str
    distance: float  # lower is closer (Chroma L2)
    doc_id: str
    doc_name: str
    page: int | None = None


@dataclass(frozen=True)
class Source:
    doc_name: str
    page: int | None = None


@dataclass(frozen=True)
class Turn:
    """One completed question/answer exchange, used as conversational context."""

    question: str
    answer: str


@dataclass(frozen=True)
class Answer:
    text: str
    sources: tuple[Source, ...] = ()
    grounded: bool = False  # False => "not enough information" fallback
    latency_ms: int = 0


@dataclass
class DocumentRecord:
    doc_id: str
    name: str
    doc_type: DocType
    raw_text: str | None = None  # only kept for manual entries (editable)
    stored_as: str | None = None  # filename under uploads/, for re-indexing
    chunk_count: int = 0
    created_at: str = field(default="")
