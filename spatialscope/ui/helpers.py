from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from spatialscope.agent.planner import validate_plan_steps


MODE_LABELS = {"quick": "快速", "standard": "标准", "advanced": "高阶"}
MODE_VALUES = {"快速": "quick", "标准": "standard", "高阶": "advanced"}


def load_theme() -> None:
    css_path = Path(__file__).parent / "assets" / "theme.css"
    st.markdown(f"<style>{css_path.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def save_upload(uploaded: Any) -> str | None:
    if uploaded is None:
        return None
    upload_dir = Path("outputs/tmp/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved = upload_dir / uploaded.name
    saved.write_bytes(uploaded.getbuffer())
    return str(saved)


def parse_gene_text(text: str) -> list[str]:
    cleaned = text.replace("，", ",").replace(";", ",").replace("\n", ",")
    genes = [item.strip() for chunk in cleaned.split(",") for item in chunk.split() if item.strip()]
    seen: set[str] = set()
    return [gene for gene in genes if not (gene in seen or seen.add(gene))]


def plan_from_state(state: dict[str, Any]) -> list[dict[str, Any]]:
    return list(state.get("approved_plan") or state.get("task_plan") or [])


def plan_to_text(plan: list[dict[str, Any]]) -> str:
    return json.dumps(plan, ensure_ascii=False, indent=2)


def load_plan_from_text(text: str) -> list[dict[str, Any]]:
    payload = json.loads(text)
    if isinstance(payload, dict) and "steps" in payload:
        payload = payload["steps"]
    if not isinstance(payload, list):
        raise ValueError("Plan JSON must be a list of steps or an object with a `steps` field.")
    return validate_plan_steps(payload)


def apply_ui_overrides(
    state: dict[str, Any],
    *,
    min_genes: int,
    min_cells: int,
    max_mt_pct: float,
    resolution: float,
    gene_text: str,
    annotation_top_n: int,
) -> dict[str, Any]:
    genes = parse_gene_text(gene_text)
    plan: list[dict[str, Any]] = []
    for raw_step in plan_from_state(state):
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
    state["task_plan"] = plan
    state["approved_plan"] = plan
    state.setdefault("parameters", {}).update(
        {
            "qc": {"min_genes": min_genes, "min_cells": min_cells, "max_mt_pct": max_mt_pct},
            "clustering": {"resolution": resolution},
            "gene_panel_override": genes[:8],
            "cluster_annotation": {"top_n": annotation_top_n},
        }
    )
    return state


def read_table_preview(path: str | None, *, n: int = 8) -> pd.DataFrame | None:
    if not path:
        return None
    table_path = Path(path)
    if not table_path.exists() or table_path.suffix.lower() != ".csv":
        return None
    try:
        return pd.read_csv(table_path).head(n)
    except Exception:
        return None


def safe_json_download_payload(state: dict[str, Any]) -> str:
    public = {key: value for key, value in state.items() if not str(key).startswith("_") and key != "__interrupt__"}
    return json.dumps(public, ensure_ascii=False, indent=2, default=str)
