"""Turn an uploaded file into plain text, page by page."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pdfplumber
from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from suhail.errors import ExtractionError, UnsupportedFileTypeError
from suhail.ingestion.rtl import fix_rtl_line_order
from suhail.models import PageText

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: tuple[str, ...] = (".pdf", ".docx", ".txt")


def extract_text(file_path: str | Path, *, fix_rtl: bool = True) -> list[PageText]:
    """Extract text from a supported file. Raises `SuhailError` subclasses only."""
    path = Path(file_path)
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileTypeError(f"Unsupported file type: {ext or '(none)'}")
    try:
        if ext == ".pdf":
            return _extract_pdf(path, fix_rtl=fix_rtl)
        if ext == ".docx":
            return _extract_docx(path)
        return _extract_txt(path)
    except ExtractionError:
        raise
    except Exception as exc:  # third-party parsers raise many unrelated types
        logger.warning("Extraction failed for %s: %s", path.name, exc)
        raise ExtractionError(f"Could not read {path.name}: {exc}") from exc


def _extract_pdf(path: Path, *, fix_rtl: bool) -> list[PageText]:
    pages: list[PageText] = []
    with pdfplumber.open(path) as pdf:
        for number, page in enumerate(pdf.pages, start=1):
            raw = (page.extract_text() or "").strip()
            pages.append(PageText(number, fix_rtl_line_order(raw) if fix_rtl else raw))
    return pages


def _iter_docx_blocks(doc) -> Iterator[Paragraph | Table]:
    """Yield paragraphs and tables in *document order* (python-docx doesn't)."""
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, doc)
        elif child.tag == qn("w:tbl"):
            yield Table(child, doc)


def _table_rows(table: Table) -> Iterator[str]:
    for row in table.rows:
        cells: list[str] = []
        previous = None
        for cell in row.cells:
            # A merged cell is returned once for every grid column it spans.
            if cell._tc is previous:
                continue
            previous = cell._tc
            text = cell.text.strip()
            if text:
                cells.append(text)
        if cells:
            yield " | ".join(cells)


def _extract_docx(path: Path) -> list[PageText]:
    # Word stores text in logical order, so no RTL repair is needed.
    doc = Document(str(path))
    blocks: list[str] = []
    for block in _iter_docx_blocks(doc):
        if isinstance(block, Paragraph):
            if block.text.strip():
                blocks.append(block.text.strip())
        else:
            blocks.extend(_table_rows(block))
    return [PageText(None, "\n".join(blocks))]


def _extract_txt(path: Path) -> list[PageText]:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1256"):  # cp1256 = legacy Windows Arabic
        try:
            return [PageText(None, data.decode(encoding))]
        except UnicodeDecodeError:
            continue
    raise ExtractionError(f"{path.name}: unknown text encoding (expected UTF-8 or CP1256)")
