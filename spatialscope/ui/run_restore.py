from __future__ import annotations

from typing import Any

import streamlit as st

from spatialscope.ui.helpers import plan_from_state, plan_to_text
from spatialscope.ui.state import set_run
from spatialscope.utils.run_index import discover_runs, load_run_state


def latest_run_state(outdir: str = "outputs/runs") -> dict[str, Any] | None:
    for run in discover_runs(outdir, limit=6):
        if not run.get("report_path"):
            continue
        run_dir = str(run.get("run_dir") or "")
        if not run_dir:
            continue
        try:
            return load_run_state(run_dir)
        except Exception:
            continue
    return None


def restore_latest_run_if_needed(outdir: str = "outputs/runs") -> dict[str, Any] | None:
    existing = st.session_state.get("run_state")
    if existing:
        return existing
    loaded = latest_run_state(outdir)
    if loaded is None:
        return None
    set_run(loaded)
    st.session_state.plan_text = plan_to_text(plan_from_state(loaded))
    st.session_state.loaded_run_notice = f"已自动载入最近运行：{loaded.get('run_id') or 'unknown'}"
    return loaded
