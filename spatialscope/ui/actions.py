from __future__ import annotations

from typing import Any

import streamlit as st

from spatialscope.domain.evidence import UIAction


def ensure_explore_state() -> None:
    defaults = {
        "explore_view_mode": "Gene expression",
        "selected_gene": "Pou5f1",
        "resolved_gene": "",
        "selected_cluster": "",
        "selected_obs_ids": [],
        "expression_source": "spatialscope_interpretation",
        "clip_low": 1.0,
        "clip_high": 99.0,
        "point_size": 8,
        "active_evidence_ids": [],
        "copilot_conversation": [],
        "report_draft_finding_ids": [],
        "open_marker_table": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value.copy() if isinstance(value, list) else value)


def apply_ui_action(action_payload: dict[str, Any] | UIAction) -> str:
    action = action_payload if isinstance(action_payload, UIAction) else UIAction.model_validate(action_payload)
    if action.type in {"set_gene", "compare_gene"}:
        gene = str(action.payload.get("gene") or action.payload.get("value") or "").strip()
        if gene:
            st.session_state.pending_selected_gene = gene
            st.session_state.pending_explore_view_mode = "Gene expression"
            return f"已切换基因：{gene}"
    if action.type == "highlight_cluster":
        cluster = str(action.payload.get("cluster") or action.payload.get("value") or "").strip()
        if cluster:
            st.session_state.selected_cluster = cluster
            st.session_state.pending_explore_view_mode = "Cluster"
            return f"已高亮 cluster：{cluster}"
    if action.type == "set_expression_source":
        source = str(action.payload.get("source") or action.payload.get("value") or "").strip()
        if source:
            st.session_state.expression_source = source
            return f"已切换表达来源：{source}"
    if action.type == "select_observations":
        obs_ids = [str(item) for item in action.payload.get("obs_ids", []) if str(item)]
        st.session_state.selected_obs_ids = obs_ids[:200]
        return f"已选择 {len(st.session_state.selected_obs_ids)} 个 observations"
    if action.type == "clear_selection":
        st.session_state.selected_obs_ids = []
        return "已清除选择"
    if action.type == "open_marker_table":
        st.session_state.open_marker_table = True
        return "已打开 marker evidence"
    if action.type == "add_finding_to_report":
        finding_id = str(action.payload.get("finding_id") or action.payload.get("value") or "copilot_finding")
        ids = list(st.session_state.get("report_draft_finding_ids", []))
        if finding_id not in ids:
            ids.append(finding_id)
        st.session_state.report_draft_finding_ids = ids
        return "已加入报告草稿"
    return f"暂不支持动作：{action.type}"
