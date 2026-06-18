from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from spatialscope.agent.llm import llm_config_status, smoke_test_llm
from spatialscope.llm.gateway import LLMGateway
from spatialscope.tools.registry import tool_contract_summary
from spatialscope.utils.agent_audit import build_agent_audit, load_agent_audit
from spatialscope.utils.artifact_audit import audit_artifacts
from spatialscope.utils.dataset_card import build_dataset_card
from spatialscope.utils.run_index import discover_runs

from .helpers import read_table_preview, safe_json_download_payload


PROJECT_SIGNATURE = "seu-yolo / 东南大学计算生物学"
ACKNOWLEDGEMENTS = [
    "We gratefully acknowledge Professor Peng Xie from the School of Biological Science and Medical Engineering, Southeast University.",
    "We also thank Teaching Assistant Binyu Gao for guidance and support throughout the course project.",
    "This agent was built as an open, reproducible spatial transcriptomics analysis system.",
]


def chip(label: str, tone: str = "neutral") -> str:
    return f'<span class="ss-pill ss-{tone}">{html.escape(str(label))}</span>'


def atlas_svg() -> str:
    return """
    <svg viewBox="0 0 220 178" role="img" aria-label="Spatial transcriptomics atlas illustration">
      <defs>
        <linearGradient id="ssTissue" x1="38" y1="30" x2="188" y2="148" gradientUnits="userSpaceOnUse">
          <stop offset="0" stop-color="#d9efed"/>
          <stop offset="0.52" stop-color="#eee7f4"/>
          <stop offset="1" stop-color="#f7ead3"/>
        </linearGradient>
        <radialGradient id="ssGlow" cx="50%" cy="42%" r="70%">
          <stop offset="0" stop-color="#ffffff" stop-opacity="0.9"/>
          <stop offset="1" stop-color="#ffffff" stop-opacity="0.18"/>
        </radialGradient>
      </defs>
      <rect x="8" y="8" width="204" height="162" rx="14" fill="#fff" stroke="#d8e0e7"/>
      <path d="M34 18V160M66 18V160M98 18V160M130 18V160M162 18V160M194 18V160M18 38H202M18 70H202M18 102H202M18 134H202"
        stroke="rgba(102,115,127,.14)" stroke-width="1"/>
      <path fill="url(#ssTissue)" stroke="rgba(23,32,38,.16)" stroke-width="1.1"
        d="M43 118C29 92 38 58 64 42C89 26 119 33 139 49C160 66 190 72 194 98C199 128 171 150 139 148C106 146 62 153 43 118Z"/>
      <path fill="url(#ssGlow)"
        d="M55 112C46 90 53 62 74 50C98 36 124 45 143 60C160 73 183 80 184 100C185 121 163 134 137 133C106 132 67 138 55 112Z"/>
      <path d="M48 120C38 96 45 64 69 47C94 30 124 38 146 55C166 71 188 80 190 101C193 126 166 143 138 142C104 141 64 148 48 120Z"
        fill="none" stroke="rgba(23,32,38,.22)" stroke-dasharray="4 5" stroke-linecap="round"/>
      <path d="M58 105C75 82 92 96 108 69C123 45 143 67 161 57C176 49 184 66 183 84"
        fill="none" stroke="rgba(15,118,110,.72)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M69 123C87 111 99 124 119 111C139 99 151 113 170 98"
        fill="none" stroke="rgba(15,118,110,.38)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      <g fill="#fff" stroke-width="2.4">
        <circle cx="58" cy="105" r="5.1" stroke="#0f766e"/>
        <circle cx="108" cy="69" r="5.3" stroke="#6f4e8f"/>
        <circle cx="161" cy="57" r="4.8" stroke="#c75f4a"/>
        <circle cx="183" cy="84" r="4.4" stroke="#b7791f"/>
        <circle cx="69" cy="123" r="4.5" stroke="#0f766e" opacity=".62"/>
        <circle cx="119" cy="111" r="4.8" stroke="#c75f4a" opacity=".62"/>
        <circle cx="170" cy="98" r="4.5" stroke="#6f4e8f" opacity=".62"/>
      </g>
      <text x="24" y="154" fill="#8a97a3" font-family="ui-monospace, Menlo, monospace" font-size="8" font-weight="700">SPOTS</text>
      <text x="154" y="154" fill="#8a97a3" font-family="ui-monospace, Menlo, monospace" font-size="8" font-weight="700">TRACE</text>
    </svg>
    """


def render_header(active: dict[str, Any] | None) -> None:
    run_id = str(active.get("run_id") or "暂无运行") if active else "暂无运行"
    mode = str(active.get("mode") or "pending") if active else "pending"
    source = str(active.get("plan_source") or "waiting") if active else "waiting"
    llm = "LLM enabled" if active and active.get("llm_enabled") else "rule fallback"
    health_tone = "fail" if active and active.get("errors") else "warn" if active and active.get("warnings") else "success" if active and active.get("report_path") else "neutral"
    health = "完成" if active and active.get("report_path") else "准备中"
    st.markdown(
        f"""
        <section class="ss-hero">
          <div>
            <div class="ss-kicker">SpatialScope Agent</div>
            <div class="ss-title">空间转录组分析工作台</div>
            <div class="ss-subtitle">
              一个真正可审阅的 Agent：自然语言理解、可编辑计划、LangGraph checkpoint、工具执行、修复诊断、证据边界解释和可复现报告。
              当前运行 <span class="ss-run-path">{html.escape(run_id)}</span>
            </div>
            <div>
              {chip("mode: " + mode, "info")}
              {chip("plan: " + source, "neutral")}
              {chip(llm, "success" if active and active.get("llm_enabled") else "warn")}
              {chip(health, health_tone)}
            </div>
            <div class="ss-signature">{html.escape(PROJECT_SIGNATURE)}</div>
          </div>
          <div class="ss-atlas">{atlas_svg()}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_acknowledgements() -> None:
    rows = "".join(f"<div class='ss-muted'>{html.escape(line)}</div>" for line in ACKNOWLEDGEMENTS)
    st.markdown(
        f"""
        <div class="ss-panel compact">
          <div class="ss-mini-label">Acknowledgements</div>
          <div class="ss-card-title">A small signature in the workspace</div>
          {rows}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _inline_items(items: list[Any], *, empty: str = "none") -> str:
    values = [str(item).strip() for item in items if str(item).strip()]
    if not values:
        return f"<span class='ss-muted'>{html.escape(empty)}</span>"
    return "".join(chip(value, "neutral") for value in values[:12])


def _list_block(label: str, items: list[Any]) -> str:
    values = [str(item).strip() for item in items if str(item).strip()]
    if not values:
        return ""
    rows = "".join(f"<li>{html.escape(value)}</li>" for value in values[:6])
    return f"<div class='ss-brief-list'><div class='ss-mini-label'>{html.escape(label)}</div><ul>{rows}</ul></div>"


def render_research_brief(state: dict[str, Any]) -> None:
    brief = state.get("research_brief") if isinstance(state.get("research_brief"), dict) else {}
    if not brief:
        st.info("还没有 Research Brief。")
        return
    question = str(brief.get("normalized_question") or state.get("user_query") or "")
    source = str(brief.get("source") or "unknown")
    confidence = brief.get("confidence", "NA")
    st.html(
        f"""
        <div class="ss-brief">
          <div>
            <div class="ss-mini-label">Agent understood</div>
            <div class="ss-brief-question">{html.escape(question)}</div>
            <div>{chip("source: " + source, "info" if source == "llm" else "warn")}{chip("confidence: " + html.escape(str(confidence)), "neutral")}</div>
          </div>
          <div class="ss-brief-lanes">
            <div><div class="ss-mini-label">Genes</div>{_inline_items(brief.get("requested_genes", []))}</div>
            <div><div class="ss-mini-label">Analyses</div>{_inline_items(brief.get("requested_analyses", []))}</div>
            <div><div class="ss-mini-label">Comparisons</div>{_inline_items(brief.get("requested_comparisons", []))}</div>
          </div>
          {_list_block("Assumptions", brief.get("dataset_assumptions", []))}
          {_list_block("Ambiguities", brief.get("ambiguities", []))}
          {_list_block("Unsupported", brief.get("unsupported_requests", []))}
        </div>
        """
    )


def render_workflow(state: dict[str, Any] | None) -> None:
    phases = [
        ("Sense", "理解请求与数据边界", [("parse_request", "Parse"), ("inspect_dataset", "Inspect")]),
        ("Plan", "生成并等待人工批准", [("plan_analysis", "Plan"), ("review_plan", "Review")]),
        ("Act", "执行工具、校验、修复", [("execute_tool", "Tools"), ("validate_result", "Validate"), ("repair_or_continue", "Repair")]),
        ("Tell", "证据解释与报告", [("interpret", "Interpret"), ("report", "Report")]),
    ]
    trace = state.get("execution_trace", []) if state else []
    status_by_node = {str(item.get("node")): str(item.get("status") or "success") for item in trace}
    if state and state.get("task_plan"):
        status_by_node.setdefault("parse_request", "success")
        status_by_node.setdefault("plan_analysis", "success")
    if state and state.get("final_answer"):
        status_by_node.setdefault("interpret", "success")
    if state and state.get("report_path"):
        status_by_node.setdefault("report", "success")
    trace_tool = {str(item.get("node")): str(item.get("tool") or "") for item in trace if item.get("node")}
    index = 1
    blocks: list[str] = []
    for title, subtitle, steps in phases:
        step_html = []
        for node, label in steps:
            status = status_by_node.get(node, "pending")
            step_html.append(
                f"<div class='ss-flow-step {html.escape(status)}'>"
                f"<span class='ss-flow-index'>{index:02d}</span>"
                "<span>"
                f"<span class='ss-flow-name'>{html.escape(label)}</span>"
                f"<span class='ss-flow-tool'>{html.escape(trace_tool.get(node, node))}</span>"
                "</span>"
                f"<span class='ss-flow-status'>{html.escape(status)}</span>"
                "</div>"
            )
            index += 1
        blocks.append(
            f"<div class='ss-flow-phase'>"
            f"<div class='ss-flow-title'>{html.escape(title)}</div>"
            f"<div class='ss-flow-subtitle'>{html.escape(subtitle)}</div>"
            f"{''.join(step_html)}"
            "</div>"
        )
    st.html(f"<div class='ss-flow'>{''.join(blocks)}</div>")


def render_evidence_metrics(state: dict[str, Any]) -> None:
    observations = state.get("observations", {})
    dataset = state.get("dataset_summary", {})
    metrics = [
        ("Figures", len(state.get("generated_figures", []))),
        ("Tables", len(state.get("generated_tables", []))),
        ("Trace", len(state.get("execution_trace", []))),
        ("Spatial", "yes" if dataset.get("has_spatial") else "no"),
        ("Resolved genes", len(observations.get("resolved_genes", []))),
        ("Repairs", len(state.get("repair_log", []))),
        ("Warnings", len(state.get("warnings", []))),
    ]
    cards = "".join(
        f"<div class='ss-evidence-card'><div class='ss-mini-label'>{html.escape(label)}</div><div class='ss-evidence-value'>{html.escape(str(value))}</div></div>"
        for label, value in metrics
    )
    st.html(f"<div class='ss-grid'>{cards}</div>")


def render_plan_cards(plan: list[dict[str, Any]]) -> None:
    if not plan:
        st.info("还没有生成分析方案。")
        return
    cards: list[str] = []
    for index, step in enumerate(plan, start=1):
        params = html.escape(json.dumps(step.get("params", {}), ensure_ascii=False))
        origins = html.escape(json.dumps(step.get("parameter_origins", {}), ensure_ascii=False))
        dependencies = ", ".join(map(str, step.get("dependencies", []) or [])) or "none"
        preconditions = ", ".join(map(str, step.get("preconditions", []) or [])) or "none"
        optional = chip("optional", "warn") if step.get("optional") else ""
        expected = ", ".join(map(str, step.get("expected_evidence", []) or []))
        cards.append(
            f"""
            <div class="ss-plan-card">
              <div class="ss-mini-label">Step {index:02d} {optional}</div>
              <div class="ss-plan-tool">{html.escape(str(step.get("tool")))}</div>
              <div class="ss-muted">{html.escape(str(step.get("rationale") or step.get("scientific_purpose") or ""))}</div>
              <div class="ss-plan-meta"><span>Params</span><code>{params}</code></div>
              <div class="ss-plan-meta"><span>Origins</span><code>{origins or "{}"}</code></div>
              <div class="ss-plan-meta"><span>Depends</span><em>{html.escape(dependencies)}</em></div>
              <div class="ss-plan-meta"><span>Checks</span><em>{html.escape(preconditions)}</em></div>
              <div class="ss-muted">Evidence: {html.escape(expected or "trace record")}</div>
            </div>
            """
        )
    st.html(f"<div class='ss-plan-grid'>{''.join(cards)}</div>")


def trace_dataframe(state: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Node": item.get("node"),
                "Tool": item.get("tool"),
                "Status": item.get("status"),
                "Seconds": item.get("duration_sec"),
                "Summary": item.get("summary"),
            }
            for item in state.get("execution_trace", [])
        ]
    )


def render_trace(state: dict[str, Any]) -> None:
    df = trace_dataframe(state)
    if df.empty:
        st.info("还没有 execution trace。")
        return
    st.dataframe(df, hide_index=True, width="stretch", height=min(460, 72 + len(df) * 38))


def render_figures(state: dict[str, Any]) -> None:
    figures = state.get("generated_figures", [])
    if not figures:
        st.info("尚未生成 figures。")
        return
    for i in range(0, len(figures), 2):
        cols = st.columns(2, gap="large")
        for col, fig in zip(cols, figures[i : i + 2]):
            with col:
                with st.container(border=True):
                    path = Path(str(fig.get("path") or ""))
                    st.markdown(f"<div class='ss-mini-label'>Figure</div><div class='ss-card-title'>{html.escape(str(fig.get('title') or path.name))}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='ss-muted'>{html.escape(str(fig.get('caption') or ''))}</div>", unsafe_allow_html=True)
                    if path.exists():
                        st.image(str(path), width="stretch")
                        st.download_button("下载 PNG", path.read_bytes(), file_name=path.name, width="stretch", key=f"png_{i}_{path.name}")
                    svg = Path(str(fig.get("svg_path") or ""))
                    if svg.exists():
                        st.download_button("下载 SVG", svg.read_bytes(), file_name=svg.name, width="stretch", key=f"svg_{i}_{svg.name}")


def render_tables(state: dict[str, Any]) -> None:
    tables = state.get("generated_tables", [])
    if not tables:
        st.info("尚未生成 tables。")
        return
    for table in tables:
        path = Path(str(table.get("path") or ""))
        with st.container(border=True):
            st.markdown(f"<div class='ss-mini-label'>Table</div><div class='ss-card-title'>{html.escape(str(table.get('title') or path.name))}</div>", unsafe_allow_html=True)
            st.markdown(f"<div class='ss-run-path'>{html.escape(str(path))}</div>", unsafe_allow_html=True)
            preview = read_table_preview(str(path))
            if preview is not None:
                st.dataframe(preview, hide_index=True, width="stretch", height=250)
            if path.exists():
                st.download_button("下载 CSV", path.read_bytes(), file_name=path.name, width="stretch", key=f"table_{path.name}")


def render_dataset_profile(state: dict[str, Any]) -> None:
    profile = state.get("dataset_profile") or state.get("dataset_summary", {}).get("dataset_profile") or {}
    summary = state.get("dataset_summary", {})
    cards = [
        ("Observations", summary.get("n_obs", profile.get("n_obs", "NA"))),
        ("Genes", summary.get("n_vars", profile.get("n_vars", "NA"))),
        ("Matrix", summary.get("matrix_state", profile.get("matrix_state", "unknown"))),
        ("Run depth", summary.get("recommended_run_depth", profile.get("recommended_run_depth", "quick"))),
        ("Clusters", len(profile.get("cluster_fields", []) or summary.get("cluster_columns", []))),
        ("Layers", len(profile.get("layers", []) or summary.get("layer_keys", []))),
    ]
    st.markdown("<div class='ss-section-title'>Dataset Profile</div>", unsafe_allow_html=True)
    st.html(
        "<div class='ss-grid'>"
        + "".join(f"<div class='ss-evidence-card'><div class='ss-mini-label'>{html.escape(label)}</div><div class='ss-evidence-value'>{html.escape(str(value))}</div></div>" for label, value in cards)
        + "</div>"
    )
    warnings = profile.get("scientific_warnings") or summary.get("scientific_warnings") or []
    if warnings:
        st.warning("\n".join(map(str, warnings)))
    with st.expander("Dataset profile JSON", expanded=False):
        st.json(profile or summary)


def render_llm_status(*, key_prefix: str = "llm") -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass
    status = llm_config_status()
    tone = "success" if status.get("enabled") else "warn"
    st.markdown(
        f"""
        <div class="ss-panel">
          <div class="ss-mini-label">LLM Control Center</div>
          <div class="ss-card-title">{html.escape(str(status.get("provider")))} · {html.escape(str(status.get("model")))}</div>
          <div>{chip("enabled" if status.get("enabled") else "fallback", tone)}{chip(str(status.get("fallback")), "neutral")}</div>
          <div class="ss-run-path">base_url={html.escape(str(status.get("base_url") or ""))}</div>
          <div class="ss-run-path">api_key={html.escape(str(status.get("api_key_preview") or ""))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("检查 LLM 连接", width="stretch", key=f"{key_prefix}_smoke"):
        with st.spinner("发送最小 JSON smoke prompt..."):
            result = smoke_test_llm()
        if result.get("status") == "success":
            st.success(f"LLM 连接成功，用时 {result.get('latency_sec')} 秒。")
        elif result.get("status") == "skipped":
            st.warning(result.get("summary"))
        else:
            st.error(result.get("summary"))


def agent_audit_for_state(state: dict[str, Any]) -> dict[str, Any]:
    audit = state.get("agent_audit")
    if isinstance(audit, dict) and audit:
        return audit
    run_dir = state.get("run_dir")
    if run_dir:
        persisted = load_agent_audit(str(run_dir))
        if persisted:
            return persisted
    return build_agent_audit(state)


def render_audits(state: dict[str, Any]) -> None:
    audit = agent_audit_for_state(state)
    st.markdown("<div class='ss-section-title'>Agent Audit</div>", unsafe_allow_html=True)
    cols = st.columns(4)
    cols[0].metric("Status", str(audit.get("overall_status", "unknown")).upper())
    cols[1].metric("Score", audit.get("score", "NA"))
    cols[2].metric("Checks", len(audit.get("checks", [])))
    cols[3].metric("Repairs", audit.get("repair_summary", {}).get("repair_records", 0))
    if audit.get("checks"):
        st.dataframe(pd.DataFrame(audit["checks"]), hide_index=True, width="stretch", height=340)

    run_dir = state.get("run_dir")
    if run_dir:
        artifact_audit = audit_artifacts(str(run_dir))
        st.markdown("<div class='ss-section-title'>Artifact Audit</div>", unsafe_allow_html=True)
        cols = st.columns(4)
        cols[0].metric("Complete", "yes" if artifact_audit.get("complete") else "check")
        cols[1].metric("Artifacts", artifact_audit.get("existing_count", 0))
        cols[2].metric("Missing", artifact_audit.get("missing_count", 0))
        cols[3].metric("Size", artifact_audit.get("total_size", "0 B"))


def render_report_assets(state: dict[str, Any]) -> None:
    run_dir = Path(str(state.get("run_dir") or ""))
    paths = [
        ("Report HTML", Path(str(state.get("report_path") or run_dir / "report.html"))),
        ("Run README", run_dir / "README.md"),
        ("Bundle ZIP", run_dir / "run_bundle.zip"),
        ("Metadata JSON", run_dir / "run_metadata.json"),
        ("Trace JSON", run_dir / "agent_trace.json"),
        ("Dataset Card", run_dir / "dataset_card.html"),
        ("Storyboard", run_dir / "storyboard.html"),
        ("RERUN.md", run_dir / "RERUN.md"),
    ]
    for label, path in paths:
        if path.exists():
            st.download_button(label, path.read_bytes(), file_name=path.name, width="stretch", key=f"download_{label}_{path.name}")


def render_contextual_copilot(state: dict[str, Any]) -> None:
    figures = state.get("generated_figures", [])
    if not figures:
        return
    labels = [str(fig.get("title") or Path(str(fig.get("path", ""))).name) for fig in figures]
    selected = st.selectbox("选择证据上下文", labels)
    figure = figures[labels.index(selected)]
    question = st.text_input("Ask the evidence copilot", value="Explain this view cautiously.")
    if st.button("生成证据边界解释", width="stretch"):
        context = {
            **figure,
            "selected_table_titles": [str(table.get("title") or table.get("path")) for table in state.get("generated_tables", [])[:4]],
            "warnings": list(map(str, state.get("warnings", [])[:6])),
        }
        answer = LLMGateway.from_env().answer_contextual_question(context=context, question=question)
        st.markdown(f"<div class='ss-story'>{html.escape(answer).replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)


def render_run_library(outdir: str) -> None:
    runs = discover_runs(outdir, limit=8)
    if not runs:
        st.caption("暂无历史运行。完成一次分析后，这里会出现 report、trace 和 manifest。")
        return
    latest = runs[0]
    st.html(
        "<div class='ss-grid'>"
        + "".join(
            [
                f"<div class='ss-evidence-card'><div class='ss-mini-label'>最近运行</div><div class='ss-evidence-value'>{html.escape(str(latest.get('run_id', ''))[:18])}</div></div>",
                f"<div class='ss-evidence-card'><div class='ss-mini-label'>历史数量</div><div class='ss-evidence-value'>{len(runs)}</div></div>",
                f"<div class='ss-evidence-card'><div class='ss-mini-label'>Figures</div><div class='ss-evidence-value'>{html.escape(str(latest.get('figures', 0)))}</div></div>",
                f"<div class='ss-evidence-card'><div class='ss-mini-label'>Tables</div><div class='ss-evidence-value'>{html.escape(str(latest.get('tables', 0)))}</div></div>",
            ]
        )
        + "</div>"
    )
    rows = [
        {
            "Run": item.get("run_id"),
            "Mode": item.get("mode"),
            "Figures": item.get("figures"),
            "Tables": item.get("tables"),
            "Trace": item.get("trace_steps"),
            "Updated": datetime.fromtimestamp(float(item.get("modified_time") or 0)).strftime("%Y-%m-%d %H:%M"),
        }
        for item in runs
    ]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=min(330, 70 + len(rows) * 38))
    options = [str(item.get("run_id")) for item in runs]
    run_by_id = {str(item.get("run_id")): item for item in runs}
    return {"options": options, "run_by_id": run_by_id}


def render_tool_registry() -> None:
    st.dataframe(pd.DataFrame(tool_contract_summary()), hide_index=True, width="stretch", height=430)


def render_public_state_json(state: dict[str, Any]) -> None:
    payload = safe_json_download_payload(state)
    st.download_button("下载 public state JSON", payload, file_name=f"{state.get('run_id', 'spatialscope')}_state_public.json", width="stretch")
    with st.expander("Public state preview", expanded=False):
        st.json(json.loads(payload))
