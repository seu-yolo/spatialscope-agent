from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from spatialscope.agent.graph import execute_agent_state, preview_agent_plan, run_agent
from spatialscope.agent.planner import validate_plan_steps
from spatialscope.tools.registry import tool_contract_summary


st.set_page_config(page_title="SpatialScope Agent", page_icon="S", layout="wide")

st.markdown(
    """
    <style>
      :root {
        --ss-ink: #172026;
        --ss-muted: #66737f;
        --ss-soft: #8a97a3;
        --ss-line: #d8e0e7;
        --ss-line-strong: #b9c5cf;
        --ss-surface: #f7f9fb;
        --ss-surface-2: #eef4f6;
        --ss-teal: #0f766e;
        --ss-teal-soft: #d9efed;
        --ss-plum: #6f4e8f;
        --ss-plum-soft: #eee7f4;
        --ss-amber: #b7791f;
        --ss-amber-soft: #f7ead3;
        --ss-rose: #b42318;
        --ss-rose-soft: #f9e3e0;
        --ss-coral: #c75f4a;
      }
      html, body, [data-testid="stAppViewContainer"] {
        background:
          linear-gradient(90deg, rgba(15, 118, 110, 0.03) 1px, transparent 1px),
          linear-gradient(0deg, rgba(111, 78, 143, 0.025) 1px, transparent 1px),
          #fbfcfd;
        background-size: 34px 34px;
      }
      .block-container { padding-top: 1.4rem; max-width: 1380px; }
      h1, h2, h3 { letter-spacing: 0 !important; color: var(--ss-ink); }
      h1 { font-size: 2.25rem !important; line-height: 1.05 !important; }
      h2, h3 { margin-top: 1.1rem !important; }
      div[data-testid="stMetric"] {
        border: 1px solid var(--ss-line);
        border-radius: 8px;
        padding: 12px 14px;
        background: rgba(255, 255, 255, 0.92);
        box-shadow: 0 1px 0 rgba(23, 32, 38, 0.03);
      }
      div[data-testid="stMetric"] label { color: var(--ss-muted) !important; }
      div[data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: var(--ss-ink);
        font-weight: 720;
      }
      .ss-panel {
        border: 1px solid var(--ss-line);
        border-radius: 8px;
        padding: 16px;
        background: rgba(255, 255, 255, 0.94);
        margin-bottom: 14px;
      }
      .ss-muted { color: var(--ss-muted); font-size: 0.92rem; }
      .ss-pill {
        border-radius: 999px;
        border: 1px solid transparent;
        display: inline-block;
        font-size: 0.78rem;
        font-weight: 650;
        letter-spacing: 0;
        padding: 3px 9px;
        margin-right: 5px;
      }
      .ss-success { background: var(--ss-teal-soft); color: #075a54; border-color: #afd8d4; }
      .ss-warn { background: var(--ss-amber-soft); color: #83540d; border-color: #e3c898; }
      .ss-fail { background: var(--ss-rose-soft); color: #8c1d14; border-color: #edb7af; }
      .ss-info { background: var(--ss-plum-soft); color: #573975; border-color: #d6c5e3; }
      .ss-neutral { background: #edf1f4; color: #47545f; border-color: #d4dde4; }
      .ss-hero {
        border: 1px solid var(--ss-line);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.96);
        padding: 18px 18px 16px;
        margin-bottom: 16px;
        display: grid;
        grid-template-columns: minmax(0, 1fr) 188px;
        gap: 18px;
        align-items: center;
      }
      .ss-kicker {
        color: var(--ss-teal);
        font-size: 0.78rem;
        font-weight: 760;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 5px;
      }
      .ss-title {
        color: var(--ss-ink);
        font-size: 2.2rem;
        font-weight: 760;
        letter-spacing: 0;
        line-height: 1.08;
      }
      .ss-subtitle {
        color: var(--ss-muted);
        margin-top: 6px;
        max-width: 760px;
      }
      .ss-status-row { margin-top: 12px; }
      .ss-glyph {
        border-left: 1px solid var(--ss-line);
        padding-left: 18px;
        display: grid;
        grid-template-columns: repeat(7, 16px);
        grid-auto-rows: 16px;
        gap: 6px;
        justify-content: end;
      }
      .ss-dot {
        width: 9px;
        height: 9px;
        border-radius: 999px;
        background: var(--ss-line-strong);
        align-self: center;
        justify-self: center;
      }
      .ss-dot.a { background: var(--ss-teal); }
      .ss-dot.b { background: var(--ss-plum); }
      .ss-dot.c { background: var(--ss-coral); }
      .ss-dot.d { background: var(--ss-amber); }
      .ss-section-title {
        border-bottom: 1px solid var(--ss-line);
        color: var(--ss-ink);
        font-weight: 760;
        margin: 10px 0 14px;
        padding-bottom: 8px;
      }
      .ss-mini-label {
        color: var(--ss-soft);
        font-size: 0.76rem;
        font-weight: 680;
        letter-spacing: 0.04em;
        text-transform: uppercase;
      }
      .ss-card-title {
        color: var(--ss-ink);
        font-size: 1.02rem;
        font-weight: 740;
        margin: 2px 0 4px;
      }
      .ss-figure-note {
        color: var(--ss-muted);
        font-size: 0.88rem;
        line-height: 1.42;
        margin-bottom: 10px;
      }
      .ss-run-path {
        color: var(--ss-muted);
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 0.82rem;
        overflow-wrap: anywhere;
      }
      .ss-download-card {
        border: 1px solid var(--ss-line);
        border-radius: 8px;
        padding: 12px;
        background: #fff;
        min-height: 88px;
      }
      .ss-quiet-rule {
        height: 1px;
        background: var(--ss-line);
        margin: 12px 0 16px;
      }
      .stTabs [data-baseweb="tab-list"] { gap: 6px; }
      .stTabs [data-baseweb="tab"] {
        border: 1px solid var(--ss-line);
        border-radius: 8px 8px 0 0;
        padding: 8px 14px;
        background: rgba(255, 255, 255, 0.78);
      }
      .stTabs [aria-selected="true"] {
        background: #fff;
        border-bottom-color: #fff;
        color: var(--ss-teal);
      }
      button[kind="primary"] {
        border-radius: 8px !important;
      }
      @media (max-width: 760px) {
        .ss-hero { grid-template-columns: 1fr; }
        .ss-glyph { display: none; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def _init_state() -> None:
    defaults = {
        "draft_state": None,
        "run_state": None,
        "plan_text": "",
        "last_plan_error": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _save_upload(uploaded: Any) -> str | None:
    if uploaded is None:
        return None
    upload_dir = Path("outputs/tmp/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved = upload_dir / uploaded.name
    saved.write_bytes(uploaded.getbuffer())
    return str(saved)


def _plan_to_text(plan: list[dict[str, Any]]) -> str:
    return json.dumps(plan, ensure_ascii=False, indent=2)


def _load_plan_from_text(text: str) -> list[dict[str, Any]]:
    payload = json.loads(text)
    if isinstance(payload, dict) and "steps" in payload:
        payload = payload["steps"]
    if not isinstance(payload, list):
        raise ValueError("Plan JSON must be a list of steps or an object with a `steps` field.")
    return validate_plan_steps(payload)


def _trace_dataframe(state: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for item in state.get("execution_trace", []):
        rows.append(
            {
                "node": item.get("node"),
                "tool": item.get("tool"),
                "status": item.get("status"),
                "duration_sec": item.get("duration_sec"),
                "summary": item.get("summary"),
            }
        )
    return pd.DataFrame(rows)


def _status_counts(state: dict[str, Any]) -> dict[str, int]:
    counts = {"success": 0, "skipped": 0, "failed": 0, "repaired": 0}
    for item in state.get("execution_trace", []):
        status = str(item.get("status", ""))
        if status in counts:
            counts[status] += 1
    return counts


def _render_status_strip(state: dict[str, Any]) -> None:
    counts = _status_counts(state)
    chips = "".join(
        [
            _chip(f"{counts['success']} success", "success"),
            _chip(f"{counts['skipped']} skipped", "warn" if counts["skipped"] else "neutral"),
            _chip(f"{counts['failed']} failed", "fail" if counts["failed"] else "neutral"),
            _chip(f"{counts['repaired']} repaired", "warn" if counts["repaired"] else "neutral"),
        ]
    )
    st.markdown(f'<div class="ss-status-row">{chips}</div>', unsafe_allow_html=True)


def _read_table_preview(path: str | None) -> pd.DataFrame | None:
    if not path:
        return None
    table_path = Path(path)
    if not table_path.exists() or table_path.suffix.lower() != ".csv":
        return None
    try:
        return pd.read_csv(table_path).head(8)
    except Exception:
        return None


def _active_state() -> dict[str, Any] | None:
    return st.session_state.run_state or st.session_state.draft_state


def _chip(label: str, tone: str = "neutral") -> str:
    return f'<span class="ss-pill ss-{tone}">{label}</span>'


def _run_tone(state: dict[str, Any] | None) -> str:
    if not state:
        return "neutral"
    if state.get("errors"):
        return "fail"
    if state.get("warnings"):
        return "warn"
    if state.get("run_state") or state.get("generated_figures"):
        return "success"
    return "info"


def _glyph_html() -> str:
    classes = [
        "a",
        "",
        "",
        "b",
        "",
        "d",
        "",
        "",
        "a",
        "",
        "",
        "c",
        "",
        "",
        "d",
        "",
        "b",
        "",
        "",
        "a",
        "",
        "",
        "c",
        "",
        "d",
        "",
        "",
        "b",
        "",
        "",
        "a",
        "",
        "c",
        "",
        "",
    ]
    dots = "".join(f'<span class="ss-dot {klass}"></span>' for klass in classes)
    return f'<div class="ss-glyph" aria-hidden="true">{dots}</div>'


def _render_header(active: dict[str, Any] | None) -> None:
    run_label = str(active.get("run_id")) if active else "no active run"
    mode_label = str(active.get("mode")) if active else "mode not set"
    plan_label = str(active.get("plan_source")) if active else "plan pending"
    llm_tone = "success" if active and active.get("llm_enabled") else "neutral"
    llm_label = "GLM active" if active and active.get("llm_enabled") else "LLM fallback"
    health_label = "ready"
    health_tone = _run_tone(active)
    if active and active.get("errors"):
        health_label = f"{len(active.get('errors', []))} errors"
    elif active and active.get("warnings"):
        health_label = f"{len(active.get('warnings', []))} warnings"
    elif active and active.get("generated_figures"):
        health_label = "analysis complete"

    chips = "".join(
        [
            _chip(mode_label, "info"),
            _chip(plan_label, "neutral"),
            _chip(llm_label, llm_tone),
            _chip(health_label, health_tone),
        ]
    )
    st.markdown(
        f"""
        <section class="ss-hero">
          <div>
            <div class="ss-kicker">SpatialScope Agent</div>
            <div class="ss-title">Spatial transcriptomics, planned and traced.</div>
            <div class="ss-subtitle">Run <span class="ss-run-path">{run_label}</span></div>
            <div class="ss-status-row">{chips}</div>
          </div>
          {_glyph_html()}
        </section>
        """,
        unsafe_allow_html=True,
    )


_init_state()

active = _active_state()
_render_header(active)

start_tab, analyze_tab, explore_tab, report_tab = st.tabs(["Start", "Analyze", "Explore", "Report"])

with start_tab:
    left, right = st.columns([1.05, 0.95], gap="large")
    with left:
        st.markdown('<div class="ss-section-title">Input</div>', unsafe_allow_html=True)
        uploaded = st.file_uploader("Spatial AnnData file", type=["h5ad"])
        default_data = st.text_input("Local data path", value="data/demo_tiny.h5ad")
        query = st.text_area(
            "Task",
            value="Run standard spatial analysis with marker genes and GeneA GeneB panel.",
            height=118,
        )
        mode = st.segmented_control("Mode", ["quick", "standard", "advanced"], default="standard")
        outdir = st.text_input("Output directory", value="outputs/runs")

        upload_path = _save_upload(uploaded)
        data_path = upload_path or default_data

        c1, c2 = st.columns(2)
        if c1.button("Generate Plan", type="primary", width="stretch"):
            with st.spinner("Generating analysis plan..."):
                state = preview_agent_plan(data_path=data_path, query=query, mode=mode, outdir=outdir)
            st.session_state.draft_state = state
            st.session_state.run_state = None
            st.session_state.plan_text = _plan_to_text(state.get("approved_plan", []))
            st.session_state.last_plan_error = ""
            st.rerun()

        if c2.button("Run Directly", width="stretch"):
            with st.spinner("Running workflow..."):
                st.session_state.run_state = run_agent(data_path=data_path, query=query, mode=mode, outdir=outdir)
            st.session_state.draft_state = None
            st.session_state.plan_text = _plan_to_text(st.session_state.run_state.get("approved_plan", []))
            st.rerun()

    with right:
        st.markdown('<div class="ss-section-title">Tool Registry</div>', unsafe_allow_html=True)
        registry_df = pd.DataFrame(tool_contract_summary())
        st.dataframe(registry_df, hide_index=True, width="stretch", height=432)

with analyze_tab:
    state = st.session_state.draft_state
    if not state:
        st.info("Generate a plan from Start.")
    else:
        st.markdown('<div class="ss-section-title">Dataset Readiness</div>', unsafe_allow_html=True)
        status_cols = st.columns(4)
        summary = state.get("dataset_summary", {})
        status_cols[0].metric("Observations", summary.get("n_obs", "NA"))
        status_cols[1].metric("Genes", summary.get("n_vars", "NA"))
        status_cols[2].metric("Spatial", "yes" if summary.get("has_spatial") else "no")
        status_cols[3].metric("Steps", len(state.get("approved_plan", [])))

        st.markdown('<div class="ss-section-title">Approved Plan</div>', unsafe_allow_html=True)
        st.caption(state.get("plan_rationale") or "Plan rationale unavailable.")
        st.session_state.plan_text = st.text_area(
            "Plan JSON",
            value=st.session_state.plan_text or _plan_to_text(state.get("approved_plan", [])),
            height=360,
        )

        b1, b2 = st.columns([1, 1])
        if b1.button("Validate Plan", width="stretch"):
            try:
                plan = _load_plan_from_text(st.session_state.plan_text)
                st.session_state.plan_text = _plan_to_text(plan)
                st.session_state.last_plan_error = ""
                st.success("Plan is valid.")
            except Exception as exc:  # noqa: BLE001
                st.session_state.last_plan_error = str(exc)

        if b2.button("Run Approved Plan", type="primary", width="stretch"):
            try:
                plan = _load_plan_from_text(st.session_state.plan_text)
                with st.spinner("Executing approved plan..."):
                    st.session_state.run_state = execute_agent_state(
                        state,
                        approved_plan=plan,
                        plan_source="user_edited",
                    )
                st.session_state.draft_state = None
                st.session_state.last_plan_error = ""
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.session_state.last_plan_error = str(exc)

        if st.session_state.last_plan_error:
            st.error(st.session_state.last_plan_error)

        st.markdown('<div class="ss-section-title">Dataset Summary</div>', unsafe_allow_html=True)
        st.json(summary)

with explore_tab:
    state = st.session_state.run_state
    if not state:
        st.info("Run an approved plan first.")
    else:
        st.markdown('<div class="ss-section-title">Run Snapshot</div>', unsafe_allow_html=True)
        top = st.columns(5)
        top[0].metric("Figures", len(state.get("generated_figures", [])))
        top[1].metric("Tables", len(state.get("generated_tables", [])))
        top[2].metric("Trace Steps", len(state.get("execution_trace", [])))
        top[3].metric("Warnings", len(state.get("warnings", [])))
        top[4].metric("Errors", len(state.get("errors", [])))
        _render_status_strip(state)
        st.markdown(f'<div class="ss-run-path">{state.get("run_dir")}</div>', unsafe_allow_html=True)

        st.markdown('<div class="ss-section-title">Execution Trace</div>', unsafe_allow_html=True)
        trace_df = _trace_dataframe(state)
        st.dataframe(
            trace_df,
            hide_index=True,
            width="stretch",
            column_config={
                "node": st.column_config.TextColumn("Node", width="small"),
                "tool": st.column_config.TextColumn("Tool", width="medium"),
                "status": st.column_config.TextColumn("Status", width="small"),
                "duration_sec": st.column_config.NumberColumn("Sec", format="%.3f", width="small"),
                "summary": st.column_config.TextColumn("Summary", width="large"),
            },
        )

        st.markdown('<div class="ss-section-title">Figure Gallery</div>', unsafe_allow_html=True)
        figures = state.get("generated_figures", [])
        if figures:
            lead = figures[0]
            lead_path = lead.get("path")
            with st.container(border=True):
                st.markdown('<div class="ss-mini-label">Primary figure</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="ss-card-title">{lead.get("title", Path(str(lead_path)).name)}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="ss-figure-note">{lead.get("caption", "")}</div>', unsafe_allow_html=True)
                if lead_path and Path(lead_path).exists():
                    st.image(lead_path, width="stretch")

            remaining = figures[1:]
            for i in range(0, len(remaining), 2):
                cols = st.columns(2, gap="large")
                for col, fig in zip(cols, remaining[i : i + 2]):
                    with col:
                        with st.container(border=True):
                            path = fig.get("path")
                            st.markdown('<div class="ss-mini-label">Figure</div>', unsafe_allow_html=True)
                            st.markdown(
                                f'<div class="ss-card-title">{fig.get("title", Path(str(path)).name)}</div>',
                                unsafe_allow_html=True,
                            )
                            st.markdown(f'<div class="ss-figure-note">{fig.get("caption", "")}</div>', unsafe_allow_html=True)
                            if path and Path(path).exists():
                                st.image(path, width="stretch")
                            else:
                                st.caption("Figure file is not available.")
        else:
            st.info("No figures generated.")

        st.markdown('<div class="ss-section-title">Tables</div>', unsafe_allow_html=True)
        tables = state.get("generated_tables", [])
        if tables:
            for i in range(0, len(tables), 2):
                cols = st.columns(2, gap="large")
                for col, table in zip(cols, tables[i : i + 2]):
                    with col:
                        with st.container(border=True):
                            path = table.get("path")
                            st.markdown('<div class="ss-mini-label">Table</div>', unsafe_allow_html=True)
                            st.markdown(f'<div class="ss-card-title">{table.get("title", Path(str(path)).name)}</div>', unsafe_allow_html=True)
                            st.markdown(f'<div class="ss-run-path">{path}</div>', unsafe_allow_html=True)
                            preview = _read_table_preview(path)
                            if preview is not None:
                                st.dataframe(preview, hide_index=True, width="stretch", height=260)
                            else:
                                st.caption("Preview unavailable.")
        else:
            st.info("No tables generated.")

with report_tab:
    state = st.session_state.run_state
    if not state:
        st.info("Run an approved plan first.")
    else:
        st.markdown('<div class="ss-section-title">Interpretation</div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown('<div class="ss-mini-label">Agent summary</div>', unsafe_allow_html=True)
            st.write(state.get("final_answer"))

        if state.get("warnings"):
            st.warning("\n".join(map(str, state.get("warnings", []))))
        if state.get("errors"):
            st.error("\n".join(map(str, state.get("errors", []))))

        report_path = state.get("report_path")
        trace_path = Path(str(state.get("run_dir"))) / "agent_trace.json"
        metadata_path = Path(str(state.get("run_dir"))) / "run_metadata.json"
        param_path = Path(str(state.get("run_dir"))) / "parameters.yaml"

        st.markdown('<div class="ss-section-title">Reproducibility Bundle</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        if report_path and Path(str(report_path)).exists():
            with c1:
                with st.container(border=True):
                    st.markdown('<div class="ss-mini-label">Narrative</div>', unsafe_allow_html=True)
                    st.markdown('<div class="ss-card-title">Report HTML</div>', unsafe_allow_html=True)
                    st.download_button(
                        "Download",
                        Path(str(report_path)).read_bytes(),
                        file_name="spatialscope_report.html",
                        width="stretch",
                    )
        if trace_path.exists():
            with c2:
                with st.container(border=True):
                    st.markdown('<div class="ss-mini-label">Provenance</div>', unsafe_allow_html=True)
                    st.markdown('<div class="ss-card-title">Trace JSON</div>', unsafe_allow_html=True)
                    st.download_button("Download", trace_path.read_bytes(), file_name="agent_trace.json", width="stretch")
        if metadata_path.exists():
            with c3:
                with st.container(border=True):
                    st.markdown('<div class="ss-mini-label">Metadata</div>', unsafe_allow_html=True)
                    st.markdown('<div class="ss-card-title">Run JSON</div>', unsafe_allow_html=True)
                    st.download_button("Download", metadata_path.read_bytes(), file_name="run_metadata.json", width="stretch")
        if param_path.exists():
            with c4:
                with st.container(border=True):
                    st.markdown('<div class="ss-mini-label">Parameters</div>', unsafe_allow_html=True)
                    st.markdown('<div class="ss-card-title">YAML</div>', unsafe_allow_html=True)
                    st.download_button("Download", param_path.read_bytes(), file_name="parameters.yaml", width="stretch")

        st.markdown('<div class="ss-quiet-rule"></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="ss-run-path">{state.get("run_dir")}</div>', unsafe_allow_html=True)
