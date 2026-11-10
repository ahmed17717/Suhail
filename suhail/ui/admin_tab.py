"""The administrator tab: sign-in, upload, manual text, document management."""

from __future__ import annotations

import html
import logging
import time

import streamlit as st

from suhail.bootstrap import Services
from suhail.errors import IngestionError
from suhail.security import verify_password
from suhail.ui import strings as S

logger = logging.getLogger(__name__)
audit = logging.getLogger("suhail.audit")


# ---- authentication ------------------------------------------------------------
def _is_authenticated(services: Services) -> bool:
    started = st.session_state.get("admin_since")
    if started is None:
        return False
    if time.time() - started > services.settings.admin_session_minutes * 60:
        st.session_state.admin_since = None
        st.warning(S.ADMIN_SESSION_EXPIRED)
        return False
    return True


def _render_login(services: Services) -> None:
    st.header(S.ADMIN_LOGIN_TITLE)
    password = st.text_input(S.ADMIN_PASSWORD, type="password")
    if not st.button(S.ADMIN_LOGIN_BUTTON):
        return

    throttle = services.login_throttle
    wait = throttle.seconds_until_allowed()
    if wait:
        st.error(S.admin_locked(wait))
        return
    if verify_password(password, services.settings.admin_password_hash):
        throttle.reset()
        st.session_state.admin_since = time.time()
        audit.info("action=admin_login result=success")
        st.rerun()
    throttle.record_failure()
    audit.warning("action=admin_login result=failure")
    st.error(S.ADMIN_WRONG_PASSWORD)


# ---- helpers -------------------------------------------------------------------
def _show_ingestion_error(services: Services, exc: Exception) -> None:
    if isinstance(exc, IngestionError):
        st.error(S.ingestion_error_message(type(exc).__name__, services.settings.max_upload_mb))
    else:
        logger.exception("Unexpected error during ingestion")
        st.error(S.UNEXPECTED_ERROR)


def _doc_label(name: str, type_label: str) -> str:
    # Names are user-supplied and rendered with unsafe_allow_html, so escape them.
    return f"{html.escape(name)} <span class='doc-type-badge'>{type_label}</span>"


# ---- sections ------------------------------------------------------------------
def _render_upload(services: Services) -> None:
    st.subheader(S.UPLOAD_TITLE)
    uploaded = st.file_uploader(S.UPLOAD_CHOOSE, type=["pdf", "docx", "txt"])

    if uploaded and st.button(S.UPLOAD_BUTTON):
        data = uploaded.getvalue()
        if services.ingestion.find_duplicate(uploaded.name):
            st.session_state.pending_duplicate = {"name": uploaded.name, "data": data}
        else:
            try:
                with st.spinner(S.UPLOAD_SPINNER):
                    record = services.ingestion.ingest_file(uploaded.name, data)
                st.success(S.uploaded_ok(record.name, record.chunk_count))
            except Exception as exc:
                _show_ingestion_error(services, exc)

    pending = st.session_state.get("pending_duplicate")
    if pending:
        st.warning(S.duplicate_warning(pending["name"]))
        yes, no = st.columns(2)
        if yes.button(S.REPLACE_YES):
            try:
                with st.spinner(S.UPLOAD_SPINNER):
                    services.ingestion.ingest_file(pending["name"], pending["data"], replace=True)
                st.session_state.pending_duplicate = None
                st.success(S.REPLACED_OK)
                st.rerun()
            except IngestionError as exc:
                _show_ingestion_error(services, exc)
        if no.button(S.CANCEL):
            st.session_state.pending_duplicate = None
            st.rerun()


def _render_manual_text(services: Services) -> None:
    st.subheader(S.MANUAL_TITLE)
    title = st.text_input(S.MANUAL_NAME)
    body = st.text_area(S.MANUAL_BODY)
    if st.button(S.MANUAL_SAVE) and body.strip():
        try:
            services.ingestion.ingest_text(title, body)
            st.success(S.MANUAL_SAVED)
        except Exception as exc:
            _show_ingestion_error(services, exc)


def _render_documents(services: Services) -> None:
    st.subheader(S.DOCS_TITLE)
    records = services.registry.all()
    if not records:
        st.write(S.DOCS_EMPTY)
        return

    editing = st.session_state.get("editing_doc_id")
    confirming = st.session_state.get("confirm_delete_id")

    for record in records:
        type_label = S.TYPE_MANUAL if record.doc_type == "manual" else S.TYPE_FILE
        label = _doc_label(record.name, type_label)

        if editing == record.doc_id:
            st.markdown(f"**{html.escape(record.name)}**", unsafe_allow_html=True)
            new_text = st.text_area(
                S.EDIT_TEXT, value=record.raw_text or "", key=f"edit_{record.doc_id}"
            )
            save, cancel = st.columns(2)
            if save.button(S.EDIT_SAVE, key=f"save_{record.doc_id}"):
                try:
                    services.ingestion.update_text(record.doc_id, new_text)
                    st.session_state.editing_doc_id = None
                    st.rerun()
                except IngestionError as exc:
                    _show_ingestion_error(services, exc)
            if cancel.button(S.CANCEL, key=f"cancel_{record.doc_id}"):
                st.session_state.editing_doc_id = None
                st.rerun()
        elif confirming == record.doc_id:
            st.warning(S.delete_confirm(record.name))
            yes, no = st.columns(2)
            if yes.button(S.DELETE_CONFIRM_YES, key=f"confirm_{record.doc_id}"):
                services.ingestion.delete(record.doc_id)
                st.session_state.confirm_delete_id = None
                st.rerun()
            if no.button(S.CANCEL, key=f"nodelete_{record.doc_id}"):
                st.session_state.confirm_delete_id = None
                st.rerun()
        else:
            name_col, edit_col, delete_col = st.columns([4, 1, 1])
            name_col.markdown(
                f"{label}<br><small>{S.chunks_label(record.chunk_count)}</small>",
                unsafe_allow_html=True,
            )
            if record.doc_type == "manual" and edit_col.button(
                S.EDIT, key=f"editbtn_{record.doc_id}"
            ):
                st.session_state.editing_doc_id = record.doc_id
                st.rerun()
            if delete_col.button(S.DELETE, key=f"delbtn_{record.doc_id}"):
                st.session_state.confirm_delete_id = record.doc_id
                st.rerun()


# ---- entry point ---------------------------------------------------------------
def render_admin_tab(services: Services) -> None:
    if not services.settings.admin_password_hash:
        st.warning(S.ADMIN_DISABLED)  # fail closed: no hash configured => no admin access
        return

    if not _is_authenticated(services):
        _render_login(services)
        return

    st.header(S.ADMIN_TITLE)
    if st.button(S.ADMIN_LOGOUT):
        st.session_state.admin_since = None
        st.rerun()

    _render_upload(services)
    _render_manual_text(services)
    _render_documents(services)
