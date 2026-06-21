from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import streamlit as st

from spatialscope.agent.llm import llm_config_status
from spatialscope.ui.helpers import MODE_LABELS, plan_from_state


PROMPT_SUGGESTIONS = {
    "QC + 聚类": "检查这个早期小鼠胚胎空间数据的质量，完成标准预处理、UMAP 和 Leiden 聚类，并总结主要质量边界。",
    "查看基因空间表达": "查看 Sox17、T 和 Mesp1 的空间表达，比较它们在空间结构和 UMAP 聚类中的差异。",
    "寻找空间可变基因": "寻找空间可变基因，说明哪些信号具有空间结构，并给出证据和局限。",
    "比较空间结构与 UMAP": "比较空间坐标中的区域结构与 UMAP 聚类是否一致，并指出可能的解释风险。",
}


def h(text: Any) -> str:
    return html.escape(str(text))


def llm_surface_label() -> str:
    try:
        status = llm_config_status()
    except Exception:
        return "Rule mode"
    if status.get("enabled") and status.get("active_mode") == "full":
        return "LLM active"
    if status.get("enabled") and status.get("active_mode") == "auto":
        return "LLM auto"
    return "Rule mode"


def dataset_identity(state: dict[str, Any] | None) -> dict[str, Any]:
    if not state:
        return {}
    summary = state.get("dataset_summary") or {}
    profile = state.get("dataset_profile") or summary.get("dataset_profile") or {}
    path = Path(str(state.get("data_path") or state.get("adata_path") or "dataset.h5ad"))
    matrix_state = summary.get("matrix_state") or profile.get("matrix_state") or "unknown expression"
    return {
        "name": path.name,
        "n_obs": summary.get("n_obs", profile.get("n_obs", "NA")),
        "n_vars": summary.get("n_vars", profile.get("n_vars", "NA")),
        "has_spatial": bool(summary.get("has_spatial", profile.get("has_spatial", False))),
        "matrix_state": matrix_state,
        "mode": MODE_LABELS.get(str(state.get("mode") or "standard"), str(state.get("mode") or "standard")),
        "organism": profile.get("organism") or summary.get("organism") or "",
        "stage": profile.get("development_stage") or summary.get("development_stage") or "",
    }


def dataset_identity_text(state: dict[str, Any] | None) -> str:
    ident = dataset_identity(state)
    if not ident:
        return "尚未检查数据"
    spatial = "spatial ✓" if ident.get("has_spatial") else "spatial unavailable"
    return (
        f"{ident.get('n_obs')} spots · {ident.get('n_vars')} genes · "
        f"{spatial} · {ident.get('matrix_state')}"
    )


def render_dataset_identity_strip(state: dict[str, Any]) -> None:
    ident = dataset_identity(state)
    st.markdown(
        f"""
        <div class="v6-dataset-strip">
          <div>
            <div class="v6-overline">Dataset inspected</div>
            <div class="v6-dataset-name">{h(ident.get("name", "dataset.h5ad"))}</div>
          </div>
          <div class="v6-dataset-facts">{h(dataset_identity_text(state))}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def state_has_plan(state: dict[str, Any] | None) -> bool:
    return bool(state and plan_from_state(state))


def state_has_report(state: dict[str, Any] | None) -> bool:
    return bool(state and state.get("report_path"))


def compact_list(items: list[Any], *, limit: int = 6, empty: str = "none") -> str:
    values = [str(item).strip() for item in items if str(item).strip()]
    if not values:
        return empty
    return "、".join(values[:limit])


def resolved_genes_for_state(state: dict[str, Any]) -> list[str]:
    observations = state.get("observations") or {}
    genes = list(map(str, observations.get("resolved_genes", []) or []))
    brief = state.get("research_brief") if isinstance(state.get("research_brief"), dict) else {}
    genes.extend(list(map(str, brief.get("requested_genes", []) or [])))
    return list(dict.fromkeys([gene for gene in genes if gene and gene.lower() != "none"]))


def analyses_for_state(state: dict[str, Any]) -> list[str]:
    brief = state.get("research_brief") if isinstance(state.get("research_brief"), dict) else {}
    analyses = list(map(str, brief.get("requested_analyses", []) or []))
    if analyses:
        return analyses
    tools = [str(step.get("tool")) for step in plan_from_state(state)]
    return [tool.replace("_", " ") for tool in tools]


def render_page_lede(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="v6-page-lede">
          <h1>{h(title)}</h1>
          <p>{h(body)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def set_prompt_from_suggestion(label: str) -> None:
    st.session_state.research_question = PROMPT_SUGGESTIONS[label]
