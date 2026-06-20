from __future__ import annotations

from typing import Any

import streamlit as st

from spatialscope.agent.runtime import AgentRuntime
from spatialscope.ui.actions import ensure_explore_state


def init_session_state() -> None:
    defaults: dict[str, Any] = {
        "draft_state": None,
        "run_state": None,
        "plan_text": "",
        "last_plan_error": "",
        "loaded_run_notice": "",
        "main_nav": "项目 Project",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    ensure_explore_state()
    if "agent_runtime" not in st.session_state:
        st.session_state.agent_runtime = AgentRuntime()


def runtime() -> AgentRuntime:
    init_session_state()
    return st.session_state.agent_runtime


def active_state() -> dict[str, Any] | None:
    return st.session_state.run_state or st.session_state.draft_state


def set_draft(state: dict[str, Any]) -> None:
    st.session_state.draft_state = state
    st.session_state.run_state = None


def set_run(state: dict[str, Any]) -> None:
    st.session_state.run_state = state
    st.session_state.draft_state = None
