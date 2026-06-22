from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import streamlit as st

from spatialscope.ui.v6_helpers import h


def render_scene_header(*, index: str, eyebrow: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="v7-scene-header">
          <div class="v7-stage-row">
            <span class="v7-stage-index">{h(index)}</span>
            <span class="v7-stage-line"></span>
            <span class="v7-stage-eyebrow">{h(eyebrow)}</span>
          </div>
          <h1>{h(title)}</h1>
          <p>{h(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


@contextmanager
def scene_frame(*, key: str, index: str, eyebrow: str, title: str, subtitle: str) -> Iterator[None]:
    with st.container(key=key):
        render_scene_header(index=index, eyebrow=eyebrow, title=title, subtitle=subtitle)
        yield


def render_scene_action_hint(text: str) -> None:
    st.markdown(f"<div class='v7-action-hint'>{h(text)}</div>", unsafe_allow_html=True)
