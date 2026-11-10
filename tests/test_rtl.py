import pytest

from suhail.ingestion.rtl import arabic_ratio, fix_rtl_line_order, is_arabic_majority
from tests.arabic_shaping import to_visual


@pytest.mark.parametrize(
    "logical",
    [
        "مرحبا بكم في النظام",
        "المادة (75) من القانون",
        "رقم القضية 2024/123 لسنة 2024",
        "تاريخ الجلسة 15-03-2024 والحكم بالسجن",
    ],
)
def test_visual_order_pdf_text_is_restored_to_logical_order(logical):
    visual = to_visual(logical)
    assert visual != logical  # the fixture really is scrambled
    assert fix_rtl_line_order(visual) == logical


def test_lam_alef_hamza_ligature_keeps_letter_order():
    # "الأوراق" as pre-shaped glyphs, in extraction (visual) order. The lam-alef-hamza
    # ligature is ONE glyph that NFKC expands to two letters: reversing *after*
    # normalising would swap them (the bug the order of operations avoids).
    logical_glyphs = "\ufe8d\ufef7\ufeed\ufead\ufe8d\ufed5"
    extracted = logical_glyphs[::-1]
    assert fix_rtl_line_order(extracted) == "الأوراق"


def test_latin_dominant_line_keeps_token_order():
    line = "Case Number رقم 42"
    assert fix_rtl_line_order(line).split()[0:2] == ["Case", "Number"]


def test_tatweel_is_removed_and_blank_lines_survive():
    out = fix_rtl_line_order("كــلــمــة\n\nabc")
    assert "\u0640" not in out
    assert out.split("\n")[1] == ""


def test_ratio_helpers():
    assert arabic_ratio("") == 0.0
    assert arabic_ratio("abc") == 0.0
    assert is_arabic_majority("مرحبا")
    assert not is_arabic_majority("hello")
