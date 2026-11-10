import pytest
from docx import Document
from reportlab.pdfgen import canvas

from suhail.errors import ExtractionError, UnsupportedFileTypeError
from suhail.ingestion.extract import extract_text


def make_pdf(path, pages):
    c = canvas.Canvas(str(path))
    for text in pages:
        c.drawString(72, 750, text)
        c.showPage()
    c.save()


def test_pdf_pages_are_numbered_from_one(tmp_path):
    pdf = tmp_path / "doc.pdf"
    make_pdf(pdf, ["first page text", "second page text"])
    pages = extract_text(pdf, fix_rtl=False)
    assert [p.page for p in pages] == [1, 2]
    assert "first page" in pages[0].text and "second page" in pages[1].text


def test_pdf_without_text_layer_yields_empty_pages(tmp_path):
    pdf = tmp_path / "blank.pdf"
    make_pdf(pdf, [""])
    assert [p.text for p in extract_text(pdf)] == [""]


def test_corrupt_pdf_raises_extraction_error(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"this is not a pdf")
    with pytest.raises(ExtractionError):
        extract_text(bad)


def test_docx_keeps_document_order_and_table_rows(tmp_path):
    doc = Document()
    doc.add_paragraph("before table")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Name", "Ahmed"
    table.cell(1, 0).text, table.cell(1, 1).text = "Role", "Engineer"
    doc.add_paragraph("after table")
    path = tmp_path / "t.docx"
    doc.save(path)

    text = extract_text(path)[0].text
    assert text.index("before table") < text.index("Name | Ahmed") < text.index("after table")
    assert "Role | Engineer" in text


def test_docx_merged_cells_are_not_duplicated(tmp_path):
    doc = Document()
    table = doc.add_table(rows=1, cols=3)
    merged = table.cell(0, 0).merge(table.cell(0, 1))
    merged.text = "Merged"
    table.cell(0, 2).text = "Other"
    path = tmp_path / "m.docx"
    doc.save(path)
    assert extract_text(path)[0].text == "Merged | Other"


def test_txt_utf8_and_legacy_windows_arabic(tmp_path):
    utf8 = tmp_path / "a.txt"
    utf8.write_text("مرحبا", encoding="utf-8")
    legacy = tmp_path / "b.txt"
    legacy.write_bytes("مرحبا".encode("cp1256"))
    assert extract_text(utf8)[0].text == "مرحبا"
    assert extract_text(legacy)[0].text == "مرحبا"


def test_unsupported_extension(tmp_path):
    f = tmp_path / "x.xlsx"
    f.write_bytes(b"x")
    with pytest.raises(UnsupportedFileTypeError):
        extract_text(f)
