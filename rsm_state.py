from __future__ import annotations

import secrets

import streamlit as st


def round_decimal_input_state(key: str, digits: int = 4) -> None:
    value = st.session_state.get(key)
    if value is not None:
        st.session_state[key] = round(float(value), digits)


def initialize_input_session_nonce() -> None:
    if "_input_reset_nonce" not in st.session_state:
        st.session_state["_input_reset_nonce"] = secrets.randbits(63)


def capture_design_table_edit(component_key: str, store_key: str) -> None:
    component_result = st.session_state.get(component_key)
    payload = getattr(component_result, "edit", None)
    if payload is None and isinstance(component_result, dict):
        payload = component_result.get("edit")
    if isinstance(payload, dict):
        st.session_state[store_key] = payload


def component_state_value(component_key: str, field: str, default: object) -> object:
    component_result = st.session_state.get(component_key)
    value = getattr(component_result, field, None)
    if value is None and isinstance(component_result, dict):
        value = component_result.get(field)
    return default if value is None else value


def reset_input_state() -> None:
    next_nonce = int(st.session_state.get("_input_reset_nonce", 0)) + 1
    st.session_state.clear()
    st.session_state["_input_reset_nonce"] = next_nonce


def clear_design_input_state_once(version: str) -> None:
    marker_key = f"_design_input_state_cleared_{version}"
    if st.session_state.get(marker_key):
        return
    prefixes = (
        "design_editor_",
        "design_y_store_",
        "design_table_event_",
        "design_response_paste_text_",
        "design_plain_response_text_",
        "design_plain_response_store_",
        "design_plain_response_form_",
        "design_excel_clipboard_",
        "design_response_grid_",
        "design_table_response_store_",
        "design_fill_",
    )
    for key in list(st.session_state.keys()):
        if any(str(key).startswith(prefix) for prefix in prefixes):
            del st.session_state[key]
    st.session_state[marker_key] = True
