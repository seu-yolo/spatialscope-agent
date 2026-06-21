from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from spatialscope.ui.components import render_report_assets
from spatialscope.ui.helpers import read_table_preview
from spatialscope.ui.v6_helpers import h, render_dataset_identity_strip


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
    cols = st.columns([0.18, 0.18, 0.18, 0.46])
    if cols[0].button("Accept", key=f"accept_{key}"):
        review_state[key] = "Accepted"
        st.rerun()
    if cols[1].button("Edit", key=f"edit_{key}"):
        review_state[key] = "Needs edit"
        st.rerun()
    if cols[2].button("Reject", key=f"reject_{key}"):
        review_state[key] = "Rejected"
        st.rerun()


def _render_main_evidence(state: dict[str, Any]) -> None:
    figures = list(state.get("generated_figures", []) or [])
    tables = list(state.get("generated_tables", []) or [])
    if not figures and not tables:
        st.info("还没有可展示的主证据。")
        return
    if figures:
        st.markdown("<h2 class='v6-report-section'>Main evidence</h2>", unsafe_allow_html=True)
        cols = st.columns(2, gap="medium")
        for col, fig in zip(cols, figures[:2]):
            path = Path(str(fig.get("path") or ""))
            with col:
                if path.exists():
                    st.image(str(path), width="stretch")
                st.caption(str(fig.get("title") or path.name))
    if tables:
        st.markdown("<h2 class='v6-report-section'>Supporting evidence</h2>", unsafe_allow_html=True)
        for table in tables[:2]:
            preview = read_table_preview(str(table.get("path") or ""), n=8)
            if preview is not None:
                st.caption(str(table.get("title") or table.get("path") or "table"))
                _static_table(preview)


def _render_methods_and_limits(state: dict[str, Any]) -> None:
    st.markdown("<h2 class='v6-report-section'>Methods</h2>", unsafe_allow_html=True)
    trace = state.get("execution_trace", []) or []
    if trace:
        rows = [
            {
                "step": item.get("tool") or item.get("node"),
                "status": item.get("status"),
                "summary": item.get("summary"),
            }
            for item in trace[:12]
        ]
        _static_table(pd.DataFrame(rows))
    else:
        st.write("No execution trace recorded.")
    st.markdown("<h2 class='v6-report-section'>Limitations</h2>", unsafe_allow_html=True)
    limitations = list(map(str, state.get("warnings", []) or []))
    limitations.extend(["LLM 只基于工具摘要和 evidence packs 解释，不读取完整表达矩阵。"])
    for item in list(dict.fromkeys(limitations))[:5]:
        st.markdown(f"<p class='v6-limit'>· {h(item)}</p>", unsafe_allow_html=True)


def report_page() -> None:
    state = st.session_state.get("run_state")
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
    render_dataset_identity_strip(state)
    brief = state.get("research_brief") if isinstance(state.get("research_brief"), dict) else {}
    question = brief.get("normalized_question") or state.get("user_query") or ""
    st.markdown(
        f"""
        <main class="v6-report">
          <div class="v6-overline">Human-reviewed output</div>
          <h1>Research Brief</h1>
          <p class="v6-report-question">{h(question)}</p>
        </main>
        """,
        unsafe_allow_html=True,
    )
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
