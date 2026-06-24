from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from spatialscope.ui.components import render_report_assets
from spatialscope.ui.components.scene_frame import scene_frame
from spatialscope.ui.helpers import read_table_preview
from spatialscope.ui.run_restore import restore_latest_run_if_needed
from spatialscope.ui.v6_helpers import h
from spatialscope.utils.visual_priority import prioritize_visual_records


def _static_table(frame: pd.DataFrame) -> None:
    st.html(frame.to_html(index=False, classes="v6-static-table", border=0, escape=True))


def _review_key(finding: dict[str, Any], index: int) -> str:
    return str(finding.get("finding_id") or finding.get("title") or index)


def _render_finding(finding: dict[str, Any], index: int) -> None:
    review_state = st.session_state.setdefault("report_finding_review", {})
    key = _review_key(finding, index)
    status = review_state.get(key, "Review")
    evidence = ", ".join(map(str, finding.get("evidence_ids", []))) or "not available"
    support = "; ".join(map(str, finding.get("quantitative_support", [])[:3])) or "not available"
    caveat = " ".join(map(str, finding.get("caveats", [])[:2])) or "Interpret cautiously within the recorded evidence."
    st.markdown(
        f"""
        <article class="v6-finding">
          <div class="v6-finding-index">{index:02d}</div>
          <div>
            <h2>{h(finding.get("title", "Finding"))}</h2>
            <p class="v6-finding-statement">{h(finding.get("statement", ""))}</p>
            <dl>
              <dt>Quantitative support</dt><dd>{h(support)}</dd>
              <dt>Evidence IDs</dt><dd><code>{h(evidence)}</code></dd>
              <dt>Caveat</dt><dd>{h(caveat)}</dd>
              <dt>Review status</dt><dd>{h(status)}</dd>
            </dl>
          </div>
        </article>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns([0.58, 0.14, 0.14, 0.14], gap="small")
    cols[0].markdown("<div class='v7-review-label'>Review decision</div>", unsafe_allow_html=True)
    if cols[1].button("Accept", key=f"accept_{key}", width="stretch"):
        review_state[key] = "Accepted"
        st.rerun()
    if cols[2].button("Edit", key=f"edit_{key}", width="stretch"):
        review_state[key] = "Needs edit"
        st.rerun()
    if cols[3].button("Reject", key=f"reject_{key}", width="stretch"):
        review_state[key] = "Rejected"
        st.rerun()


def _render_figure_panel(fig: dict[str, Any]) -> None:
    path = Path(str(fig.get("path") or ""))
    st.markdown("<div class='v7-evidence-panel report'>", unsafe_allow_html=True)
    if path.exists():
        st.image(str(path), width="stretch")
    st.caption(str(fig.get("title") or path.name))
    caption = str(fig.get("caption") or "").strip()
    if caption:
        st.markdown(f"<p class='v6-limit'>{h(caption)}</p>", unsafe_allow_html=True)
    evidence_id = str(fig.get("evidence_id") or "").strip()
    if evidence_id:
        st.markdown(f"<p class='v6-limit'><code>{h(evidence_id)}</code></p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_main_evidence(state: dict[str, Any]) -> None:
    figures = prioritize_visual_records(list(state.get("generated_figures", []) or []))
    tables = list(state.get("generated_tables", []) or [])
    if not figures and not tables:
        st.info("还没有可展示的主证据。")
        return
    primary_figures = figures[:3]
    supporting_figures = figures[3:]
    if primary_figures:
        st.markdown("<h2 class='v6-report-section'>Primary visual evidence</h2>", unsafe_allow_html=True)
        st.caption("优先展示空间结构、UMAP 拓扑和请求基因表达；QC/HVG 等方法证据放在后面。")
        cols = st.columns(2, gap="medium")
        for col, fig in zip(cols, primary_figures[:2]):
            with col:
                _render_figure_panel(fig)
        if len(primary_figures) > 2:
            _render_figure_panel(primary_figures[2])
    if supporting_figures or tables:
        st.markdown("<h2 class='v6-report-section'>Supporting evidence</h2>", unsafe_allow_html=True)
    if supporting_figures:
        cols = st.columns(2, gap="medium")
        for index, fig in enumerate(supporting_figures[:4]):
            with cols[index % 2]:
                _render_figure_panel(fig)
    if tables:
        for table in tables[:2]:
            preview = read_table_preview(str(table.get("path") or ""), n=8)
            if preview is not None:
                st.caption(str(table.get("title") or table.get("path") or "table"))
                _static_table(preview)


def _render_methods_and_limits(state: dict[str, Any]) -> None:
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("<h2 class='v6-report-section'>Methods</h2>", unsafe_allow_html=True)
        trace = state.get("execution_trace", []) or []
        if trace:
            rows = [
                {
                    "step": item.get("tool") or item.get("node"),
                    "status": item.get("status"),
                    "summary": item.get("summary"),
                }
                for item in trace[:10]
            ]
            _static_table(pd.DataFrame(rows))
        else:
            st.write("No execution trace recorded.")
    with right:
        st.markdown("<h2 class='v6-report-section'>Limitations</h2>", unsafe_allow_html=True)
        limitations = list(map(str, state.get("warnings", []) or []))
        limitations.extend(["LLM 只基于工具摘要和 evidence packs 解释，不读取完整表达矩阵。"])
        for item in list(dict.fromkeys(limitations))[:5]:
            st.markdown(f"<p class='v6-limit'>· {h(item)}</p>", unsafe_allow_html=True)


def report_page() -> None:
    state = restore_latest_run_if_needed()
    if not state:
        st.markdown(
            """
            <div class="v6-empty-note">
              <h2>报告尚未生成</h2>
              <p>完成一次运行后，SpatialScope 会把 findings、证据和局限整理成可审阅报告。</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return
    if st.session_state.get("loaded_run_notice"):
        st.caption(str(st.session_state.get("loaded_run_notice")))
    brief = state.get("research_brief") if isinstance(state.get("research_brief"), dict) else {}
    question = brief.get("normalized_question") or state.get("user_query") or ""
    with scene_frame(
        key="report_scene",
        index="05 / 05",
        eyebrow="HUMAN-REVIEWED OUTPUT",
        title="Research Brief",
        subtitle=str(question),
    ):
        findings = list(state.get("scientific_findings", []) or [])[:5]
        st.markdown("<h2 class='v6-report-section'>Key findings</h2>", unsafe_allow_html=True)
        if findings:
            for index, finding in enumerate(findings, start=1):
                _render_finding(finding, index)
        else:
            st.info("还没有 evidence-linked findings。")
        draft_ids = set(map(str, st.session_state.get("report_draft_finding_ids", [])))
        draft_turns = [turn for turn in st.session_state.get("copilot_conversation", []) if str(turn.get("turn_id")) in draft_ids]
        if draft_turns:
            st.markdown("<h2 class='v6-report-section'>Copilot additions</h2>", unsafe_allow_html=True)
            for turn in draft_turns:
                st.markdown(
                    f"""
                    <article class="v6-finding copilot">
                      <div class="v6-finding-index">C</div>
                      <div>
                        <h2>{h(turn.get("question", ""))}</h2>
                        <p class="v6-finding-statement">{h(turn.get("content", ""))}</p>
                        <dl><dt>Evidence IDs</dt><dd><code>{h(", ".join(map(str, turn.get("evidence_ids", []))) or "none")}</code></dd></dl>
                      </div>
                    </article>
                    """,
                    unsafe_allow_html=True,
                )
        _render_main_evidence(state)
        _render_methods_and_limits(state)
        st.markdown("<h2 class='v6-report-section'>Downloads</h2>", unsafe_allow_html=True)
        render_report_assets(state, primary=True)
