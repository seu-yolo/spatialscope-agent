from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from spatialscope.utils.demo import ensure_demo_data, get_demo_preset
from spatialscope.utils.run_index import load_run_state

from .components import (
    ACKNOWLEDGEMENTS,
    PROJECT_SIGNATURE,
    render_audits,
    render_contextual_copilot,
    render_dataset_profile,
    render_evidence_metrics,
    render_figures,
    render_header,
    render_linked_explore,
    render_llm_status,
    render_plan_cards,
    render_public_state_json,
    render_report_assets,
    render_report_findings,
    render_research_brief,
    render_run_library,
    render_tables,
    render_tool_registry,
    render_trace,
    render_workflow,
)
from .helpers import (
    MODE_VALUES,
    apply_ui_overrides,
    load_plan_from_text,
    plan_from_state,
    plan_to_text,
    save_upload,
)
from .state import active_state, runtime, set_draft, set_run


def _prepare_state(
    *,
    data_path: str,
    query: str,
    mode: str,
    outdir: str,
    min_genes: int,
    min_cells: int,
    max_mt_pct: float,
    resolution: float,
    gene_text: str,
    annotation_top_n: int,
) -> dict[str, Any]:
    state = runtime().start_run(
        data_path=data_path,
        query=query,
        mode=mode,  # type: ignore[arg-type]
        outdir=outdir,
        auto_approve=False,
    )
    return apply_ui_overrides(
        state,
        min_genes=min_genes,
        min_cells=min_cells,
        max_mt_pct=max_mt_pct,
        resolution=resolution,
        gene_text=gene_text,
        annotation_top_n=annotation_top_n,
    )


def _run_approved(state: dict[str, Any], *, plan_source: str = "user_edited") -> dict[str, Any]:
    plan = plan_from_state(state)
    return runtime().resume_run(
        str(state.get("thread_id") or state.get("run_id")),
        approved_plan=plan,
        plan_source=plan_source,
    )


def _stream_approved(state: dict[str, Any], *, plan_source: str = "user_edited") -> dict[str, Any]:
    plan = plan_from_state(state)
    thread_id = str(state.get("thread_id") or state.get("run_id"))
    status_slot = st.empty()
    workflow_slot = st.empty()
    trace_slot = st.empty()
    final_state = dict(state)
    for update in runtime().stream_resume(thread_id, approved_plan=plan, plan_source=plan_source):
        snapshot = runtime().state_snapshot(thread_id)
        values = dict(getattr(snapshot, "values", {}) or {})
        if values:
            final_state = values
        node_names = ", ".join(update.keys()) if isinstance(update, dict) else "graph event"
        status_slot.info(f"LangGraph event: {node_names}")
        with workflow_slot.container():
            render_workflow(final_state)
        if final_state.get("execution_trace"):
            with trace_slot.container():
                render_trace(final_state)
    snapshot = runtime().state_snapshot(thread_id)
    values = dict(getattr(snapshot, "values", {}) or {})
    return values or final_state


def render_workspace_page() -> None:
    st.markdown("<div class='ss-section-title'>Project</div>", unsafe_allow_html=True)
    left, right = st.columns([1.1, 0.9], gap="large")
    with left:
        preset = get_demo_preset()
        st.markdown(
            """
            <div class="ss-panel">
              <div class="ss-mini-label">Demo Launchpad</div>
              <div class="ss-card-title">一键生成适合展示的标准分析</div>
              <div class="ss-muted">使用内置 synthetic spatial AnnData，展示 plan review、trace、figures、report 和 reproducibility bundle。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        c_demo_plan, c_demo_run = st.columns(2)
        if c_demo_plan.button("生成 Demo 方案", width="stretch"):
            try:
                demo = ensure_demo_data(preset["data_path"])
                with st.spinner("准备 Demo 方案..."):
                    state = _prepare_state(
                        data_path=str(demo["path"]),
                        query=str(preset["query"]),
                        mode=str(preset["mode"]),
                        outdir=str(preset["outdir"]),
                        min_genes=int(preset["min_genes"]),
                        min_cells=int(preset["min_cells"]),
                        max_mt_pct=float(preset["max_mt_pct"]),
                        resolution=float(preset["resolution"]),
                        gene_text=str(preset["gene_text"]),
                        annotation_top_n=int(preset["annotation_top_n"]),
                    )
                set_draft(state)
                st.session_state.plan_text = plan_to_text(plan_from_state(state))
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))
        if c_demo_run.button("一键运行 Demo", type="primary", width="stretch"):
            try:
                demo = ensure_demo_data(preset["data_path"])
                with st.status("生成并运行 Demo workflow...", expanded=True):
                    state = _prepare_state(
                        data_path=str(demo["path"]),
                        query=str(preset["query"]),
                        mode=str(preset["mode"]),
                        outdir=str(preset["outdir"]),
                        min_genes=int(preset["min_genes"]),
                        min_cells=int(preset["min_cells"]),
                        max_mt_pct=float(preset["max_mt_pct"]),
                        resolution=float(preset["resolution"]),
                        gene_text=str(preset["gene_text"]),
                        annotation_top_n=int(preset["annotation_top_n"]),
                    )
                    final = _stream_approved(state, plan_source="demo_approved")
                set_run(final)
                st.session_state.plan_text = plan_to_text(plan_from_state(final))
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))

        uploaded = st.file_uploader("上传空间 AnnData 文件 (.h5ad)", type=["h5ad"])
        query = st.text_area(
            "分析任务",
            value="探索早期小鼠胚胎空间转录组结构，生成 marker genes，并绘制 Pou5f1 Sox2 Nanog Sox17 Gata6 T Mesp1 空间表达图。",
            height=118,
        )
        mode_label = st.segmented_control("运行模式", ["快速", "标准", "高阶"], default="标准") or "标准"

        with st.expander("高级输入与参数", expanded=False):
            default_data = st.text_input("本地数据路径", value="data/demo_embryo.h5ad")
            outdir = st.text_input("输出目录", value="outputs/runs")
            q1, q2, q3 = st.columns(3)
            min_genes = q1.number_input("每个 spot 最少基因数", min_value=0, max_value=5000, value=20, step=5)
            min_cells = q2.number_input("每个基因最少细胞数", min_value=0, max_value=200, value=3, step=1)
            max_mt_pct = q3.number_input("线粒体比例上限", min_value=0.0, max_value=100.0, value=25.0, step=1.0)
            r1, r2, r3 = st.columns([0.8, 1.3, 0.8])
            resolution = r1.slider("Leiden resolution", min_value=0.1, max_value=2.0, value=0.8, step=0.1)
            gene_text = r2.text_input("Gene panel override", value="", placeholder="留空则使用自然语言中的基因")
            annotation_top_n = r3.number_input("Annotation top N", min_value=3, max_value=30, value=12, step=1)
        upload_path = save_upload(uploaded)
        data_path = upload_path or default_data

        c_plan, c_run = st.columns(2)
        common = {
            "data_path": data_path,
            "query": query,
            "mode": MODE_VALUES.get(str(mode_label), "standard"),
            "outdir": outdir,
            "min_genes": int(min_genes),
            "min_cells": int(min_cells),
            "max_mt_pct": float(max_mt_pct),
            "resolution": float(resolution),
            "gene_text": gene_text,
            "annotation_top_n": int(annotation_top_n),
        }
        if c_plan.button("生成分析方案", type="primary", width="stretch"):
            try:
                with st.spinner("调用 Agent 生成可审阅方案..."):
                    state = _prepare_state(**common)
                set_draft(state)
                st.session_state.plan_text = plan_to_text(plan_from_state(state))
                st.session_state.last_plan_error = ""
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))
        if c_run.button("直接运行", width="stretch"):
            try:
                with st.spinner("生成方案并自动批准运行..."):
                    state = _prepare_state(**common)
                    final = _run_approved(state, plan_source="ui_auto_approved")
                set_run(final)
                st.session_state.plan_text = plan_to_text(plan_from_state(final))
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))

    with right:
        render_workflow(active_state())
        with st.expander("LLM status", expanded=False):
            render_llm_status(key_prefix="workspace_llm")


def render_plan_page() -> None:
    state = st.session_state.draft_state
    if not state:
        st.info("请先在 Workspace 生成一个分析方案。")
        return
    st.markdown("<div class='ss-section-title'>Plan Review</div>", unsafe_allow_html=True)
    render_workflow(state)
    render_research_brief(state)
    render_dataset_profile(state)
    st.caption(state.get("plan_rationale") or "No rationale recorded.")
    render_plan_cards(plan_from_state(state))
    if st.button("运行已批准方案", type="primary", width="stretch"):
        try:
            plan = plan_from_state(state)
            state["task_plan"] = plan
            state["approved_plan"] = plan
            final = _stream_approved(state, plan_source="user_edited")
            set_run(final)
            st.session_state.last_plan_error = ""
            st.rerun()
        except Exception as exc:  # noqa: BLE001
            st.session_state.last_plan_error = str(exc)
    if st.session_state.last_plan_error:
        st.error(st.session_state.last_plan_error)


def render_run_page() -> None:
    if st.session_state.draft_state and not st.session_state.run_state:
        state = st.session_state.draft_state
        st.markdown("<div class='ss-section-title'>Run</div>", unsafe_allow_html=True)
        st.info("Plan 已生成并等待批准。点击下面按钮后，LangGraph 事件会在本页实时更新。")
        render_workflow(state)
        if st.button("运行已批准方案", type="primary", width="stretch", key="run_page_stream_approved"):
            try:
                final = _stream_approved(state, plan_source="run_page_approved")
                set_run(final)
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))
        return
    state = st.session_state.run_state
    if not state:
        st.info("请先运行一个已批准方案。")
        return
    st.markdown("<div class='ss-section-title'>Run</div>", unsafe_allow_html=True)
    render_evidence_metrics(state)
    if state.get("warnings"):
        st.warning("\n".join(map(str, state.get("warnings", [])[:5])))
    if state.get("errors"):
        st.error("\n".join(map(str, state.get("errors", [])[:5])))
    render_workflow(state)
    render_trace(state)
    if state.get("repair_log"):
        st.markdown("<div class='ss-section-title'>Repair Log</div>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(state["repair_log"]), hide_index=True, width="stretch", height=280)
    with st.expander("Advanced provenance checks", expanded=False):
        render_audits(state)


def render_explore_page() -> None:
    state = st.session_state.run_state
    if not state:
        st.info("请先运行一个已批准方案。")
        return
    st.markdown("<div class='ss-section-title'>Explore</div>", unsafe_allow_html=True)
    render_linked_explore(state)
    render_contextual_copilot(state)
    with st.expander("All generated figures and tables", expanded=False):
        render_figures(state)
        render_tables(state)


def render_report_page() -> None:
    state = st.session_state.run_state
    if not state:
        st.info("请先运行一个已批准方案。")
        return
    st.markdown("<div class='ss-section-title'>Report</div>", unsafe_allow_html=True)
    render_evidence_metrics(state)
    with st.container(border=True):
        st.markdown("<div class='ss-mini-label'>Agent summary</div>", unsafe_allow_html=True)
        st.write(state.get("final_answer") or "No interpretation generated.")
    if state.get("warnings"):
        st.warning("\n".join(map(str, state.get("warnings", []))))
    if state.get("errors"):
        st.error("\n".join(map(str, state.get("errors", []))))
    render_report_findings(state)
    render_report_assets(state, primary=True)
    report_path = Path(str(state.get("report_path") or ""))
    if report_path.exists():
        with st.expander("Report HTML preview", expanded=False):
            st.html(report_path.read_text(encoding="utf-8"))


def render_provenance_page() -> None:
    state = active_state()
    st.markdown("<div class='ss-section-title'>Provenance</div>", unsafe_allow_html=True)
    left, right = st.columns([1.05, 0.95], gap="large")
    with left:
        render_llm_status(key_prefix="provenance_llm")
        st.markdown("<div class='ss-section-title'>Tool Registry</div>", unsafe_allow_html=True)
        render_tool_registry()
        if state:
            render_audits(state)
            st.markdown("<div class='ss-section-title'>Public State</div>", unsafe_allow_html=True)
            render_public_state_json(state)
            if state.get("llm_calls"):
                st.markdown("<div class='ss-section-title'>LLM Telemetry</div>", unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(state["llm_calls"]), hide_index=True, width="stretch", height=260)
    with right:
        outdir = "outputs/runs"
        if state and state.get("outdir"):
            outdir = str(state.get("outdir"))
        outdir = st.text_input("Run Library outdir", value=outdir)
        library = render_run_library(outdir)
        if library:
            run_id = st.selectbox("载入历史 run", library["options"])
            if st.button("载入到工作台", width="stretch"):
                try:
                    loaded = load_run_state(library["run_by_id"][run_id]["run_dir"])
                    set_run(loaded)
                    st.session_state.plan_text = plan_to_text(plan_from_state(loaded))
                    st.session_state.loaded_run_notice = f"已载入历史 run: {loaded.get('run_id', run_id)}"
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"载入失败：{exc}")


def render_project_page() -> None:
    render_workspace_page()
    if st.session_state.draft_state:
        st.markdown("---")
        render_plan_page()


def render_app() -> None:
    active = active_state()
    render_header(active)
    if st.session_state.loaded_run_notice:
        st.success(st.session_state.loaded_run_notice)
        st.session_state.loaded_run_notice = ""

    tabs = st.tabs(["Project", "Run", "Explore", "Report", "Advanced"])
    with tabs[0]:
        render_project_page()
    with tabs[1]:
        render_run_page()
    with tabs[2]:
        render_explore_page()
    with tabs[3]:
        render_report_page()
    with tabs[4]:
        render_provenance_page()
    st.markdown(
        (
            f"<footer class='ss-footer'><span>{PROJECT_SIGNATURE}</span>"
            "<span>SpatialScope Agent · reproducible spatial transcriptomics workspace</span>"
            f"<span>{' '.join(ACKNOWLEDGEMENTS[:2])}</span></footer>"
        ),
        unsafe_allow_html=True,
    )
