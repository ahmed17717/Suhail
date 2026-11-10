"""Tiny Arabic shaper used only to *generate* realistic PDF-style test input.

Real PDFs that store pre-shaped presentation forms hand the extractor glyphs in
visual (mirrored) order. This helper produces exactly that from logical text, so the
RTL repair code can be tested with a round trip: logical -> visual -> repaired.
It deliberately skips lam-alef ligatures; those are covered by an explicit test.
"""

from __future__ import annotations

import unicodedata

_FORMS: dict[tuple[str, str], str] = {}
for _cp in list(range(0xFE70, 0xFF00)):
    _decomp = unicodedata.decomposition(chr(_cp))
    if _decomp.startswith("<") and len(_decomp.split()) == 2:
        _tag, _base = _decomp.split()
        _FORMS[(chr(int(_base, 16)), _tag.strip("<>"))] = chr(_cp)


def _connects_forward(ch: str) -> bool:
    return (ch, "initial") in _FORMS


def shape(word: str) -> str:
    out = []
    for i, ch in enumerate(word):
        prev_joins = i > 0 and _connects_forward(word[i - 1])
        has_next = i < len(word) - 1 and (ch, "initial") in _FORMS
        if prev_joins and has_next:
            form = "medial"
        elif prev_joins:
            form = "final"
        elif has_next:
            form = "initial"
        else:
            form = "isolated"
        out.append(_FORMS.get((ch, form), ch))
    return "".join(out)


def to_visual(logical_line: str) -> str:
    """What a naive extractor returns for a pre-shaped RTL line."""
    from suhail.ingestion.rtl import BIDI_MIRROR, is_arabic_majority

    tokens = []
    for tok in logical_line.split(" "):
        if is_arabic_majority(tok):
            tokens.append(shape(tok)[::-1])
        else:
            tokens.append(tok.translate(BIDI_MIRROR))
    return " ".join(reversed(tokens))
