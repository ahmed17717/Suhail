"""Visual theme: RTL layout, gold palette, locally bundled Tajawal font.

The font is served from `static/fonts/` (Streamlit static serving) instead of Google
Fonts: the app runs on an internal network that often has no internet access, and a
page that silently calls out to a third party would be a privacy leak anyway.
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

FONT_BASE = "app/static/fonts"

_CSS = f"""
<style>
@font-face {{ font-family: 'Tajawal'; font-weight: 400; font-display: swap;
  src: url('{FONT_BASE}/Tajawal-Regular.ttf') format('truetype'); }}
@font-face {{ font-family: 'Tajawal'; font-weight: 500; font-display: swap;
  src: url('{FONT_BASE}/Tajawal-Medium.ttf') format('truetype'); }}
@font-face {{ font-family: 'Tajawal'; font-weight: 700; font-display: swap;
  src: url('{FONT_BASE}/Tajawal-Bold.ttf') format('truetype'); }}

* {{ direction: rtl; text-align: right; font-family: 'Tajawal', sans-serif; }}

.block-container {{ padding-top: 1.5rem; padding-bottom: 6rem; max-width: 900px; }}

.app-header {{
    display: flex; align-items: center; justify-content: center;
    padding: 1.4rem; margin-bottom: 1.6rem; border-radius: 16px;
    background: linear-gradient(135deg, #8D7230 0%, #C8A142 100%);
    box-shadow: 0 4px 14px rgba(141, 114, 48, 0.25);
}}
.app-header img {{ max-width: 600px; width: 100%; height: auto; }}

div[data-testid="stChatMessageContent"] {{
    background-color: #F7F7F7; border: 1px solid #EAEAEA; border-radius: 14px;
    padding: 0.9rem 1.1rem; color: #2B2B2D;
}}
div[data-testid="stChatMessage"] {{ align-items: center; }}

.stButton button {{
    border-radius: 10px; font-weight: 500; background-color: #B58F3A;
    color: #FFFFFF; border: none;
}}
.stButton button:hover {{ background-color: #9E7B2F; color: #FFFFFF; }}

input, textarea {{ border-radius: 10px !important; border: 1px solid #DDD !important; }}

.stTabs [data-baseweb="tab-list"] {{ gap: 6px; }}
.stTabs [data-baseweb="tab"] {{ border-radius: 10px 10px 0 0; padding: 8px 18px; }}
.stTabs [aria-selected="true"] {{
    color: #B58F3A !important; border-bottom: 2px solid #B58F3A !important;
}}

div[data-testid="stChatInput"] {{
    position: fixed; bottom: 0; left: 50%; transform: translateX(-50%);
    width: 100%; max-width: 860px; background-color: #FFFFFF;
    padding: 0.8rem 1rem; border-top: 1px solid #EAEAEA; z-index: 999;
}}

.doc-type-badge {{
    display: inline-block; font-size: 0.75rem; padding: 2px 10px; border-radius: 999px;
    background-color: #F1E7D0; color: #8D7230; margin-inline-start: 8px;
}}
</style>
"""


def inject_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def asset(assets_dir: Path, filename: str) -> str | None:
    """Path to a branding asset, or None if the deployment doesn't provide it."""
    path = Path(assets_dir) / filename
    return str(path) if path.is_file() else None


def render_header(assets_dir: Path) -> None:
    logo = asset(assets_dir, "header_logo.png")
    img = ""
    if logo:
        encoded = base64.b64encode(Path(logo).read_bytes()).decode()
        img = f'<img src="data:image/png;base64,{encoded}" alt="logo" />'
    st.markdown(f'<div class="app-header">{img}</div>', unsafe_allow_html=True)
