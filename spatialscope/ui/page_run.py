from __future__ import annotations

import streamlit as st

from spatialscope.ui.state import set_run
from spatialscope.ui.v6_helpers import h, render_dataset_identity_strip
from spatialscope.ui.v6_runner import render_current_step, render_timeline, stream_approved


def _switch_to_explore() -> None:
    explore_page = st.session_state.get("_v6_explore_page")
    if explore_page is not None:
        st.switch_page(explore_page)


def _render_waiting_for_approval(state: dict) -> None:
    render_dataset_identity_strip(state)
    st.markdown(
        """
        <div class="v6-page-lede compact">
          <h1>方案等待批准</h1>
          <p>批准后，LangGraph 节点会在本页以时间线方式直播执行。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    main, side = st.columns([0.7, 0.3], gap="large")
    with main:
        render_timeline(state)
    with side:
        render_current_step(state)
        if st.button("批准并运行", type="primary", width="stretch", key="run_page_approve"):
            st.session_state.pending_run_approval = True
            st.session_state.pending_run_plan_source = "run_page_approved"
            st.rerun()


def _render_completed(state: dict) -> None:
    render_dataset_identity_strip(state)
    if state.get("warnings"):
        st.warning("\n".join(map(str, state.get("warnings", [])[:5])))
    if state.get("errors"):
        st.error("\n".join(map(str, state.get("errors", [])[:5])))
    main, side = st.columns([0.7, 0.3], gap="large")
    with main:
        st.markdown("<div class='v6-flow-label'>Live execution timeline</div>", unsafe_allow_html=True)
        render_timeline(state)
    with side:
        render_current_step(state)
        st.markdown(
            f"""
            <div class="v6-run-complete">
              <div class="v6-overline">分析完成</div>
              <h3>{len(state.get("execution_trace", []) or [])} events · {len(state.get("generated_figures", []) or [])} figures · {len(state.get("generated_tables", []) or [])} tables</h3>
              <p>{h("0 unresolved errors" if not state.get("errors") else str(len(state.get("errors", []))) + " errors recorded")}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("打开探索工作区", type="primary", width="stretch"):
            _switch_to_explore()


def _render_live(state: dict) -> None:
    render_dataset_identity_strip(state)
    st.markdown(
        """
        <div class="v6-page-lede compact">
          <h1>正在运行分析</h1>
          <p>工具执行、校验和修复事件会随着 LangGraph 节点完成持续更新。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    main, side = st.columns([0.7, 0.3], gap="large")
    timeline_slot = main.empty()
    current_slot = side.empty()
    interrupt_slot = side.empty()
    final = stream_approved(
        state,
        plan_source=str(st.session_state.get("pending_run_plan_source") or "project_approved"),
        timeline_slot=timeline_slot,
        current_slot=current_slot,
        interrupt_slot=interrupt_slot,
    )
    set_run(final)
    st.session_state.pending_run_approval = False
    st.session_state.pending_run_plan_source = ""
    st.success("分析完成。")
    if st.button("打开探索工作区", type="primary", width="stretch"):
        _switch_to_explore()


def run_page() -> None:
    draft = st.session_state.get("draft_state")
    run_state = st.session_state.get("run_state")
    if draft and st.session_state.get("pending_run_approval"):
        _render_live(draft)
        return
    if draft and not run_state:
        _render_waiting_for_approval(draft)
        return
    if run_state:
        _render_completed(run_state)
        return
    st.markdown(
        """
        <div class="v6-empty-note">
          <h2>还没有可运行的方案</h2>
          <p>请先在项目页选择数据并生成分析方案。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
