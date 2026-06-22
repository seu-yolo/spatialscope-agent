from __future__ import annotations

import os
from typing import Literal, TypedDict

import streamlit as st


ProjectStage = Literal[
    "landing",
    "dataset_inspected",
    "plan_review",
    "running",
    "explore",
    "report",
]


class SignatureMeta(TypedDict):
    author: str
    email: str
    affiliation: str


def set_project_stage(stage: ProjectStage) -> None:
    st.session_state.project_stage = stage


def project_stage_for_state(state: dict | None) -> ProjectStage:
    if not state:
        return "landing"
    requested = st.session_state.get("project_stage")
    if requested == "plan_review":
        return "plan_review"
    if state.get("report_path"):
        return "report"
    return "dataset_inspected"


def signature_meta() -> SignatureMeta:
    return {
        "author": os.getenv("SPATIALSCOPE_AUTHOR_NAME", "").strip(),
        "email": os.getenv("SPATIALSCOPE_AUTHOR_EMAIL", "").strip(),
        "affiliation": os.getenv("SPATIALSCOPE_AFFILIATION", "Southeast University · Computational Biology").strip(),
    }


def stage_dot(label: str, *, active: bool = False) -> str:
    cls = "active" if active else ""
    return f"<span class='v7-status-dot {cls}'></span>{label}"
