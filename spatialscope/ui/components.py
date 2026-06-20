from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from spatialscope.agent.llm import llm_config_status, smoke_test_llm
from spatialscope.domain.dataset_store import DEFAULT_DATASET_STORE
from spatialscope.domain.expression_lineage import infer_matrix_state
from spatialscope.llm.context import context_for_copilot
from spatialscope.llm.gateway import LLMGateway
from spatialscope.tools.registry import tool_contract_summary
from spatialscope.utils.agent_audit import build_agent_audit, load_agent_audit
from spatialscope.utils.artifact_audit import audit_artifacts
from spatialscope.utils.dataset_card import build_dataset_card
from spatialscope.utils.gene_matching import match_gene_name
from spatialscope.utils.run_index import discover_runs
from spatialscope.visualization.theme import CLUSTER_PALETTE, numeric_sort_key

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
    spatial: bool = False,
) -> go.Figure:
    fig = go.Figure()
    categories = sorted(labels.astype(str).unique(), key=numeric_sort_key)
    for category in categories:
        mask = np.asarray(labels.astype(str) == category)
        fig.add_trace(
            go.Scattergl(
                x=coords[mask, 0],
                y=coords[mask, 1],
                mode="markers",
                name=str(category),
                marker={"size": point_size, "color": palette[str(category)], "opacity": 0.86, "line": {"width": 0}},
                hovertemplate="group=%{fullData.name}<br>x=%{x:.2f}<br>y=%{y:.2f}<extra></extra>",
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
    spatial: bool = False,
) -> go.Figure:
    finite = values[np.isfinite(values)]
    if len(finite):
        lo, hi = np.percentile(finite, [1, 99])
        values = np.clip(values, lo, hi)
    fig = go.Figure(
        go.Scattergl(
            x=coords[:, 0],
            y=coords[:, 1],
            mode="markers",
            marker={
                "size": point_size,
                "color": values,
                "colorscale": [[0, "#f7faf9"], [0.35, "#dcefed"], [0.7, "#3d9a91"], [1, "#075a54"]],
                "showscale": True,
                "colorbar": {"title": "expr"},
                "opacity": 0.9,
                "line": {"width": 0},
            },
            hovertemplate="expr=%{marker.color:.3g}<br>x=%{x:.2f}<br>y=%{y:.2f}<extra></extra>",
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


def render_linked_explore(state: dict[str, Any]) -> None:
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

    control_col, spatial_col, umap_col = st.columns([0.82, 1.12, 1.12], gap="large")
    with control_col:
        st.markdown("<div class='ss-panel compact'><div class='ss-mini-label'>Explore Controls</div><div class='ss-card-title'>联动证据工作台</div>", unsafe_allow_html=True)
        cluster_key = st.selectbox("Cluster key", cluster_options, index=0)
        color_mode = st.segmented_control("颜色模式", ["Cluster", "Gene expression"], default="Cluster")
        genes = _gene_choices(state, adata)
        selected_gene = st.selectbox("Gene", genes, index=0, disabled=color_mode != "Gene expression")
        layers = _safe_expression_layers(adata)
        layer = st.selectbox("Expression layer", layers or ["no safe layer"], index=0, disabled=color_mode != "Gene expression" or not layers)
        point_size = st.slider("Point size", min_value=4, max_value=18, value=8, step=1)
        st.markdown("</div>", unsafe_allow_html=True)
        if color_mode == "Gene expression" and not layers:
            st.warning("没有安全 raw/normalized expression source；gene/marker 解释已被阻断。")
        st.markdown("<div class='ss-section-title'>Evidence-linked Findings</div>", unsafe_allow_html=True)
        for finding in state.get("scientific_findings", [])[:3]:
            evidence = ", ".join(map(str, finding.get("evidence_ids", [])))
            st.markdown(
                (
                    "<div class='ss-story compact'>"
                    f"<div class='ss-card-title'>{html.escape(str(finding.get('title', 'Finding')))}</div>"
                    f"<p>{html.escape(str(finding.get('statement', '')))}</p>"
                    f"<p class='ss-run-path'>{html.escape(evidence)}</p>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )

    labels = adata.obs[cluster_key].astype(str)
    categories = sorted(labels.unique(), key=numeric_sort_key)
    palette = _palette_for(adata, cluster_key, categories)
    spatial_coords = np.asarray(adata.obsm["spatial"])
    umap_coords = np.asarray(adata.obsm["X_umap"])
    use_expression = color_mode == "Gene expression" and bool(layers) and selected_gene in list(map(str, adata.var_names))
    if use_expression:
        values = _gene_vector(adata, selected_gene, layer)
        spatial_fig = _expression_scatter(
            coords=spatial_coords,
            values=values,
            title=f"Spatial expression · {selected_gene}",
            point_size=point_size,
            spatial=True,
        )
        umap_fig = _expression_scatter(
            coords=umap_coords,
            values=values,
            title=f"UMAP expression · {selected_gene}",
            point_size=point_size,
        )
    else:
        spatial_fig = _cluster_scatter(
            coords=spatial_coords,
            labels=labels,
            title=f"Spatial clusters · {cluster_key}",
            palette=palette,
            point_size=point_size,
            spatial=True,
        )
        umap_fig = _cluster_scatter(
            coords=umap_coords,
            labels=labels,
            title=f"UMAP clusters · {cluster_key}",
            palette=palette,
            point_size=point_size,
        )
    with spatial_col:
        st.plotly_chart(spatial_fig, use_container_width=True, key="linked_spatial_plot")
        st.caption("Gene expression 模式下两张图共享同一顺序色标。" if use_expression else "Spatial 与 UMAP 在 cluster 模式下共享同一套颜色。")
    with umap_col:
        st.plotly_chart(umap_fig, use_container_width=True, key="linked_umap_plot")
        st.caption("当前使用安全表达层；表达模式仍需结合 evidence 与 caveat 解读。" if use_expression else "Gene expression 模式只使用安全表达层；否则保持 cluster 视图。")


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
