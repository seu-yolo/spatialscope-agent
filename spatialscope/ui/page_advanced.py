from __future__ import annotations

import pandas as pd
import streamlit as st

from spatialscope.ui.components import (
    render_acknowledgements,
    render_audits,
    render_llm_status,
    render_public_state_json,
    render_report_assets,
    render_run_library,
    render_tool_registry,
    render_trace,
)
from spatialscope.ui.helpers import plan_from_state, plan_to_text
from spatialscope.ui.state import active_state, set_run
from spatialscope.utils.run_index import load_run_state


def advanced_page() -> None:
    state = active_state()
    st.markdown(
        """
        <div class="v6-page-lede compact">
          <h1>Advanced / Provenance</h1>
          <p>技术元数据、LLM 状态、工具注册表、运行历史和原始状态集中放在这里，不干扰主研究流程。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    left, right = st.columns([0.58, 0.42], gap="large")
    with left:
        render_llm_status(key_prefix="advanced_llm")
        render_acknowledgements()
        st.markdown("<div class='v6-flow-label'>Tool Registry</div>", unsafe_allow_html=True)
        render_tool_registry()
        if state:
            st.markdown("<div class='v6-flow-label'>Execution trace</div>", unsafe_allow_html=True)
            render_trace(state)
            if state.get("llm_calls"):
                st.markdown("<div class='v6-flow-label'>LLM telemetry</div>", unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(state["llm_calls"]), hide_index=True, width="stretch", height=260)
    with right:
        outdir = str(state.get("outdir") if state else "outputs/runs")
        outdir = st.text_input("Run library outdir", value=outdir)
        library = render_run_library(outdir)
        if library:
            run_id = st.selectbox("载入历史 run", library["options"])
            if st.button("载入到工作台", width="stretch"):
                try:
                    loaded = load_run_state(library["run_by_id"][run_id]["run_dir"])
                    set_run(loaded)
                    st.session_state.plan_text = plan_to_text(plan_from_state(loaded))
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"载入失败：{exc}")
        if state:
            st.markdown("<div class='v6-flow-label'>Artifact downloads</div>", unsafe_allow_html=True)
            render_report_assets(state, primary=False)
            st.markdown("<div class='v6-flow-label'>Audits</div>", unsafe_allow_html=True)
            render_audits(state)
            st.markdown("<div class='v6-flow-label'>Raw public state</div>", unsafe_allow_html=True)
            render_public_state_json(state)
