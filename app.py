from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from spatialscope.agent.graph import execute_agent_state, preview_agent_plan
from spatialscope.agent.planner import validate_plan_steps
from spatialscope.tools.registry import tool_contract_summary


PROJECT_SIGNATURE = "seu-yolo / 东南大学计算生物学"
PROJECT_TAGS = [
    ("期末大作业", "info"),
    ("LangGraph Agent", "success"),
    ("全流程可追踪", "neutral"),
    ("GLM 已适配", "warn"),
]
ACKNOWLEDGEMENT_LINES = [
    "This project was developed for the Computational Biology final assignment at Southeast University.",
    "We gratefully acknowledge Professor Peng Xie from the School of Biological Science and Medical Engineering, Southeast University.",
    "We also thank Teaching Assistant Binyu Gao for guidance and support throughout the course project.",
]


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
        font-family: "PingFang SC", "Noto Sans CJK SC", "Microsoft YaHei", Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      .block-container { padding-top: 1.05rem; max-width: 1380px; }
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
        background:
          linear-gradient(135deg, rgba(15, 118, 110, 0.07), rgba(111, 78, 143, 0.055)),
          rgba(255, 255, 255, 0.97);
        box-shadow: 0 10px 30px rgba(23, 32, 38, 0.055);
        padding: 22px 22px 18px;
        margin-bottom: 16px;
        display: grid;
        grid-template-columns: minmax(0, 1fr) 210px;
        gap: 22px;
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
        font-size: 2.38rem;
        font-weight: 760;
        letter-spacing: 0;
        line-height: 1.12;
      }
      .ss-subtitle {
        color: var(--ss-muted);
        margin-top: 6px;
        max-width: 760px;
        line-height: 1.55;
      }
      .ss-status-row { margin-top: 12px; }
      .ss-tagline {
        color: var(--ss-muted);
        font-size: 0.86rem;
        margin-top: 8px;
        line-height: 1.5;
      }
      .ss-stamp {
        border-top: 1px solid var(--ss-line);
        color: var(--ss-muted);
        font-size: 0.74rem;
        font-weight: 650;
        letter-spacing: 0.04em;
        margin-top: 12px;
        padding-top: 10px;
        text-transform: uppercase;
      }
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
        margin: 12px 0 14px;
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
      .ss-mode-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
        margin: 10px 0 16px;
      }
      .ss-mode-card {
        border: 1px solid var(--ss-line);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.94);
        min-height: 128px;
        padding: 14px;
        box-shadow: 0 1px 0 rgba(23, 32, 38, 0.03);
      }
      .ss-mode-card strong {
        color: var(--ss-ink);
        display: block;
        font-size: 1.02rem;
        margin-bottom: 5px;
      }
      .ss-mode-card span {
        color: var(--ss-muted);
        display: block;
        font-size: 0.88rem;
        line-height: 1.5;
      }
      .ss-workflow {
        display: grid;
        grid-template-columns: repeat(9, minmax(74px, 1fr));
        gap: 7px;
        margin: 10px 0 18px;
      }
      .ss-node {
        border: 1px solid var(--ss-line);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.94);
        min-height: 74px;
        padding: 9px 8px;
      }
      .ss-node .ss-mini-label { font-size: 0.66rem; }
      .ss-node-name {
        color: var(--ss-ink);
        font-size: 0.78rem;
        font-weight: 720;
        line-height: 1.25;
        margin-top: 4px;
      }
      .ss-node.pending { opacity: 0.58; }
      .ss-node.success { border-color: #a8d5d1; background: #f3fbfa; }
      .ss-node.warn, .ss-node.repaired { border-color: #e0c38f; background: #fff8ed; }
      .ss-node.fail { border-color: #e9aaa2; background: #fff4f2; }
      .ss-plan-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(235px, 1fr));
        gap: 10px;
        margin: 10px 0 16px;
      }
      .ss-plan-card {
        border: 1px solid var(--ss-line);
        border-radius: 8px;
        background: #fff;
        padding: 12px;
        min-height: 122px;
      }
      .ss-plan-tool {
        color: var(--ss-ink);
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        font-size: 0.86rem;
        font-weight: 720;
        overflow-wrap: anywhere;
      }
      .ss-plan-rationale {
        color: var(--ss-muted);
        font-size: 0.84rem;
        line-height: 1.42;
        margin-top: 6px;
      }
      .ss-evidence-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 10px;
        margin-bottom: 14px;
      }
      .ss-evidence-card {
        border: 1px solid var(--ss-line);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.94);
        padding: 12px;
      }
      .ss-evidence-value {
        color: var(--ss-ink);
        font-size: 1.35rem;
        font-weight: 760;
        line-height: 1.1;
        margin-top: 4px;
      }
      .ss-tag-wall {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin: 10px 0 14px;
      }
      .ss-ack {
        border: 1px solid var(--ss-line);
        border-radius: 8px;
        background: linear-gradient(135deg, rgba(15, 118, 110, 0.06), rgba(111, 78, 143, 0.055)), #fff;
        padding: 14px;
        margin: 10px 0 16px;
      }
      .ss-ack-line {
        color: var(--ss-muted);
        font-size: 0.88rem;
        line-height: 1.45;
        margin-top: 4px;
      }
      .ss-footer {
        border-top: 1px solid var(--ss-line);
        color: var(--ss-muted);
        display: flex;
        flex-wrap: wrap;
        font-size: 0.82rem;
        gap: 8px 14px;
        justify-content: space-between;
        margin-top: 18px;
        padding: 16px 2px 4px;
      }
      .ss-credit-bar {
        align-items: center;
        border: 1px solid var(--ss-line);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.9);
        color: var(--ss-muted);
        display: flex;
        flex-wrap: wrap;
        font-size: 0.84rem;
        gap: 8px 12px;
        margin: -6px 0 14px;
        padding: 9px 12px;
      }
      .ss-credit-bar strong { color: var(--ss-ink); }
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
        .ss-mode-grid, .ss-workflow { grid-template-columns: 1fr; }
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
                "节点": item.get("node"),
                "工具": item.get("tool"),
                "状态": item.get("status"),
                "耗时秒": item.get("duration_sec"),
                "摘要": item.get("summary"),
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
            _chip(f"{counts['success']} 步成功", "success"),
            _chip(f"{counts['skipped']} 步跳过", "warn" if counts["skipped"] else "neutral"),
            _chip(f"{counts['failed']} 步失败", "fail" if counts["failed"] else "neutral"),
            _chip(f"{counts['repaired']} 步修复", "warn" if counts["repaired"] else "neutral"),
        ]
    )
    st.markdown(f'<div class="ss-status-row">{chips}</div>', unsafe_allow_html=True)


def _render_tag_wall() -> None:
    tags = "".join(_chip(label, tone) for label, tone in PROJECT_TAGS)
    st.markdown(f'<div class="ss-tag-wall">{tags}</div>', unsafe_allow_html=True)


def _render_acknowledgements() -> None:
    lines = "".join(f'<div class="ss-ack-line">{html.escape(line)}</div>' for line in ACKNOWLEDGEMENT_LINES)
    st.markdown(
        f"""
        <div class="ss-ack">
          <div class="ss-mini-label">致谢</div>
          <div class="ss-card-title">来自构建者的一点小注脚</div>
          {lines}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_credit_bar() -> None:
    st.markdown(
        f"""
        <div class="ss-credit-bar">
          <strong>致谢</strong>
          <span>{html.escape(ACKNOWLEDGEMENT_LINES[0])}</span>
          <span>{html.escape(PROJECT_SIGNATURE)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


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


def _render_figure_downloads(fig: dict[str, Any], *, key_prefix: str) -> None:
    cols = st.columns(2)
    path = fig.get("path")
    svg_path = fig.get("svg_path")
    if path and Path(str(path)).exists():
        cols[0].download_button(
            "PNG",
            Path(str(path)).read_bytes(),
            file_name=Path(str(path)).name,
            width="stretch",
            key=f"{key_prefix}_png",
        )
    if svg_path and Path(str(svg_path)).exists():
        cols[1].download_button(
            "SVG",
            Path(str(svg_path)).read_bytes(),
            file_name=Path(str(svg_path)).name,
            width="stretch",
            key=f"{key_prefix}_svg",
        )


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


def _parse_gene_text(text: str) -> list[str]:
    cleaned = text.replace("，", ",").replace(";", ",").replace("\n", ",")
    genes = [item.strip() for chunk in cleaned.split(",") for item in chunk.split() if item.strip()]
    seen: set[str] = set()
    return [gene for gene in genes if not (gene in seen or seen.add(gene))]


def _apply_ui_overrides(
    state: dict[str, Any],
    *,
    min_genes: int,
    min_cells: int,
    max_mt_pct: float,
    resolution: float,
    gene_text: str,
    annotation_top_n: int,
) -> dict[str, Any]:
    plan = []
    genes = _parse_gene_text(gene_text)
    for raw_step in state.get("approved_plan", []):
        step = dict(raw_step)
        params = dict(step.get("params", {}))
        if step.get("tool") == "run_qc":
            params.update({"min_genes": min_genes, "min_cells": min_cells, "max_mt_pct": max_mt_pct})
        elif step.get("tool") == "run_clustering":
            params.update({"resolution": resolution})
        elif step.get("tool") == "plot_gene_panel" and genes:
            params.update({"genes": genes[:8]})
        elif step.get("tool") == "suggest_cluster_annotations":
            params.update({"top_n": annotation_top_n})
        step["params"] = params
        plan.append(step)

    plan = validate_plan_steps(plan)
    state["approved_plan"] = plan
    state["task_plan"] = plan
    state.setdefault("parameters", {}).update(
        {
            "qc": {"min_genes": min_genes, "min_cells": min_cells, "max_mt_pct": max_mt_pct},
            "clustering": {"resolution": resolution},
            "gene_panel_override": genes[:8],
            "cluster_annotation": {"top_n": annotation_top_n},
        }
    )
    return state


def _mode_cards_html() -> str:
    cards = [
        (
            "快速模式",
            "用于演示和冒烟测试：数据概览、QC、UMAP、空间聚类和指定基因面板。",
        ),
        (
            "标准模式",
            "覆盖期末要求的核心分析：预处理、聚类、marker genes、候选注释、图表和报告。",
        ),
        (
            "高阶模式",
            "在标准流程上加入可选的空间变异基因与邻域富集分析，适合展示扩展能力。",
        ),
    ]
    body = "".join(
        f'<div class="ss-mode-card"><strong>{title}</strong><span>{description}</span></div>'
        for title, description in cards
    )
    return f'<div class="ss-mode-grid">{body}</div>'


def _render_workflow_map(state: dict[str, Any] | None) -> None:
    nodes = [
        ("parse_request", "解析请求"),
        ("inspect_dataset", "检查数据"),
        ("plan_analysis", "生成方案"),
        ("preview_plan", "方案预览"),
        ("execute_tool", "执行工具"),
        ("validate_result", "结果校验"),
        ("repair_or_continue", "自动修复"),
        ("interpret", "结果解释"),
        ("report", "生成报告"),
    ]
    status_labels = {
        "pending": "等待",
        "success": "完成",
        "skipped": "跳过",
        "failed": "失败",
        "repaired": "已修复",
    }
    trace = state.get("execution_trace", []) if state else []
    seen = {str(item.get("node")): str(item.get("status", "success")) for item in trace}
    if state and state.get("approved_plan"):
        for node in ["parse_request", "inspect_dataset", "plan_analysis", "preview_plan"]:
            seen.setdefault(node, "success")
    if state and state.get("final_answer"):
        seen.setdefault("interpret", "success")
    if state and state.get("report_path"):
        seen.setdefault("report", "success")

    html_nodes = []
    for index, (node, label) in enumerate(nodes, start=1):
        status = seen.get(node, "pending")
        tone = "fail" if status == "failed" else status
        html_nodes.append(
            f"""
            <div class="ss-node {tone}">
              <div class="ss-mini-label">{index:02d} {html.escape(status_labels.get(status, status))}</div>
              <div class="ss-node-name">{html.escape(label)}</div>
            </div>
            """
        )
    st.markdown(f'<div class="ss-workflow">{"".join(html_nodes)}</div>', unsafe_allow_html=True)


def _render_plan_cards(plan: list[dict[str, Any]]) -> None:
    cards = []
    for index, step in enumerate(plan, start=1):
        optional = _chip("可选", "warn") if step.get("optional") else ""
        params = html.escape(json.dumps(step.get("params", {}), ensure_ascii=False))
        rationale = html.escape(str(step.get("rationale", "")))
        cards.append(
            f"""
            <div class="ss-plan-card">
              <div class="ss-mini-label">步骤 {index:02d} {optional}</div>
              <div class="ss-plan-tool">{html.escape(str(step.get("tool")))}</div>
              <div class="ss-plan-rationale">{rationale}</div>
              <div class="ss-run-path">{params}</div>
            </div>
            """
        )
    st.markdown(f'<div class="ss-plan-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def _render_evidence_cards(state: dict[str, Any]) -> None:
    observations = state.get("observations", {})
    dataset = state.get("dataset_summary", {})
    evidence = [
        ("数据指纹", str(state.get("dataset_hash") or "未生成")[:12]),
        ("空间坐标", "是" if dataset.get("has_spatial") else "否"),
        ("匹配基因", len(observations.get("resolved_genes", []))),
        ("候选注释", len(observations.get("cluster_annotation_suggestions", []))),
    ]
    cards = "".join(
        f"""
        <div class="ss-evidence-card">
          <div class="ss-mini-label">{html.escape(label)}</div>
          <div class="ss-evidence-value">{html.escape(str(value))}</div>
        </div>
        """
        for label, value in evidence
    )
    st.markdown(f'<div class="ss-evidence-grid">{cards}</div>', unsafe_allow_html=True)


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


def _brand_mark_html() -> str:
    return f"""
    <div>
      {_glyph_html()}
      <div class="ss-stamp">{html.escape(PROJECT_SIGNATURE)}</div>
    </div>
    """


def _render_header(active: dict[str, Any] | None) -> None:
    run_label = str(active.get("run_id")) if active else "暂无运行"
    mode_display = {"quick": "快速模式", "standard": "标准模式", "advanced": "高阶模式"}
    source_display = {"llm": "LLM 规划", "rule_based": "规则规划", "user_edited": "人工修订"}
    mode_label = mode_display.get(str(active.get("mode")), "未选择模式") if active else "未选择模式"
    plan_label = source_display.get(str(active.get("plan_source")), "等待生成方案") if active else "等待生成方案"
    llm_tone = "success" if active and active.get("llm_enabled") else "neutral"
    llm_label = "GLM 已接入" if active and active.get("llm_enabled") else "规则兜底"
    health_label = "就绪"
    health_tone = _run_tone(active)
    if active and active.get("errors"):
        health_label = f"{len(active.get('errors', []))} 个错误"
    elif active and active.get("warnings"):
        health_label = f"{len(active.get('warnings', []))} 条提醒"
    elif active and active.get("generated_figures"):
        health_label = "分析完成"

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
            <div class="ss-kicker">SpatialScope Agent · 中文友好版</div>
            <div class="ss-title">空间转录组分析工作台</div>
            <div class="ss-subtitle">从自然语言请求到可复现报告：自动规划、执行 Scanpy/Squidpy 工作流，并保留完整 trace。当前运行 <span class="ss-run-path">{run_label}</span></div>
            <div class="ss-tagline">面向期末展示：流程清晰、图表精致、解释谨慎，并带有一点属于我们的项目签名。</div>
            <div class="ss-status-row">{chips}</div>
            <div class="ss-tag-wall">{"".join(_chip(label, tone) for label, tone in PROJECT_TAGS)}</div>
          </div>
          {_brand_mark_html()}
        </section>
        """,
        unsafe_allow_html=True,
    )


def _render_footer(active: dict[str, Any] | None) -> None:
    run = html.escape(str(active.get("run_id"))) if active else "暂无运行"
    st.markdown(
        f"""
        <footer class="ss-footer">
          <span>{html.escape(PROJECT_SIGNATURE)}</span>
          <span>SpatialScope Agent · 可复现空间转录组分析工作台</span>
          <span>运行 {run}</span>
        </footer>
        """,
        unsafe_allow_html=True,
    )


_init_state()

active = _active_state()
_render_header(active)
_render_credit_bar()

start_tab, analyze_tab, explore_tab, report_tab = st.tabs(["开始", "方案", "探索", "报告"])

with start_tab:
    left, right = st.columns([1.05, 0.95], gap="large")
    with left:
        st.markdown('<div class="ss-section-title">输入与运行设置</div>', unsafe_allow_html=True)
        st.markdown(_mode_cards_html(), unsafe_allow_html=True)
        uploaded = st.file_uploader("上传空间 AnnData 文件（.h5ad）", type=["h5ad"])
        default_data = st.text_input("本地数据路径", value="data/demo_tiny.h5ad")
        query = st.text_area(
            "分析任务",
            value="运行标准空间转录组分析，生成 marker genes、候选 cluster 注释，并绘制 GeneA GeneB 空间表达图。",
            height=118,
        )
        mode_label = st.segmented_control("运行模式", ["快速", "标准", "高阶"], default="标准")
        mode = {"快速": "quick", "标准": "standard", "高阶": "advanced"}[mode_label]
        outdir = st.text_input("输出目录", value="outputs/runs")

        upload_path = _save_upload(uploaded)
        data_path = upload_path or default_data

        with st.expander("分析参数", expanded=True):
            q1, q2, q3 = st.columns(3)
            min_genes = q1.number_input("每个 spot 最少基因数", min_value=0, max_value=5000, value=20, step=5)
            min_cells = q2.number_input("每个基因最少细胞数", min_value=0, max_value=200, value=3, step=1)
            max_mt_pct = q3.number_input("线粒体比例上限", min_value=0.0, max_value=100.0, value=25.0, step=1.0)
            c_res, c_gene, c_anno = st.columns([0.8, 1.3, 0.8])
            resolution = c_res.slider("Leiden 分辨率", min_value=0.1, max_value=2.0, value=0.8, step=0.1)
            gene_text = c_gene.text_input("基因面板", value="GeneA, GeneB")
            annotation_top_n = c_anno.number_input("候选注释 marker 数", min_value=3, max_value=30, value=12, step=1)

        c1, c2 = st.columns(2)
        if c1.button("生成分析方案", type="primary", width="stretch"):
            with st.spinner("正在生成分析方案..."):
                state = preview_agent_plan(data_path=data_path, query=query, mode=mode, outdir=outdir)
                state = _apply_ui_overrides(
                    state,
                    min_genes=min_genes,
                    min_cells=min_cells,
                    max_mt_pct=max_mt_pct,
                    resolution=resolution,
                    gene_text=gene_text,
                    annotation_top_n=annotation_top_n,
                )
            st.session_state.draft_state = state
            st.session_state.run_state = None
            st.session_state.plan_text = _plan_to_text(state.get("approved_plan", []))
            st.session_state.last_plan_error = ""
            st.rerun()

        if c2.button("直接运行", width="stretch"):
            with st.spinner("正在运行工作流..."):
                state = preview_agent_plan(data_path=data_path, query=query, mode=mode, outdir=outdir)
                state = _apply_ui_overrides(
                    state,
                    min_genes=min_genes,
                    min_cells=min_cells,
                    max_mt_pct=max_mt_pct,
                    resolution=resolution,
                    gene_text=gene_text,
                    annotation_top_n=annotation_top_n,
                )
                st.session_state.run_state = execute_agent_state(
                    state,
                    approved_plan=state.get("approved_plan", []),
                    plan_source=state.get("plan_source", "rule_based"),
                )
            st.session_state.draft_state = None
            st.session_state.plan_text = _plan_to_text(st.session_state.run_state.get("approved_plan", []))
            st.rerun()

    with right:
        st.markdown('<div class="ss-section-title">Agent 流程图</div>', unsafe_allow_html=True)
        _render_workflow_map(_active_state())
        _render_acknowledgements()
        st.markdown('<div class="ss-section-title">工具注册表</div>', unsafe_allow_html=True)
        registry_df = pd.DataFrame(tool_contract_summary())
        st.dataframe(registry_df, hide_index=True, width="stretch", height=432)

with analyze_tab:
    state = st.session_state.draft_state
    if not state:
        st.info("请先在「开始」页生成分析方案。")
    else:
        st.markdown('<div class="ss-section-title">Workflow 状态</div>', unsafe_allow_html=True)
        _render_workflow_map(state)
        st.markdown('<div class="ss-section-title">数据就绪情况</div>', unsafe_allow_html=True)
        status_cols = st.columns(4)
        summary = state.get("dataset_summary", {})
        status_cols[0].metric("Observations", summary.get("n_obs", "NA"))
        status_cols[1].metric("Genes", summary.get("n_vars", "NA"))
        status_cols[2].metric("Spatial", "yes" if summary.get("has_spatial") else "no")
        status_cols[3].metric("Plan steps", len(state.get("approved_plan", [])))

        st.markdown('<div class="ss-section-title">已批准的分析方案</div>', unsafe_allow_html=True)
        st.caption(state.get("plan_rationale") or "暂无 plan rationale。")
        _render_plan_cards(state.get("approved_plan", []))
        with st.expander("编辑 Plan JSON", expanded=False):
            st.session_state.plan_text = st.text_area(
                "Plan JSON",
                value=st.session_state.plan_text or _plan_to_text(state.get("approved_plan", [])),
                height=360,
            )

        b1, b2 = st.columns([1, 1])
        if b1.button("校验 Plan", width="stretch"):
            try:
                plan = _load_plan_from_text(st.session_state.plan_text)
                st.session_state.plan_text = _plan_to_text(plan)
                st.session_state.last_plan_error = ""
                st.success("Plan JSON 校验通过。")
            except Exception as exc:  # noqa: BLE001
                st.session_state.last_plan_error = str(exc)

        if b2.button("运行已批准方案", type="primary", width="stretch"):
            try:
                plan = _load_plan_from_text(st.session_state.plan_text)
                with st.spinner("正在执行已批准的 workflow..."):
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

        st.markdown('<div class="ss-section-title">Dataset summary</div>', unsafe_allow_html=True)
        st.json(summary)

with explore_tab:
    state = st.session_state.run_state
    if not state:
        st.info("请先运行一个已批准的分析方案。")
    else:
        st.markdown('<div class="ss-section-title">运行快照</div>', unsafe_allow_html=True)
        top = st.columns(5)
        top[0].metric("Figures", len(state.get("generated_figures", [])))
        top[1].metric("Tables", len(state.get("generated_tables", [])))
        top[2].metric("Trace steps", len(state.get("execution_trace", [])))
        top[3].metric("Warnings", len(state.get("warnings", [])))
        top[4].metric("Errors", len(state.get("errors", [])))
        _render_status_strip(state)
        st.markdown(f'<div class="ss-run-path">{state.get("run_dir")}</div>', unsafe_allow_html=True)
        _render_evidence_cards(state)

        st.markdown('<div class="ss-section-title">Execution Trace</div>', unsafe_allow_html=True)
        _render_workflow_map(state)
        trace_df = _trace_dataframe(state)
        st.dataframe(
            trace_df,
            hide_index=True,
            width="stretch",
            column_config={
                "节点": st.column_config.TextColumn("节点", width="small"),
                "工具": st.column_config.TextColumn("Tool", width="medium"),
                "状态": st.column_config.TextColumn("状态", width="small"),
                "耗时秒": st.column_config.NumberColumn("秒", format="%.3f", width="small"),
                "摘要": st.column_config.TextColumn("摘要", width="large"),
            },
        )

        st.markdown('<div class="ss-section-title">Figure Gallery</div>', unsafe_allow_html=True)
        figures = state.get("generated_figures", [])
        if figures:
            lead = figures[0]
            lead_path = lead.get("path")
            with st.container(border=True):
                st.markdown('<div class="ss-mini-label">主图</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="ss-card-title">{lead.get("title", Path(str(lead_path)).name)}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="ss-figure-note">{lead.get("caption", "")}</div>', unsafe_allow_html=True)
                if lead_path and Path(lead_path).exists():
                    st.image(lead_path, width="stretch")
                    _render_figure_downloads(lead, key_prefix="lead_figure")

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
                                _render_figure_downloads(fig, key_prefix=f"figure_{i}_{Path(str(path)).stem}")
                            else:
                                st.caption("Figure 文件暂不可用。")
        else:
            st.info("尚未生成 figures。")

        st.markdown('<div class="ss-section-title">Tables</div>', unsafe_allow_html=True)
        tables = state.get("generated_tables", [])
        if tables:
            annotation_table = next(
                (table for table in tables if "annotation" in str(table.get("title", "")).lower()),
                None,
            )
            annotation_preview = _read_table_preview(annotation_table.get("path")) if annotation_table else None
            if annotation_preview is not None:
                with st.container(border=True):
                    st.markdown('<div class="ss-mini-label">解释支持</div>', unsafe_allow_html=True)
                    st.markdown('<div class="ss-card-title">候选 Cluster labels</div>', unsafe_allow_html=True)
                    st.dataframe(annotation_preview, hide_index=True, width="stretch", height=260)
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
                                st.caption("预览暂不可用。")
        else:
            st.info("尚未生成 tables。")

with report_tab:
    state = st.session_state.run_state
    if not state:
        st.info("请先运行一个已批准的分析方案。")
    else:
        st.markdown('<div class="ss-section-title">结果解释</div>', unsafe_allow_html=True)
        _render_workflow_map(state)
        _render_evidence_cards(state)
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

        st.markdown('<div class="ss-section-title">可复现输出包</div>', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns(4)
        if report_path and Path(str(report_path)).exists():
            with c1:
                with st.container(border=True):
                    st.markdown('<div class="ss-mini-label">报告</div>', unsafe_allow_html=True)
                    st.markdown('<div class="ss-card-title">Report HTML</div>', unsafe_allow_html=True)
                    st.download_button(
                        "下载",
                        Path(str(report_path)).read_bytes(),
                        file_name="spatialscope_report.html",
                        width="stretch",
                    )
        if trace_path.exists():
            with c2:
                with st.container(border=True):
                    st.markdown('<div class="ss-mini-label">溯源</div>', unsafe_allow_html=True)
                    st.markdown('<div class="ss-card-title">Trace JSON</div>', unsafe_allow_html=True)
                    st.download_button("下载", trace_path.read_bytes(), file_name="agent_trace.json", width="stretch")
        if metadata_path.exists():
            with c3:
                with st.container(border=True):
                    st.markdown('<div class="ss-mini-label">元数据</div>', unsafe_allow_html=True)
                    st.markdown('<div class="ss-card-title">Run JSON</div>', unsafe_allow_html=True)
                    st.download_button("下载", metadata_path.read_bytes(), file_name="run_metadata.json", width="stretch")
        if param_path.exists():
            with c4:
                with st.container(border=True):
                    st.markdown('<div class="ss-mini-label">参数</div>', unsafe_allow_html=True)
                    st.markdown('<div class="ss-card-title">YAML</div>', unsafe_allow_html=True)
                    st.download_button("下载", param_path.read_bytes(), file_name="parameters.yaml", width="stretch")

        st.markdown('<div class="ss-quiet-rule"></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="ss-run-path">{state.get("run_dir")}</div>', unsafe_allow_html=True)

_render_footer(_active_state())
