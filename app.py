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
        --ss-ink: #16202a;
        --ss-muted: #607080;
        --ss-line: #d9e2ea;
        --ss-surface: #f7f9fb;
        --ss-teal: #0f766e;
        --ss-plum: #704a8f;
        --ss-amber: #b7791f;
        --ss-rose: #b42318;
      }
      .block-container { padding-top: 2rem; max-width: 1320px; }
      h1, h2, h3 { letter-spacing: 0 !important; color: var(--ss-ink); }
      div[data-testid="stMetric"] {
        border: 1px solid var(--ss-line);
        border-radius: 8px;
        padding: 10px 12px;
        background: #ffffff;
      }
      .ss-panel {
        border: 1px solid var(--ss-line);
        border-radius: 8px;
        padding: 16px;
        background: #ffffff;
        margin-bottom: 14px;
      }
      .ss-muted { color: var(--ss-muted); font-size: 0.92rem; }
      .ss-pill {
        border-radius: 999px;
        color: #fff;
        display: inline-block;
        font-size: 0.78rem;
        padding: 2px 9px;
        margin-right: 5px;
      }
      .ss-success { background: var(--ss-teal); }
      .ss-warn { background: var(--ss-amber); }
      .ss-fail { background: var(--ss-rose); }
      .ss-info { background: var(--ss-plum); }
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


def _active_state() -> dict[str, Any] | None:
    return st.session_state.run_state or st.session_state.draft_state


_init_state()

st.title("SpatialScope Agent")
st.caption("Open, traceable spatial transcriptomics analysis with LangGraph and DeepSeek.")

active = _active_state()
metric_cols = st.columns(4)
metric_cols[0].metric("Run", active.get("run_id") if active else "none")
metric_cols[1].metric("Mode", active.get("mode") if active else "not set")
metric_cols[2].metric("Plan", active.get("plan_source") if active else "not generated")
metric_cols[3].metric("LLM", "enabled" if active and active.get("llm_enabled") else "fallback")

start_tab, analyze_tab, explore_tab, report_tab = st.tabs(["Start", "Analyze", "Explore", "Report"])

with start_tab:
    left, right = st.columns([1.05, 0.95], gap="large")
    with left:
        st.subheader("Input")
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
        if c1.button("Generate Plan", type="primary", use_container_width=True):
            with st.spinner("Generating analysis plan..."):
                state = preview_agent_plan(data_path=data_path, query=query, mode=mode, outdir=outdir)
            st.session_state.draft_state = state
            st.session_state.run_state = None
            st.session_state.plan_text = _plan_to_text(state.get("approved_plan", []))
            st.session_state.last_plan_error = ""
            st.rerun()

        if c2.button("Run Directly", use_container_width=True):
            with st.spinner("Running workflow..."):
                st.session_state.run_state = run_agent(data_path=data_path, query=query, mode=mode, outdir=outdir)
            st.session_state.draft_state = None
            st.session_state.plan_text = _plan_to_text(st.session_state.run_state.get("approved_plan", []))
            st.rerun()

    with right:
        st.subheader("Tool Registry")
        registry_df = pd.DataFrame(tool_contract_summary())
        st.dataframe(registry_df, hide_index=True, use_container_width=True, height=432)

with analyze_tab:
    state = st.session_state.draft_state
    if not state:
        st.info("Generate a plan from Start.")
    else:
        status_cols = st.columns(4)
        summary = state.get("dataset_summary", {})
        status_cols[0].metric("Observations", summary.get("n_obs", "NA"))
        status_cols[1].metric("Genes", summary.get("n_vars", "NA"))
        status_cols[2].metric("Spatial", "yes" if summary.get("has_spatial") else "no")
        status_cols[3].metric("Steps", len(state.get("approved_plan", [])))

        st.subheader("Approved Plan")
        st.caption(state.get("plan_rationale") or "Plan rationale unavailable.")
        st.session_state.plan_text = st.text_area(
            "Plan JSON",
            value=st.session_state.plan_text or _plan_to_text(state.get("approved_plan", [])),
            height=360,
        )

        b1, b2 = st.columns([1, 1])
        if b1.button("Validate Plan", use_container_width=True):
            try:
                plan = _load_plan_from_text(st.session_state.plan_text)
                st.session_state.plan_text = _plan_to_text(plan)
                st.session_state.last_plan_error = ""
                st.success("Plan is valid.")
            except Exception as exc:  # noqa: BLE001
                st.session_state.last_plan_error = str(exc)

        if b2.button("Run Approved Plan", type="primary", use_container_width=True):
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

        st.subheader("Dataset Summary")
        st.json(summary)

with explore_tab:
    state = st.session_state.run_state
    if not state:
        st.info("Run an approved plan first.")
    else:
        top = st.columns(4)
        top[0].metric("Figures", len(state.get("generated_figures", [])))
        top[1].metric("Tables", len(state.get("generated_tables", [])))
        top[2].metric("Warnings", len(state.get("warnings", [])))
        top[3].metric("Errors", len(state.get("errors", [])))

        st.subheader("Execution Trace")
        trace_df = _trace_dataframe(state)
        st.dataframe(trace_df, hide_index=True, use_container_width=True)

        st.subheader("Figures")
        figures = state.get("generated_figures", [])
        if figures:
            for fig in figures:
                path = fig.get("path")
                st.markdown(f"**{fig.get('title', Path(str(path)).name)}**")
                if path and Path(path).exists():
                    st.image(path, caption=fig.get("caption"), use_container_width=True)
                else:
                    st.caption(fig.get("caption", ""))
        else:
            st.info("No figures generated.")

        st.subheader("Tables")
        table_rows = []
        for table in state.get("generated_tables", []):
            path = table.get("path")
            table_rows.append({"title": table.get("title"), "path": path})
        if table_rows:
            st.dataframe(pd.DataFrame(table_rows), hide_index=True, use_container_width=True)
        else:
            st.info("No tables generated.")

with report_tab:
    state = st.session_state.run_state
    if not state:
        st.info("Run an approved plan first.")
    else:
        st.subheader("Interpretation")
        st.write(state.get("final_answer"))

        if state.get("warnings"):
            st.warning("\n".join(map(str, state.get("warnings", []))))
        if state.get("errors"):
            st.error("\n".join(map(str, state.get("errors", []))))

        report_path = state.get("report_path")
        trace_path = Path(str(state.get("run_dir"))) / "agent_trace.json"
        metadata_path = Path(str(state.get("run_dir"))) / "run_metadata.json"
        param_path = Path(str(state.get("run_dir"))) / "parameters.yaml"

        c1, c2, c3, c4 = st.columns(4)
        if report_path and Path(str(report_path)).exists():
            c1.download_button(
                "Report HTML",
                Path(str(report_path)).read_bytes(),
                file_name="spatialscope_report.html",
                use_container_width=True,
            )
        if trace_path.exists():
            c2.download_button("Trace JSON", trace_path.read_bytes(), file_name="agent_trace.json", use_container_width=True)
        if metadata_path.exists():
            c3.download_button("Metadata JSON", metadata_path.read_bytes(), file_name="run_metadata.json", use_container_width=True)
        if param_path.exists():
            c4.download_button("Parameters YAML", param_path.read_bytes(), file_name="parameters.yaml", use_container_width=True)

        st.markdown(f"`{state.get('run_dir')}`")
