from __future__ import annotations

import streamlit as st

from spatialscope.ui.components import render_linked_explore
from spatialscope.ui.components.scene_frame import scene_frame
from spatialscope.ui.run_restore import restore_latest_run_if_needed


def explore_page() -> None:
    state = restore_latest_run_if_needed()
    if not state:
        st.markdown(
            """
            <div class="v6-empty-note">
              <h2>探索工作区尚未准备好</h2>
              <p>请先批准并完成一次分析运行。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return
    with scene_frame(
        key="explore_scene",
        index="04 / 05",
        eyebrow="EVIDENCE EXPLORATION",
        title="证据探索工作区",
        subtitle="空间图、UMAP、表达层和 Copilot 使用同一组 evidence IDs；解释必须回到当前视图中的证据。",
    ):
        render_linked_explore(state)
