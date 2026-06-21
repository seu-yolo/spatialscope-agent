from __future__ import annotations

import html
from datetime import datetime
from typing import Any

import streamlit as st

from spatialscope.ui.helpers import apply_ui_overrides, plan_from_state
from spatialscope.ui.state import runtime


NODE_LABELS = {
    "parse_request": "LLM 已解析研究问题",
    "inspect_dataset": "数据集检查完成",
    "plan_analysis": "分析方案已生成",
    "review_plan": "分析方案已批准",
    "execute_tool": "正在执行分析工具",
    "validate_result": "正在验证工具结果",
    "repair_or_continue": "正在执行澄清/修复策略",
    "interpret": "正在合成证据解释",
    "report": "正在生成可复现报告",
    "generate_report": "正在写出 HTML report",
}


def prepare_state(
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


def _event_time() -> str:
    return datetime.now().strftime("%H:%M:%S")


def timeline_items(state: dict[str, Any] | None, *, live_node: str | None = None) -> list[dict[str, Any]]:
    if not state:
        return []
    items: list[dict[str, Any]] = []
    summary = state.get("dataset_summary") or {}
    if summary:
        items.append(
            {
                "time": _event_time(),
                "status": "done",
                "title": "数据集检查完成",
                "detail": f"{summary.get('n_obs', 'NA')} observations · {summary.get('n_vars', 'NA')} genes",
            }
        )
    if state.get("research_brief"):
        items.append(
            {
                "time": _event_time(),
                "status": "done",
                "title": "研究问题已结构化",
                "detail": "ResearchBrief schema validated",
            }
        )
    if state.get("approved_plan"):
        items.append(
            {
                "time": _event_time(),
                "status": "done",
                "title": "分析方案已批准",
                "detail": f"{len(state.get('approved_plan') or [])} steps",
            }
        )
    elif state.get("task_plan"):
        items.append(
            {
                "time": _event_time(),
                "status": "pending",
                "title": "分析方案等待批准",
                "detail": f"{len(state.get('task_plan') or [])} steps prepared",
            }
        )

    for record in state.get("execution_trace", []) or []:
        status_raw = str(record.get("status") or "success")
        status = "failed" if status_raw == "failed" else "done" if status_raw in {"success", "success_after_retry", "skipped", "skipped_optional"} else "active"
        tool = str(record.get("tool") or record.get("node") or "step")
        summary_text = str(record.get("summary") or "")
        items.append(
            {
                "time": _event_time(),
                "status": status,
                "title": tool.replace("_", " "),
                "detail": summary_text,
            }
        )
    if live_node:
        items.append(
            {
                "time": _event_time(),
                "status": "active",
                "title": NODE_LABELS.get(live_node, live_node),
                "detail": "LangGraph event streaming",
            }
        )
    if state.get("report_path"):
        items.append(
            {
                "time": _event_time(),
                "status": "done",
                "title": "分析完成",
                "detail": (
                    f"{len(state.get('execution_trace', []) or [])} events · "
                    f"{len(state.get('generated_figures', []) or [])} figures · "
                    f"{len(state.get('generated_tables', []) or [])} tables"
                ),
            }
        )
    return items


def render_timeline(state: dict[str, Any] | None, *, live_node: str | None = None) -> None:
    items = timeline_items(state, live_node=live_node)
    if not items:
        st.info("还没有运行事件。批准方案后，LangGraph 节点会在这里实时出现。")
        return
    rows = []
    for item in items:
        status = item["status"]
        symbol = "✓" if status == "done" else "!" if status == "failed" else "●" if status == "active" else "○"
        rows.append(
            f"""
            <div class="v6-timeline-item {status}">
              <div class="v6-timeline-time">{html.escape(str(item["time"]))}</div>
              <div class="v6-timeline-mark">{symbol}</div>
              <div>
                <div class="v6-timeline-title">{html.escape(str(item["title"]))}</div>
                <div class="v6-timeline-detail">{html.escape(str(item["detail"]))}</div>
              </div>
            </div>
            """
        )
    st.html(f"<div class='v6-timeline'>{''.join(rows)}</div>")


def render_current_step(state: dict[str, Any] | None, *, live_node: str | None = None) -> None:
    if not state:
        st.markdown("<div class='v6-current-step'>等待方案批准</div>", unsafe_allow_html=True)
        return
    record = (state.get("execution_trace") or [{}])[-1] if state.get("execution_trace") else {}
    title = NODE_LABELS.get(live_node or "", "") or str(record.get("tool") or state.get("current_step") or "准备运行")
    params = record.get("params") or {}
    outputs = []
    if state.get("generated_figures"):
        outputs.append(f"{len(state.get('generated_figures', []))} figures")
    if state.get("generated_tables"):
        outputs.append(f"{len(state.get('generated_tables', []))} tables")
    detail = str(record.get("summary") or "等待下一个 LangGraph 节点。")
    param_rows = "".join(
        f"<li><code>{html.escape(str(key))}</code> = {html.escape(str(value))}</li>"
        for key, value in list(params.items())[:8]
    )
    st.markdown(
        f"""
        <aside class="v6-current-step">
          <div class="v6-overline">当前步骤</div>
          <h3>{html.escape(str(title))}</h3>
          <p>{html.escape(str(detail))}</p>
          <div class="v6-current-subtitle">参数</div>
          <ul>{param_rows or "<li>暂无公开参数</li>"}</ul>
          <div class="v6-current-subtitle">输出</div>
          <p>{html.escape(' · '.join(outputs) if outputs else '等待工具产物')}</p>
        </aside>
        """,
        unsafe_allow_html=True,
    )


def stream_approved(
    state: dict[str, Any],
    *,
    plan_source: str = "user_edited",
    timeline_slot: Any | None = None,
    current_slot: Any | None = None,
    interrupt_slot: Any | None = None,
) -> dict[str, Any]:
    plan = plan_from_state(state)
    thread_id = str(state.get("thread_id") or state.get("run_id"))
    timeline_slot = timeline_slot or st.empty()
    current_slot = current_slot or st.empty()
    interrupt_slot = interrupt_slot or st.empty()
    final_state = dict(state)

    with timeline_slot.container():
        render_timeline(final_state, live_node="review_plan")
    with current_slot.container():
        render_current_step(final_state, live_node="review_plan")

    for update in runtime().stream_resume(thread_id, approved_plan=plan, plan_source=plan_source):
        snapshot = runtime().state_snapshot(thread_id)
        values = dict(getattr(snapshot, "values", {}) or {})
        if values:
            final_state = values
        node_names = list(update.keys()) if isinstance(update, dict) else ["graph_event"]
        live_node = node_names[-1] if node_names else "graph_event"
        with timeline_slot.container():
            render_timeline(final_state, live_node=live_node)
        with current_slot.container():
            render_current_step(final_state, live_node=live_node)
        if final_state.get("clarification_items"):
            with interrupt_slot.container():
                st.warning("需要人工确认：" + str(final_state["clarification_items"][-1].get("message", "Clarification required.")))

    snapshot = runtime().state_snapshot(thread_id)
    values = dict(getattr(snapshot, "values", {}) or {})
    return values or final_state
