"""Streamlit page assembly: config → theme → header → tabs."""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from suhail.bootstrap import Services, build_services, configure_logging
from suhail.config import Settings
from suhail.errors import SuhailError
from suhail.ui import strings as S
from suhail.ui.admin_tab import render_admin_tab
from suhail.ui.chat_tab import render_chat_tab
from suhail.ui.theme import asset, inject_theme, render_header


@st.cache_resource
def get_settings() -> Settings:
    load_dotenv()
    settings = Settings.from_env(os.environ)
    configure_logging(settings.log_level)
    return settings


@st.cache_resource(show_spinner=False)
def get_services() -> Services:
    """Built once per server process and shared by every session."""
    return build_services(get_settings())


def main() -> None:
    try:
        settings = get_settings()
    except SuhailError as exc:  # invalid configuration: say exactly what is wrong
        st.set_page_config(page_title="Suhail")
        st.error(f"{S.STARTUP_ERROR}: {exc}")
        st.stop()

    st.set_page_config(
        page_title=settings.app_title,
        page_icon=asset(settings.assets_dir, "favicon.png"),
        layout="wide",
    )
    inject_theme()
    render_header(settings.assets_dir)

    try:
        services = get_services()
    except SuhailError as exc:  # e.g. model file missing
        st.error(f"{S.STARTUP_ERROR}: {exc}")
        st.stop()

    chat_tab, admin_tab = st.tabs([S.TAB_CHAT, S.TAB_ADMIN])
    with chat_tab:
        render_chat_tab(services)
    with admin_tab:
        render_admin_tab(services)
