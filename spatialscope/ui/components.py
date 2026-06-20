from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from spatialscope.agent.llm import llm_config_status, smoke_test_llm
from spatialscope.domain.dataset_store import DEFAULT_DATASET_STORE
from spatialscope.domain.expression_lineage import infer_matrix_state
from spatialscope.domain.exploration_evidence import (
    expression_vector,
    resolve_gene,
    safe_expression_sources,
    summarize_cluster,
    summarize_gene,
    summarize_selection,
)
from spatialscope.llm.context import context_for_copilot
from spatialscope.llm.gateway import LLMGateway
from spatialscope.tools.registry import tool_contract_summary
from spatialscope.utils.agent_audit import build_agent_audit, load_agent_audit
from spatialscope.utils.artifact_audit import audit_artifacts
from spatialscope.utils.dataset_card import build_dataset_card
from spatialscope.utils.gene_matching import match_gene_name
from spatialscope.utils.run_index import discover_runs
from spatialscope.visualization.theme import CLUSTER_PALETTE, numeric_sort_key
from spatialscope.ui.actions import apply_ui_action, ensure_explore_state

from .helpers import read_table_preview, safe_json_download_payload


PROJECT_SIGNATURE = "seu-yolo / 东南大学计算生物学"
ACKNOWLEDGEMENTS = [
    "We gratefully acknowledge Professor Peng Xie from the School of Biological Science and Medical Engineering, Southeast University.",
    "We also thank Teaching Assistant Binyu Gao for guidance and support throughout the course project.",
    "This agent was built as an open, reproducible spatial transcriptomics analysis system.",
]

GENE_TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_.-]{0,20}\b")
QUESTION_STOPWORDS = {
    "cluster",
    "clusters",
    "mean",
    "average",
    "expression",
    "spatial",
    "umap",
    "gene",
    "genes",
    "highest",
    "global",
    "selected",
}


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
    if active:
        st.markdown(
            f"""
            <section class="ss-topbar">
              <div>
                <div class="ss-kicker">SpatialScope Agent</div>
                <div class="ss-topbar-title">证据驱动的空间转录组分析工作台</div>
              </div>
              <div class="ss-topbar-tags">
                {chip("run: " + run_id, "neutral")}
                {chip("mode: " + mode, "info")}
                {chip("plan: " + source, "neutral")}
                {chip(llm, "success" if active.get("llm_enabled") else "warn")}
                {chip(health, health_tone)}
              </div>
            </section>
            """,
            unsafe_allow_html=True,
        )
        return
    st.markdown(
        f"""
        <section class="ss-hero">
          <div>
            <div class="ss-kicker">SpatialScope Agent</div>
            <div class="ss-title">空间转录组分析工作台</div>
            <div class="ss-subtitle">
              自然语言问题进入工作流，数据检查先于计划生成；每一条观察都回到 figures、tables、trace 和 evidence IDs。
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
        ("Sense", "先读取数据，再理解问题", [("inspect_dataset", "Inspect"), ("parse_request", "Understand")]),
        ("Plan", "生成并等待人工批准", [("plan_analysis", "Plan"), ("review_plan", "Review")]),
        ("Act", "执行工具、校验、修复", [("execute_tool", "Tools"), ("validate_result", "Validate"), ("repair_or_continue", "Repair")]),
        ("Tell", "证据解释与报告", [("interpret", "Interpret"), ("report", "Report")]),
    ]
    trace = state.get("execution_trace", []) if state else []
    status_by_node = {str(item.get("node")): str(item.get("status") or "success") for item in trace}
    if state and state.get("task_plan"):
        status_by_node.setdefault("parse_request", "success")
        status_by_node.setdefault("plan_analysis", "success")
    if state and any(str(item.get("node")) == "execute_tool" for item in trace):
        status_by_node.setdefault("validate_result", "failed" if state.get("needs_repair") else "success")
    if state and state.get("report_path") and "repair_or_continue" not in status_by_node:
        status_by_node["repair_or_continue"] = "skipped"
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


def render_clarifications(state: dict[str, Any]) -> None:
    items = state.get("clarification_items", [])
    if not items:
        return
    st.markdown("<div class='ss-section-title'>Clarification & Repair</div>", unsafe_allow_html=True)
    for item in items[:5]:
        suggestions = item.get("suggestions", {})
        suggestion_text = json.dumps(suggestions, ensure_ascii=False) if suggestions else ""
        st.markdown(
            (
                "<div class='ss-story compact'>"
                f"<div class='ss-mini-label'>{html.escape(str(item.get('kind', 'clarification')))}</div>"
                f"<div class='ss-card-title'>{html.escape(str(item.get('message', 'Needs clarification')))}</div>"
                f"<p class='ss-run-path'>{html.escape(suggestion_text)}</p>"
                f"{chip(str(item.get('status', 'recorded')), 'warn')}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )


def render_plan_cards(plan: list[dict[str, Any]]) -> None:
    if not plan:
        st.info("还没有生成分析方案。")
        return
    rows: list[str] = []
    for index, step in enumerate(plan, start=1):
        dependencies = ", ".join(map(str, step.get("dependencies", []) or [])) or "none"
        optional = chip("optional", "warn") if step.get("optional") else ""
        expected = ", ".join(map(str, step.get("expected_evidence", []) or []))
        purpose = str(step.get("rationale") or step.get("scientific_purpose") or "")
        rows.append(
            f"""
            <div class="ss-stepper-row">
              <div class="ss-stepper-index">{index:02d}</div>
              <div>
                <div class="ss-plan-tool">{html.escape(str(step.get("tool")))} {optional}</div>
                <div class="ss-muted">{html.escape(purpose)}</div>
                <div class="ss-stepper-meta">
                  <span>依赖：{html.escape(dependencies)}</span>
                  <span>预期证据：{html.escape(expected or "trace record")}</span>
                </div>
              </div>
            </div>
            """
        )
    st.html(f"<div class='ss-stepper'>{''.join(rows)}</div>")


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


def _find_figure(state: dict[str, Any], *needles: str) -> dict[str, Any] | None:
    for fig in state.get("generated_figures", []):
        haystack = f"{fig.get('title', '')} {fig.get('path', '')}".lower()
        if all(needle.lower() in haystack for needle in needles):
            return fig
    for fig in state.get("generated_figures", []):
        haystack = f"{fig.get('title', '')} {fig.get('caption', '')} {fig.get('path', '')}".lower()
        if all(needle.lower() in haystack for needle in needles):
            return fig
    return None


def _load_explore_adata(state: dict[str, Any]) -> Any | None:
    ref = str(state.get("working_dataset_ref") or state.get("adata_path") or state.get("data_path") or "")
    if not ref:
        return None
    try:
        return DEFAULT_DATASET_STORE.load(ref)
    except Exception:
        return None


def _dense_vector(values: Any) -> np.ndarray:
    if hasattr(values, "toarray"):
        values = values.toarray()
    return np.ravel(np.asarray(values))


def _safe_expression_layers(adata: Any) -> list[str]:
    layers = getattr(adata, "layers", {})
    safe: list[str] = []
    if "spatialscope_interpretation" in layers:
        safe.append("spatialscope_interpretation")
    if "counts" in layers:
        safe.append("counts")
    if getattr(adata, "raw", None) is not None:
        safe.append("raw")
    try:
        state = infer_matrix_state(adata.X).state
        if state in {"count_like", "log_normalized"}:
            safe.append("X")
    except Exception:
        pass
    return list(dict.fromkeys(safe))


def _gene_vector(adata: Any, gene: str, layer: str) -> np.ndarray:
    if layer == "raw" and getattr(adata, "raw", None) is not None:
        return _dense_vector(adata.raw[:, gene].X)
    idx = list(map(str, adata.var_names)).index(gene)
    if layer != "X" and layer in getattr(adata, "layers", {}):
        return _dense_vector(adata.layers[layer][:, idx])
    return _dense_vector(adata.X[:, idx])


def _cluster_options(adata: Any) -> list[str]:
    options: list[str] = []
    for column in adata.obs.columns:
        values = adata.obs[column]
        unique = values.astype(str).nunique(dropna=True)
        if 1 < unique <= 40:
            options.append(str(column))
    preferred = [item for item in ["leiden", "cluster", "clusters", "demo_region", "embryo_zone"] if item in options]
    return list(dict.fromkeys([*preferred, *options]))[:12]


def _gene_choices(state: dict[str, Any], adata: Any) -> list[str]:
    var_names = list(map(str, adata.var_names))
    requested = []
    observations = state.get("observations", {})
    for key in ["resolved_genes", "requested_genes"]:
        requested.extend(list(map(str, observations.get(key, []) or [])))
    brief = state.get("research_brief") if isinstance(state.get("research_brief"), dict) else {}
    requested.extend(list(map(str, brief.get("requested_genes", []) or [])))
    resolved: list[str] = []
    for gene in requested:
        match = match_gene_name(gene, var_names)
        if match.get("match"):
            resolved.append(str(match["match"]))
    if not resolved:
        resolved = var_names[: min(12, len(var_names))]
    return list(dict.fromkeys(resolved))


def _palette_for(adata: Any, key: str, categories: list[str]) -> dict[str, str]:
    stored = getattr(adata, "uns", {}).get("spatialscope_cluster_palette", {}).get(key, {})
    if isinstance(stored, dict) and all(cat in stored for cat in categories):
        return {cat: str(stored[cat]) for cat in categories}
    return {cat: CLUSTER_PALETTE[i % len(CLUSTER_PALETTE)] for i, cat in enumerate(categories)}


def _cluster_scatter(
    *,
    coords: np.ndarray,
    labels: pd.Series,
    title: str,
    palette: dict[str, str],
    point_size: int,
    obs_ids: list[str],
    selected_cluster: str = "",
    selected_obs_ids: list[str] | None = None,
    spatial: bool = False,
) -> go.Figure:
    fig = go.Figure()
    categories = sorted(labels.astype(str).unique(), key=numeric_sort_key)
    selected_obs = set(map(str, selected_obs_ids or []))
    for category in categories:
        mask = np.asarray(labels.astype(str) == category)
        trace_obs = np.asarray(obs_ids)[mask]
        selectedpoints = [i for i, obs in enumerate(trace_obs) if str(obs) in selected_obs]
        focus_active = bool(selected_cluster)
        opacity = 0.92 if not focus_active or str(category) == str(selected_cluster) else 0.14
        fig.add_trace(
            go.Scattergl(
                x=coords[mask, 0],
                y=coords[mask, 1],
                mode="markers",
                name=str(category),
                customdata=trace_obs,
                selectedpoints=selectedpoints if selectedpoints else None,
                selected={"marker": {"opacity": 1.0, "size": point_size + 3}},
                unselected={"marker": {"opacity": opacity}},
                marker={"size": point_size, "color": palette[str(category)], "opacity": opacity, "line": {"width": 0}},
                hovertemplate="obs=%{customdata}<br>group=%{fullData.name}<br>x=%{x:.2f}<br>y=%{y:.2f}<extra></extra>",
            )
        )
    fig.update_layout(
        title={"text": title, "x": 0.02, "xanchor": "left"},
        margin={"l": 8, "r": 8, "t": 46, "b": 8},
        height=470,
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend={"orientation": "h", "y": -0.08, "x": 0},
        font={"family": "Inter, PingFang SC, sans-serif", "size": 13, "color": "#172026"},
    )
    fig.update_xaxes(showgrid=False, zeroline=False, showticklabels=not spatial)
    fig.update_yaxes(showgrid=False, zeroline=False, showticklabels=not spatial)
    if spatial:
        fig.update_yaxes(scaleanchor="x")
    return fig


def _expression_scatter(
    *,
    coords: np.ndarray,
    values: np.ndarray,
    title: str,
    point_size: int,
    obs_ids: list[str],
    selected_obs_ids: list[str] | None = None,
    clip_percentiles: tuple[float, float] = (1.0, 99.0),
    spatial: bool = False,
) -> go.Figure:
    finite = values[np.isfinite(values)]
    if len(finite):
        lo, hi = np.percentile(finite, clip_percentiles)
        values = np.clip(values, lo, hi)
    selected_obs = set(map(str, selected_obs_ids or []))
    selectedpoints = [i for i, obs in enumerate(obs_ids) if str(obs) in selected_obs]
    fig = go.Figure(
        go.Scattergl(
            x=coords[:, 0],
            y=coords[:, 1],
            mode="markers",
            customdata=obs_ids,
            selectedpoints=selectedpoints if selectedpoints else None,
            selected={"marker": {"opacity": 1.0, "size": point_size + 3}},
            unselected={"marker": {"opacity": 0.9 if not selectedpoints else 0.16}},
            marker={
                "size": point_size,
                "color": values,
                "colorscale": [[0, "#f7faf9"], [0.35, "#dcefed"], [0.7, "#3d9a91"], [1, "#075a54"]],
                "showscale": True,
                "colorbar": {"title": "expr"},
                "opacity": 0.9,
                "line": {"width": 0},
            },
            hovertemplate="obs=%{customdata}<br>expr=%{marker.color:.3g}<br>x=%{x:.2f}<br>y=%{y:.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        title={"text": title, "x": 0.02, "xanchor": "left"},
        margin={"l": 8, "r": 8, "t": 46, "b": 8},
        height=470,
        paper_bgcolor="white",
        plot_bgcolor="white",
        font={"family": "Inter, PingFang SC, sans-serif", "size": 13, "color": "#172026"},
    )
    fig.update_xaxes(showgrid=False, zeroline=False, showticklabels=not spatial)
    fig.update_yaxes(showgrid=False, zeroline=False, showticklabels=not spatial)
    if spatial:
        fig.update_yaxes(scaleanchor="x")
    return fig


def _format_metric(value: Any) -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        if abs(value) < 1:
            return f"{value:.3f}"
        return f"{value:.2f}"
    return str(value)


def _plotly_selection_event(fig: go.Figure, *, key: str) -> Any:
    try:
        return st.plotly_chart(
            fig,
            use_container_width=True,
            key=key,
            on_select="rerun",
            selection_mode=("points", "box", "lasso"),
        )
    except TypeError:
        st.plotly_chart(fig, use_container_width=True, key=key)
        return None


def _selected_obs_from_event(event: Any) -> list[str]:
    if not event:
        return []
    payload = event
    if hasattr(payload, "selection"):
        payload = payload.selection
    if isinstance(payload, dict) and "selection" in payload:
        payload = payload.get("selection")
    points: Any = []
    if isinstance(payload, dict):
        points = payload.get("points") or []
    elif hasattr(payload, "points"):
        points = getattr(payload, "points")
    obs_ids: list[str] = []
    for point in points or []:
        custom = point.get("customdata") if isinstance(point, dict) else getattr(point, "customdata", None)
        if isinstance(custom, (list, tuple, np.ndarray)):
            custom = custom[0] if len(custom) else None
        if custom is not None and str(custom):
            obs_ids.append(str(custom))
    return list(dict.fromkeys(obs_ids))


def _runtime_gateway() -> LLMGateway:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass
    runtime = st.session_state.get("agent_runtime")
    gateway = getattr(runtime, "llm_gateway", None)
    status = llm_config_status()
    if isinstance(gateway, LLMGateway) and (gateway.client.enabled or not status.get("enabled")):
        return gateway
    gateway = LLMGateway.from_env()
    if runtime is not None:
        try:
            runtime.llm_gateway = gateway
        except Exception:
            pass
    return gateway


def _metric_strip_html(items: list[tuple[str, Any]]) -> str:
    cards = "".join(
        "<div class='ss-strip-item'>"
        f"<span>{html.escape(label)}</span>"
        f"<strong>{html.escape(_format_metric(value))}</strong>"
        "</div>"
        for label, value in items
    )
    return f"<div class='ss-evidence-strip'>{cards}</div>"


def _gene_metric_items(gene_pack: Any, selection_pack: Any | None) -> list[tuple[str, Any]]:
    metrics = getattr(gene_pack, "summary_metrics", {}) or {}
    global_stats = metrics.get("global") or {}
    top = (metrics.get("top_clusters_by_mean") or ["NA"])[0]
    by_cluster = metrics.get("by_cluster") or {}
    top_stats = by_cluster.get(str(top), {}) if top != "NA" else {}
    items: list[tuple[str, Any]] = [
        ("Gene mean", global_stats.get("mean")),
        ("Top cluster", top),
        ("Top mean", top_stats.get("mean")),
        ("Non-zero", global_stats.get("nonzero_fraction")),
    ]
    if selection_pack is not None:
        selection_metrics = getattr(selection_pack, "summary_metrics", {}) or {}
        items.extend(
            [
                ("Selected spots", selection_metrics.get("selected_count")),
                ("Selected/global", selection_metrics.get("selected_minus_global_mean")),
            ]
        )
    return items[:6]


def _cluster_metric_items(cluster_pack: Any | None, selection_pack: Any | None) -> list[tuple[str, Any]]:
    if cluster_pack is None:
        return [("Cluster", "all"), ("Selected spots", len(st.session_state.get("selected_obs_ids", [])))]
    metrics = getattr(cluster_pack, "summary_metrics", {}) or {}
    items: list[tuple[str, Any]] = [
        ("Cluster", metrics.get("cluster")),
        ("Cluster size", metrics.get("cluster_size")),
        ("Cluster fraction", metrics.get("cluster_fraction")),
        ("Selected in cluster", metrics.get("selected_count")),
    ]
    if selection_pack is not None:
        selection_metrics = getattr(selection_pack, "summary_metrics", {}) or {}
        items.append(("Selected spots", selection_metrics.get("selected_count")))
    return items[:6]


def _marker_excerpt(state: dict[str, Any], cluster: str) -> list[dict[str, Any]]:
    if not cluster:
        return []
    for table in state.get("generated_tables", []):
        title = str(table.get("title") or table.get("path") or "").lower()
        if "marker" not in title:
            continue
        preview = read_table_preview(str(table.get("path") or ""), n=80)
        if preview is None or preview.empty:
            continue
        columns = {str(column).lower(): column for column in preview.columns}
        cluster_col = columns.get("cluster") or columns.get("group") or columns.get("leiden")
        if cluster_col is not None:
            preview = preview[preview[cluster_col].astype(str) == str(cluster)]
        if preview.empty:
            continue
        return preview.head(5).to_dict(orient="records")
    return []


def _gene_mentioned_in_question(question: str, adata: Any) -> str:
    var_names = list(map(str, adata.var_names))
    for token in GENE_TOKEN_RE.findall(question):
        if token.lower() in QUESTION_STOPWORDS:
            continue
        match = match_gene_name(token, var_names)
        score = float(match.get("score") or 0)
        matched = str(match.get("match") or "")
        if matched and (matched.lower() == token.lower() or score >= 90):
            return matched
    return ""


def _local_region_obs_ids(coords: np.ndarray, obs_ids: list[str]) -> list[str]:
    if len(coords) == 0:
        return []
    x = coords[:, 0]
    y = coords[:, 1]
    x_cut = np.percentile(x, 38)
    y_low, y_high = np.percentile(y, [28, 72])
    mask = (x <= x_cut) & (y >= y_low) & (y <= y_high)
    selected = [obs for obs, keep in zip(obs_ids, mask) if bool(keep)]
    return selected[:180]


def _render_pack_summary(pack: Any) -> None:
    if pack is None:
        return
    metrics = getattr(pack, "summary_metrics", {}) or {}
    caveats = getattr(pack, "caveats", []) or []
    st.markdown(
        (
            "<div class='ss-evidence-note'>"
            f"<div class='ss-mini-label'>Evidence ID</div>"
            f"<div class='ss-run-path'>{html.escape(str(getattr(pack, 'evidence_id', '')))}</div>"
            f"<div class='ss-muted'>{html.escape('; '.join(map(str, caveats[:2])) or 'Evidence is generated from deterministic summaries.')}</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    top = metrics.get("top_clusters_by_mean")
    if top:
        st.caption(f"Top clusters by mean expression: {', '.join(map(str, top[:3]))}")


def render_linked_explore(state: dict[str, Any]) -> None:
    ensure_explore_state()
    pending_view = st.session_state.pop("pending_explore_view_mode", None)
    if pending_view:
        st.session_state.explore_view_mode = pending_view
    pending_gene = st.session_state.pop("pending_selected_gene", None)
    if pending_gene:
        st.session_state.selected_gene = pending_gene
    adata = _load_explore_adata(state)
    if adata is None:
        st.info("无法载入本次 run 的 working AnnData；请先完成一次运行。")
        return
    cluster_options = _cluster_options(adata)
    if "spatial" not in adata.obsm:
        st.warning("当前数据没有 `adata.obsm['spatial']`，Spatial view 无法渲染。")
        return
    if "X_umap" not in adata.obsm:
        st.warning("当前 run 还没有 UMAP 坐标；请运行包含 clustering 的分析方案。")
        return
    if not cluster_options:
        st.warning("没有找到可用于联动视图的 cluster/category 列。")
        return

    obs_ids = list(map(str, adata.obs_names))
    safe_sources = safe_expression_sources(adata)
    cluster_key = str(st.session_state.get("cluster_key") or cluster_options[0])
    if cluster_key not in cluster_options:
        cluster_key = cluster_options[0]
    labels = adata.obs[cluster_key].astype(str)
    categories = sorted(labels.unique(), key=numeric_sort_key)
    palette = _palette_for(adata, cluster_key, categories)
    spatial_coords = np.asarray(adata.obsm["spatial"])
    umap_coords = np.asarray(adata.obsm["X_umap"])

    genes = _gene_choices(state, adata)
    selected_gene = str(st.session_state.get("selected_gene") or (genes[0] if genes else "")).strip()
    if not selected_gene and genes:
        selected_gene = genes[0]
    resolved = resolve_gene(adata, selected_gene) if selected_gene else {"resolved_gene": ""}
    resolved_gene = str(resolved.get("resolved_gene") or "")
    if resolved_gene and resolved_gene not in genes:
        genes = [resolved_gene, *genes]
    st.session_state.resolved_gene = resolved_gene

    expression_source = str(st.session_state.get("expression_source") or (safe_sources[0] if safe_sources else "unavailable"))
    if safe_sources and expression_source not in safe_sources:
        expression_source = safe_sources[0]
    st.session_state.expression_source = expression_source
    clip_low = float(st.session_state.get("clip_low", 1.0))
    clip_high = float(st.session_state.get("clip_high", 99.0))
    if clip_low >= clip_high:
        clip_low, clip_high = 1.0, 99.0
    selected_cluster = str(st.session_state.get("selected_cluster") or "")
    if selected_cluster and selected_cluster not in categories:
        selected_cluster = ""
    selected_obs_ids = [obs for obs in st.session_state.get("selected_obs_ids", []) if obs in set(obs_ids)]

    can_interpret_gene = bool(resolved_gene and expression_source in safe_sources)
    gene_pack = (
        summarize_gene(
            adata,
            selected_gene,
            expression_source,
            cluster_key,
            selected_obs_ids=selected_obs_ids,
            clip_percentiles=(clip_low, clip_high),
        )
        if selected_gene
        else None
    )
    cluster_pack = summarize_cluster(adata, selected_cluster, cluster_key, selected_obs_ids) if selected_cluster else None
    selection_pack = (
        summarize_selection(adata, selected_obs_ids, selected_gene, expression_source, cluster_key)
        if selected_obs_ids
        else None
    )
    active_packs = [pack for pack in [gene_pack, cluster_pack, selection_pack] if pack is not None]
    active_evidence_ids = [pack.evidence_id for pack in active_packs]
    st.session_state.active_evidence_ids = active_evidence_ids

    control_col, canvas_col, copilot_col = st.columns([0.72, 2.18, 1.02], gap="large")
    with control_col:
        st.markdown("<div class='ss-control-heading'>视图控制</div>", unsafe_allow_html=True)
        cluster_key = st.selectbox("Cluster key", cluster_options, index=cluster_options.index(cluster_key), key="cluster_key")
        view_mode = st.segmented_control(
            "View",
            ["Gene expression", "Cluster"],
            default=str(st.session_state.get("explore_view_mode") or "Gene expression"),
            key="explore_view_mode",
        )
        gene_input = st.text_input("Gene", value=selected_gene, key="selected_gene")
        if gene_input != selected_gene:
            st.session_state.selected_gene = gene_input.strip()
            st.rerun()
        gene_choice = ""
        if genes:
            gene_choice = st.selectbox(
                "Gene panel",
                list(dict.fromkeys([selected_gene, *genes])),
                index=0,
                disabled=view_mode != "Gene expression",
                key="gene_panel_choice",
            )
        if gene_choice and gene_choice != selected_gene:
            st.session_state.pending_selected_gene = gene_choice
            st.session_state.pending_explore_view_mode = "Gene expression"
            st.rerun()
        cluster_options_ui = [""] + categories
        cluster_index = cluster_options_ui.index(selected_cluster) if selected_cluster in cluster_options_ui else 0
        cluster_choice = st.selectbox("高亮 cluster", cluster_options_ui, index=cluster_index, format_func=lambda x: "全部" if not x else f"cluster {x}")
        if cluster_choice != selected_cluster:
            st.session_state.selected_cluster = cluster_choice
            if cluster_choice:
                st.session_state.pending_explore_view_mode = "Cluster"
            st.rerun()
        source_choice = st.selectbox(
            "Expression source",
            safe_sources or ["unavailable"],
            index=(safe_sources.index(expression_source) if expression_source in safe_sources else 0),
            disabled=not safe_sources,
        )
        if source_choice != expression_source:
            st.session_state.expression_source = source_choice
            st.rerun()
        clip = st.slider("Clip percentiles", 0.0, 100.0, (clip_low, clip_high), step=0.5)
        st.session_state.clip_low, st.session_state.clip_high = float(clip[0]), float(clip[1])
        st.session_state.point_size = st.slider("Point size", min_value=4, max_value=18, value=int(st.session_state.point_size), step=1)
        if st.button("选择局部区域", width="stretch"):
            st.session_state.selected_obs_ids = _local_region_obs_ids(spatial_coords, obs_ids)
            st.rerun()
        if st.button("清除选择", width="stretch"):
            st.session_state.selected_obs_ids = []
            st.rerun()
        if not safe_sources:
            st.warning("没有安全 raw/normalized expression source；gene/marker 解释已阻断。")
        if selected_gene and not resolved_gene:
            st.warning(f"`{selected_gene}` 无法安全匹配到数据集基因。")
        elif selected_gene and resolved_gene != selected_gene:
            st.info(f"基因名已安全修复：`{selected_gene}` → `{resolved_gene}`")
            if st.button(f"使用 {resolved_gene}", width="stretch"):
                st.session_state.pending_selected_gene = resolved_gene
                st.session_state.pending_explore_view_mode = "Gene expression"
                st.rerun()

    point_size = int(st.session_state.point_size)
    use_expression = view_mode == "Gene expression" and can_interpret_gene
    if use_expression:
        values = expression_vector(adata, resolved_gene, expression_source)
        spatial_fig = _expression_scatter(
            coords=spatial_coords,
            values=values,
            title=f"Spatial expression · {resolved_gene}",
            point_size=point_size,
            obs_ids=obs_ids,
            selected_obs_ids=selected_obs_ids,
            clip_percentiles=(clip_low, clip_high),
            spatial=True,
        )
        umap_fig = _expression_scatter(
            coords=umap_coords,
            values=values,
            title=f"UMAP expression · {resolved_gene}",
            point_size=point_size,
            obs_ids=obs_ids,
            selected_obs_ids=selected_obs_ids,
            clip_percentiles=(clip_low, clip_high),
        )
    else:
        spatial_fig = _cluster_scatter(
            coords=spatial_coords,
            labels=labels,
            title=f"Spatial clusters · {cluster_key}",
            palette=palette,
            point_size=point_size,
            obs_ids=obs_ids,
            selected_cluster=selected_cluster,
            selected_obs_ids=selected_obs_ids,
            spatial=True,
        )
        umap_fig = _cluster_scatter(
            coords=umap_coords,
            labels=labels,
            title=f"UMAP clusters · {cluster_key}",
            palette=palette,
            point_size=point_size,
            obs_ids=obs_ids,
            selected_cluster=selected_cluster,
            selected_obs_ids=selected_obs_ids,
        )

    with canvas_col:
        st.markdown("<div class='ss-canvas-heading'>科研证据画布</div>", unsafe_allow_html=True)
        c_spatial, c_umap = st.columns(2, gap="medium")
        with c_spatial:
            spatial_event = _plotly_selection_event(spatial_fig, key="linked_spatial_plot")
        with c_umap:
            umap_event = _plotly_selection_event(umap_fig, key="linked_umap_plot")
        selected_from_plot = _selected_obs_from_event(spatial_event) or _selected_obs_from_event(umap_event)
        if selected_from_plot and selected_from_plot != selected_obs_ids:
            st.session_state.selected_obs_ids = selected_from_plot[:500]
            st.rerun()
        metric_items = _gene_metric_items(gene_pack, selection_pack) if use_expression and gene_pack else _cluster_metric_items(cluster_pack, selection_pack)
        st.markdown(_metric_strip_html(metric_items), unsafe_allow_html=True)
        st.caption(
            f"Evidence IDs: {', '.join(active_evidence_ids) if active_evidence_ids else '暂无'} · "
            f"Layer: {expression_source} · Clip: {clip_low:g}-{clip_high:g}% · Selected: {len(selected_obs_ids)}"
        )
        marker_rows = _marker_excerpt(state, selected_cluster)
        if marker_rows:
            st.markdown("<div class='ss-support-title'>相关 marker evidence</div>", unsafe_allow_html=True)
            st.dataframe(pd.DataFrame(marker_rows), hide_index=True, width="stretch", height=210)
        elif gene_pack is not None:
            _render_pack_summary(gene_pack)

    with copilot_col:
        st.markdown("<div class='ss-copilot-rail'>", unsafe_allow_html=True)
        status = llm_config_status()
        source_label = (
            "LLM full mode · schema-validated"
            if status.get("active_mode") == "full" and status.get("enabled")
            else "规则模式：未调用外部 LLM"
        )
        if (
            source_label.startswith("LLM")
            and st.session_state.get("copilot_conversation")
            and str(st.session_state.copilot_conversation[-1].get("source")) == "fallback"
        ):
            source_label = "LLM full mode · 当前回答已安全回退"
        st.markdown(
            (
                "<div class='ss-mini-label'>Research Copilot</div>"
                f"<div class='ss-copilot-source'>{html.escape(source_label)}</div>"
            ),
            unsafe_allow_html=True,
        )
        context_rows = [
            ("Gene", resolved_gene or selected_gene or "NA"),
            ("Cluster", selected_cluster or "全部"),
            ("Selection", f"{len(selected_obs_ids)} spots"),
            ("Layer", expression_source),
        ]
        st.markdown(_metric_strip_html(context_rows), unsafe_allow_html=True)
        prompt_options = [
            "哪个 cluster 的 Sox17 平均表达最高？",
            "我当前选择的空间区域和全局相比有什么差异？",
            "这张图最主要的局限是什么？",
            "下一步最值得运行什么分析？",
        ]
        selected_prompt = st.selectbox("快捷问题", prompt_options, index=0, key="copilot_prompt_choice")
        if st.session_state.get("_copilot_prompt_choice_seen") != selected_prompt:
            st.session_state.copilot_question = selected_prompt
            st.session_state._copilot_prompt_choice_seen = selected_prompt
        question = st.text_area("向当前证据提问", value=selected_prompt, height=86, key="copilot_question")
        if st.button("询问 Copilot", type="primary", width="stretch"):
            gateway = _runtime_gateway()
            history = list(st.session_state.get("copilot_conversation", []))[-6:]
            copilot_packs = list(active_packs)
            question_gene = _gene_mentioned_in_question(question, adata)
            if question_gene and question_gene != resolved_gene and expression_source in safe_sources:
                question_gene_pack = summarize_gene(
                    adata,
                    question_gene,
                    expression_source,
                    cluster_key,
                    selected_obs_ids=selected_obs_ids,
                    clip_percentiles=(clip_low, clip_high),
                )
                copilot_packs = [question_gene_pack, *copilot_packs]
            copilot_evidence_ids = list(dict.fromkeys(pack.evidence_id for pack in copilot_packs))
            context = {
                "research_question": state.get("user_query", ""),
                "selected_gene": question_gene or resolved_gene or selected_gene,
                "selected_cluster": selected_cluster or None,
                "selected_obs_ids": selected_obs_ids[:80],
                "expression_source": expression_source,
                "clip_percentiles": (clip_low, clip_high),
                "active_view": str(view_mode),
                "evidence_ids": copilot_evidence_ids,
                "evidence_packs": [pack.model_dump() for pack in copilot_packs],
                "warnings": list(map(str, state.get("warnings", [])[:8])),
                "available_genes": list(map(str, adata.var_names[:80])),
            }
            answer = gateway.answer_contextual_question(context=context, question=question, conversation_memory=history)
            state.setdefault("llm_calls", []).extend(gateway.telemetry)
            gateway.telemetry.clear()
            turn_id = f"copilot_{uuid4().hex[:8]}"
            for action in answer.get("suggested_actions", []) or []:
                if action.get("type") == "add_finding_to_report":
                    action.setdefault("payload", {})["finding_id"] = turn_id
            turn = {
                "turn_id": turn_id,
                "role": "assistant",
                "stage": "explore",
                "question": question,
                "content": answer.get("direct_answer") or answer.get("answer") or "",
                "source": answer.get("source", "fallback"),
                "observations": answer.get("observations", []),
                "evidence_ids": answer.get("evidence_ids", []),
                "caveats": answer.get("caveats", []),
                "ui_actions": answer.get("suggested_actions", []),
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            st.session_state.copilot_conversation = [*history, turn]
            st.session_state.run_state = state
        history = list(st.session_state.get("copilot_conversation", []))[-4:]
        for turn in reversed(history):
            evidence = ", ".join(map(str, turn.get("evidence_ids", []))) or "none"
            source = str(turn.get("source") or "fallback")
            st.markdown(
                (
                    "<div class='ss-copilot-answer'>"
                    f"<div class='ss-mini-label'>Copilot · {html.escape('LLM' if source == 'llm' else '规则解释')}</div>"
                    f"<div class='ss-card-title'>{html.escape(str(turn.get('question', '')))}</div>"
                    f"<p>{html.escape(str(turn.get('content', '')))}</p>"
                    f"<p><strong>Evidence IDs used:</strong> {html.escape(evidence)}</p>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )
            for observation in turn.get("observations", [])[:3]:
                st.caption(f"Observation: {observation}")
            for caveat in turn.get("caveats", [])[:2]:
                st.caption(f"Caveat: {caveat}")
            action_cols = st.columns(min(2, max(1, len(turn.get("ui_actions", []) or []))))
            for index, action in enumerate(turn.get("ui_actions", []) or []):
                col = action_cols[index % len(action_cols)]
                if col.button(str(action.get("label") or action.get("type")), key=f"action_{turn.get('turn_id')}_{index}", width="stretch"):
                    try:
                        message = apply_ui_action(action)
                        st.toast(message)
                        st.rerun()
                    except Exception as exc:  # noqa: BLE001
                        st.error(str(exc))
        st.markdown("</div>", unsafe_allow_html=True)


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


def _evidence_ids_matching(state: dict[str, Any], *needles: str) -> list[str]:
    ids: list[str] = []
    for item in state.get("evidence_artifacts", []):
        haystack = f"{item.get('title', '')} {item.get('caption', '')} {item.get('tool', '')} {item.get('path', '')}".lower()
        if all(needle.lower() in haystack for needle in needles):
            ids.append(str(item.get("evidence_id")))
    return [item for item in ids if item]


def _evidence_ids_for_tools(state: dict[str, Any], *tools: str) -> list[str]:
    wanted = set(tools)
    ids = [
        str(item.get("evidence_id"))
        for item in state.get("evidence_artifacts", [])
        if str(item.get("tool")) in wanted and str(item.get("evidence_id"))
    ]
    return list(dict.fromkeys(ids))


def render_report_findings(state: dict[str, Any]) -> None:
    st.markdown("<div class='ss-section-title'>Findings</div>", unsafe_allow_html=True)
    findings = state.get("scientific_findings", [])
    if not findings:
        st.info("还没有 evidence-linked findings。")
        return
    for finding in findings[:5]:
        evidence = ", ".join(map(str, finding.get("evidence_ids", []))) or "not available"
        support = "; ".join(map(str, finding.get("quantitative_support", [])[:3]))
        caveat = " ".join(map(str, finding.get("caveats", [])[:2]))
        st.markdown(
            (
                "<div class='ss-story'>"
                f"<div class='ss-card-title'>{html.escape(str(finding.get('title', 'Finding')))}</div>"
                f"<p>{html.escape(str(finding.get('statement', '')))}</p>"
                f"<p><strong>Quantitative support:</strong> {html.escape(support or 'not available')}</p>"
                f"<p><strong>Evidence:</strong> {html.escape(evidence)}</p>"
                f"<p><strong>Caveat:</strong> {html.escape(caveat or 'Interpret cautiously within the recorded evidence.')}</p>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )


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


def render_report_assets(state: dict[str, Any], *, primary: bool = False) -> None:
    run_dir = Path(str(state.get("run_dir") or ""))
    if primary:
        bundle = run_dir / "run_bundle.zip"
        report = Path(str(state.get("report_path") or run_dir / "report.html"))
        cols = st.columns(2)
        if report.exists():
            cols[0].download_button("Download report HTML", report.read_bytes(), file_name=report.name, width="stretch")
        if bundle.exists():
            cols[1].download_button("Download reproducibility bundle", bundle.read_bytes(), file_name=bundle.name, width="stretch")
        return
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
    evidence = state.get("evidence_packs") or state.get("evidence_artifacts", [])
    if not evidence:
        return
    st.markdown("<div class='ss-section-title'>Contextual Copilot</div>", unsafe_allow_html=True)
    labels = {
        f"{item.get('evidence_id')} · {item.get('title') or Path(str(item.get('path', ''))).name}": item
        for item in evidence
    }
    selected_labels = st.multiselect("选择证据上下文", list(labels), default=list(labels)[: min(8, len(labels))])
    selected_items = [labels[label] for label in selected_labels] if selected_labels else [evidence[0]]
    history = list(state.get("copilot_history", []))[-8:]
    question = st.text_input("向证据提问", value="这组证据最支持什么？主要局限是什么？")
    if st.button("询问 Copilot", width="stretch"):
        table_titles = [str(table.get("title") or table.get("path")) for table in state.get("generated_tables", [])[:4]]
        context = context_for_copilot(
            selected_evidence=selected_items,
            warnings=list(map(str, state.get("warnings", [])[:8])),
            table_titles=table_titles,
            conversation_memory=history,
        )
        context["title"] = "; ".join(str(item.get("title") or item.get("path")) for item in selected_items)
        gateway = LLMGateway.from_env()
        answer = gateway.answer_contextual_question(context=context, question=question, conversation_memory=history)
        state.setdefault("llm_calls", []).extend(gateway.telemetry)
        state.setdefault("copilot_history", []).append(
            {
                "question": question,
                "answer": answer.get("answer", ""),
                "evidence_ids": answer.get("evidence_ids", []),
                "caveat": answer.get("caveat", ""),
                "next_step": answer.get("next_step", ""),
                "source": answer.get("source", "unknown"),
            }
        )
        st.session_state.run_state = state
        history = list(state.get("copilot_history", []))[-8:]
    for item in reversed(history[-3:]):
        used_ids = item.get("evidence_ids", [])
        st.markdown(
            (
                "<div class='ss-story'>"
                f"<div class='ss-mini-label'>Copilot · {html.escape(str(item.get('source', 'llm')))}</div>"
                f"<div class='ss-card-title'>{html.escape(str(item.get('question', '')))}</div>"
                f"<p>{html.escape(str(item.get('answer', '')))}</p>"
                f"<p><strong>Evidence IDs used:</strong> {html.escape(', '.join(map(str, used_ids)) or 'none')}</p>"
                f"<p><strong>Caveat:</strong> {html.escape(str(item.get('caveat', '')))}</p>"
                f"<p><strong>Next step:</strong> {html.escape(str(item.get('next_step', '')))}</p>"
                "</div>"
            ),
            unsafe_allow_html=True,
        )


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
