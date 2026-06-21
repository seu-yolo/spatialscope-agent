from __future__ import annotations

import streamlit as st

from spatialscope.ui.components import render_linked_explore
from spatialscope.ui.v6_helpers import render_dataset_identity_strip


def explore_page() -> None:
    state = st.session_state.get("run_state")
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
    render_dataset_identity_strip(state)
    st.markdown(
        """
        <div class="v6-page-lede compact">
          <h1>证据探索工作区</h1>
          <p>空间图、UMAP、表达层和 Copilot 使用同一组 evidence IDs；解释必须回到当前视图中的证据。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_linked_explore(state)
