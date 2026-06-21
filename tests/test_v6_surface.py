from __future__ import annotations

from pathlib import Path

from spatialscope.ui.landing_preview import ensure_landing_preview
from spatialscope.ui.v6_helpers import (
    PROMPT_SUGGESTIONS,
    dataset_identity,
    dataset_identity_text,
    resolved_genes_for_state,
    state_has_plan,
    state_has_report,
)


def _state() -> dict:
    return {
        "data_path": "data/demo_embryo.h5ad",
        "mode": "standard",
        "dataset_summary": {
            "n_obs": 240,
            "n_vars": 80,
            "has_spatial": True,
            "matrix_state": "count_like",
        },
        "observations": {"resolved_genes": ["Sox17", "T", "Mesp1"]},
        "task_plan": [{"id": "qc", "tool": "run_qc", "params": {}, "rationale": "QC"}],
    }


def test_prompt_suggestions_are_actionable_research_questions():
    assert 3 <= len(PROMPT_SUGGESTIONS) <= 4
    assert "查看基因空间表达" in PROMPT_SUGGESTIONS
    assert "Sox17" in PROMPT_SUGGESTIONS["查看基因空间表达"]
    assert all(len(text) > 20 for text in PROMPT_SUGGESTIONS.values())


def test_dataset_identity_formatter_uses_actual_dataset_facts():
    ident = dataset_identity(_state())
    assert ident["name"] == "demo_embryo.h5ad"
    assert ident["n_obs"] == 240
    assert ident["has_spatial"] is True
    assert "240 spots" in dataset_identity_text(_state())
    assert "spatial ✓" in dataset_identity_text(_state())


def test_page_state_helpers_gate_plan_and_report_surfaces():
    state = _state()
    assert state_has_plan(state) is True
    assert state_has_report(state) is False
    state["report_path"] = "outputs/runs/demo/report.html"
    assert state_has_report(state) is True


def test_agent_message_gene_list_comes_from_state():
    assert resolved_genes_for_state(_state()) == ["Sox17", "T", "Mesp1"]


def test_v6_preview_asset_exists_and_replaces_abstract_svg():
    paths = ensure_landing_preview()
    assert paths["png"].exists()
    assert paths["png"].stat().st_size > 10_000
    components = Path("spatialscope/ui/components.py").read_text(encoding="utf-8")
    assert "def atlas_svg" not in components
