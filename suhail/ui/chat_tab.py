"""The employee-facing chat tab."""

from __future__ import annotations

import logging
import re
from itertools import pairwise

import streamlit as st

from suhail.bootstrap import Services
from suhail.models import Answer, Turn
from suhail.rag.pipeline import MAX_HISTORY_TURNS, MAX_QUESTION_CHARS
from suhail.ui import strings as S
from suhail.ui.theme import asset

logger = logging.getLogger(__name__)

_MD_SPECIALS = re.compile(r"([\\`*_{}\[\]()#+\-.!|>~])")


def md_escape(text: str) -> str:
    """Neutralise Markdown so a file name like `a_b*.pdf` renders literally."""
    return _MD_SPECIALS.sub(r"\\\1", text)


def to_turns(messages: list[dict]) -> list[Turn]:
    """Pair consecutive user→assistant messages into completed turns.

    The greeting (assistant with no preceding question) and failed replies are skipped,
    so neither pollutes the context sent to the model.
    """
    turns: list[Turn] = []
    for first, second in pairwise(messages):
        if first["role"] == "user" and second["role"] == "assistant" and not second.get("error"):
            turns.append(Turn(first["content"], second["content"]))
    return turns


def _greeting(services: Services) -> list[dict]:
    return [{"role": "assistant", "content": services.settings.welcome_message, "sources": []}]


def _render_sources(sources: list[tuple[str, int | None]]) -> None:
    if not sources:
        return
    with st.expander(S.SOURCES_LABEL):
        for doc_name, page in sources:
            suffix = f" — {S.PAGE_LABEL} {page}" if page else ""
            st.markdown(f"- {md_escape(doc_name)}{suffix}")


def _render_message(services: Services, message: dict) -> None:
    avatar_name = "assistant_avatar.png" if message["role"] == "assistant" else "user_avatar.png"
    with st.chat_message(message["role"], avatar=asset(services.settings.assets_dir, avatar_name)):
        st.write(message["content"])
        _render_sources(message.get("sources", []))


def _answer_safely(services: Services, question: str, history: list[Turn]) -> Answer | None:
    try:
        with st.spinner(S.CHAT_SPINNER):
            return services.pipeline.answer(question, history)
    except Exception:
        logger.exception("Unhandled error while answering")
        return None


def render_chat_tab(services: Services) -> None:
    if "messages" not in st.session_state:
        st.session_state.messages = _greeting(services)

    for message in st.session_state.messages:
        _render_message(services, message)

    question = st.chat_input(S.CHAT_PLACEHOLDER, max_chars=MAX_QUESTION_CHARS)
    if question:
        history = to_turns(st.session_state.messages)[-MAX_HISTORY_TURNS:]
        user_message = {"role": "user", "content": question}
        st.session_state.messages.append(user_message)
        _render_message(services, user_message)

        with st.chat_message(
            "assistant", avatar=asset(services.settings.assets_dir, "assistant_avatar.png")
        ):
            answer = _answer_safely(services, question, history)
            if answer is None:
                reply = {"role": "assistant", "content": S.CHAT_ERROR, "sources": [], "error": True}
            else:
                reply = {
                    "role": "assistant",
                    "content": answer.text,
                    "sources": [(s.doc_name, s.page) for s in answer.sources],
                }
            st.write(reply["content"])
            _render_sources(reply["sources"])
        st.session_state.messages.append(reply)

    if len(st.session_state.messages) > 1 and st.button(S.CHAT_CLEAR):
        st.session_state.messages = _greeting(services)
        st.rerun()
