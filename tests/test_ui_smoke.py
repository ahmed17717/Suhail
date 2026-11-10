"""Drives the real Streamlit app (headless) with fake models injected."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from suhail import bootstrap
from suhail.config import Settings
from suhail.security import hash_password
from suhail.ui import strings as S
from suhail.ui.chat_tab import md_escape, to_turns
from tests.fakes import FakeEmbedding, FakeGenerator

PASSWORD = "a-long-test-password"
APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture
def app(tmp_path, monkeypatch):
    import streamlit as st

    st.cache_resource.clear()
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", hash_password(PASSWORD))
    monkeypatch.setenv("LLM_MODEL_PATH", str(tmp_path / "unused.gguf"))
    generator = FakeGenerator(reply="ثلاثون يوماً")
    built = {}

    def fake_build(settings: Settings):
        built["services"] = bootstrap.build_services(
            settings, embedding_function=FakeEmbedding(), generator=generator
        )
        return built["services"]

    monkeypatch.setattr("suhail.ui.app.build_services", fake_build)
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.generator, at.built = generator, built
    return at


def texts(at):
    return [m.value for m in at.markdown]


def test_app_starts_with_greeting_and_no_exception(app):
    assert not app.exception
    assert len(app.chat_message) == 1
    assert "سهيل" in app.chat_message[0].markdown[0].value


def test_question_is_answered_with_sources(app):
    app.built["services"].ingestion.ingest_file("leave-policy.txt", b"annual leave is thirty days")
    app.chat_input[0].set_value("annual leave days").run()
    assert not app.exception
    assert any("ثلاثون يوماً" in t for t in texts(app))
    assert any("leave\\-policy\\.txt" in t for t in texts(app))  # cited, markdown-escaped


def test_unrelated_question_gets_fallback_and_no_citation(app):
    app.chat_input[0].set_value("zzz qqq nothing known").run()
    assert any(S.CHAT_ERROR not in t and "لا تتوفر" in t for t in texts(app))
    assert not app.expander


def test_model_failure_shows_friendly_message_not_a_traceback(app):
    app.built["services"].ingestion.ingest_file("a.txt", b"annual leave is thirty days")
    app.generator.error = RuntimeError("cuda out of memory")
    app.chat_input[0].set_value("annual leave days").run()
    assert not app.exception
    assert any(S.CHAT_ERROR in t for t in texts(app))
    assert not any("cuda" in t for t in texts(app))


def test_admin_rejects_wrong_password_and_accepts_the_right_one(app):
    app.text_input[0].set_value("wrong password").run()
    app.button[0].click().run()
    assert [e.value for e in app.error] == [S.ADMIN_WRONG_PASSWORD]

    app.text_input[0].set_value(PASSWORD).run()
    app.button[0].click().run()
    assert any(h.value == S.ADMIN_TITLE for h in app.header)


def test_admin_locks_after_repeated_failures(app):
    for _ in range(5):
        app.text_input[0].set_value("nope nope nope").run()
        app.button[0].click().run()
    app.text_input[0].set_value(PASSWORD).run()
    app.button[0].click().run()  # even the right password is refused while locked
    assert any("حاول مجدداً" in e.value for e in app.error)
    assert not any(h.value == S.ADMIN_TITLE for h in app.header)


def test_admin_is_disabled_when_no_password_hash_is_configured(app, monkeypatch):
    import streamlit as st

    st.cache_resource.clear()
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "")
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert [w.value for w in at.warning] == [S.ADMIN_DISABLED]
    assert len(at.text_input) == 0  # no login form is even offered


def test_invalid_configuration_is_reported_not_crashed(tmp_path, monkeypatch):
    import streamlit as st

    st.cache_resource.clear()
    monkeypatch.setenv("TOP_K", "banana")
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert any("TOP_K" in e.value for e in at.error)


def test_to_turns_skips_greeting_and_failed_replies():
    msgs = [
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "boom", "error": True},
    ]
    assert [(t.question, t.answer) for t in to_turns(msgs)] == [("q1", "a1")]


def test_md_escape_neutralises_markdown():
    assert md_escape("a_b*c.pdf") == r"a\_b\*c\.pdf"
