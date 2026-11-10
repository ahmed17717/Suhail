"""Split text into small, topically tight, overlapping chunks.

Why a character window instead of sentence splitting: Arabic legal/government
documents are punctuation-light clauses separated by line breaks, not
period-terminated sentences. A sentence splitter produced oversized chunks that
mixed unrelated facts (names, case numbers, table rows) into one diluted
embedding and made retrieval inconsistent. A fixed window keeps each chunk
focused, and the overlap guarantees a fact near a cut point appears whole in at
least one chunk.
"""

from __future__ import annotations

import re

_BLANK_LINE = re.compile(r"\n\s*\n")
_WHITESPACE = re.compile(r"\s+")
_WHITESPACE_CHAR = re.compile(r"\s")


def split_into_paragraphs(text: str) -> list[str]:
    """Split on blank lines, then collapse inner whitespace.

    Single newlines are *not* paragraph breaks: in extracted PDF text they are
    usually word-wrap continuations, and cutting there would split a clause.
    """
    paragraphs = []
    for block in _BLANK_LINE.split(text):
        collapsed = _WHITESPACE.sub(" ", block).strip()
        if collapsed:
            paragraphs.append(collapsed)
    return paragraphs


def chunk_text(text: str, chunk_size: int = 350, overlap: int = 80) -> list[str]:
    """Sliding-window chunker with cuts snapped to word boundaries."""
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    paragraphs = split_into_paragraphs(text)
    if not paragraphs:
        return []

    full_text = "\n\n".join(paragraphs)
    total = len(full_text)
    if total <= chunk_size:
        return [full_text]

    chunks: list[str] = []
    start = 0
    while start < total:
        end = start + chunk_size
        if end >= total:
            tail = full_text[start:].strip()
            if tail:
                chunks.append(tail)
            break

        boundary = max(full_text.rfind(" ", start, end), full_text.rfind("\n", start, end))
        if boundary <= start:
            boundary = end  # no whitespace in range: hard cut as a last resort

        piece = full_text[start:boundary].strip()
        if piece:
            chunks.append(piece)

        start = _next_start(full_text, start, boundary, overlap)

    return chunks


def _next_start(text: str, current_start: int, boundary: int, overlap: int) -> int:
    """Where the next chunk begins: `overlap` characters back, snapped to a word start.

    Snapping forward (never back) guarantees progress and that a chunk never opens in
    the middle of a word, number or case reference.
    """
    candidate = boundary - overlap
    if candidate <= current_start:
        return boundary
    if text[candidate - 1].isspace():
        return candidate  # already at the start of a word
    gap = _WHITESPACE_CHAR.search(text, candidate, boundary)
    return gap.end() if gap else boundary
