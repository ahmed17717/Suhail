"""Repair Arabic text extracted from PDFs that store it in *visual* order.

Many PDF generators (including some Gulf-government document systems) encode
Arabic as pre-shaped *presentation-form* glyphs positioned purely by x/y
coordinate. A text extractor then returns words — and the letters inside each
word — mirrored. This module restores logical reading order.

The approach is heuristic by nature, so it is isolated here, documented, and
covered by unit tests.
"""

from __future__ import annotations

import re
import unicodedata

# Arabic, Arabic Supplement, and both presentation-form blocks.
ARABIC_RANGE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")

# Stretching character used in justified layouts; meaningless once extracted.
TATWEEL = "\u0640"

# Brackets are "mirrored" glyphs: when a run moves across an RTL reversal an
# opening paren must become a closing one, or "(75)" turns into ")75(".
BIDI_MIRROR = str.maketrans("()[]{}<>", ")(][}{><")

# A line is "Arabic-dominant" (token order is reversed) above this share of
# Arabic characters; below it (e.g. a bilingual header row led by an English
# label) token order is left alone.
LINE_ARABIC_RATIO_THRESHOLD = 0.35

# A token is "Arabic" (glyphs reversed + normalised) above this share; numbers
# and Latin words must stay untouched internally — only their position moves.
WORD_ARABIC_RATIO_THRESHOLD = 0.5


def arabic_ratio(text: str) -> float:
    letters = re.sub(r"\s+", "", text)
    if not letters:
        return 0.0
    return len(ARABIC_RANGE.findall(letters)) / len(letters)


def is_arabic_majority(token: str) -> bool:
    return arabic_ratio(token) > WORD_ARABIC_RATIO_THRESHOLD


def fix_arabic_token(token: str) -> str:
    """Reverse the glyphs first, *then* NFKC-normalise.

    Order matters: a presentation-form ligature (e.g. LAM+ALEF-WITH-HAMZA as one
    glyph) expands to two letters under NFKC. Normalising before reversing would
    scramble the two letters that came from a single ligature.
    """
    return unicodedata.normalize("NFKC", token[::-1])


def fix_rtl_line_order(text: str) -> str:
    """Return `text` with each line put back into logical reading order."""
    fixed_lines: list[str] = []
    for line in text.split("\n"):
        line = line.replace(TATWEEL, "")
        tokens = [t for t in line.split(" ") if t]
        if not tokens:
            fixed_lines.append("")
            continue

        arabic_dominant = arabic_ratio(line) > LINE_ARABIC_RATIO_THRESHOLD
        if arabic_dominant:
            # Reverse the *whole* sequence: numbers/dates inside the line must
            # not act as fixed anchors or word order around them stays wrong.
            tokens = tokens[::-1]

        fixed: list[str] = []
        for token in tokens:
            if is_arabic_majority(token):
                fixed.append(fix_arabic_token(token))
            else:
                token = unicodedata.normalize("NFKC", token)
                if arabic_dominant:
                    token = token.translate(BIDI_MIRROR)
                fixed.append(token)
        fixed_lines.append(" ".join(fixed))
    return "\n".join(fixed_lines)
