import json
import zipfile

from spatialscope.tools.report_tools import generate_report
from spatialscope.tools.registry import list_tool_contracts
from spatialscope.utils.run_index import discover_runs


def test_generate_report_bundle(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "figures").mkdir(parents=True)
    (run_dir / "tables").mkdir()
    state = {
        "run_id": "run",
        "run_dir": str(run_dir),
        "data_path": "data/demo_tiny.h5ad",
        "user_query": "demo",
        "dataset_summary": {"n_obs": 1, "n_vars": 1},
        "approved_plan": [{"tool": "run_qc", "params": {}, "rationale": "QC"}],
        "tool_contracts": list_tool_contracts(),
        "generated_figures": [],
        "generated_tables": [],
        "execution_trace": [{"node": "execute_tool", "tool": "run_qc", "status": "success"}],
        "parameters": {"mode": "quick"},
        "environment": {},
        "final_answer": "done",
        "repair_log": [
            {
                "tool": "run_svg",
                "category": "missing_dependency",
                "action": "skip_optional_step",
                "likely_cause": "Squidpy is unavailable.",
                "recommended_actions": ["Install squidpy."],
            }
        ],
        "review_notes": {
            "schema_version": "1.0",
            "run_id": "run",
            "decision": "accepted_with_caveats",
            "decision_label": "Accepted with caveats",
            "confidence": "medium",
            "confidence_label": "Medium",
            "reviewer": "Reviewer",
            "tags": ["demo"],
            "notes": "Review note.",
            "limitations": "Demo data only.",
            "quality_gate_overrides": [
                {
                    "gate_name": "Evidence outputs",
                    "original_status": "warn",
                    "original_score": 65,
                    "decision": "requires_rerun",
                    "decision_label": "Requires rerun",
                    "rationale": "Need marker evidence before final interpretation.",
                    "reviewer": "Reviewer",
                    "updated_at": "2026-06-18T03:31:00",
                }
            ],
            "updated_at": "2026-06-18T03:30:00",
        },
    }
    result = generate_report(state)
    assert result.status == "success"
    assert (run_dir / "report.html").exists()
    assert (run_dir / "dataset_card.html").exists()
    assert (run_dir / "dataset_card.json").exists()
    assert (run_dir / "DATASET_CARD.md").exists()
    assert (run_dir / "agent_trace.json").exists()
    assert (run_dir / "run_metadata.json").exists()
    assert (run_dir / "artifact_manifest.json").exists()
    assert (run_dir / "storyboard.html").exists()
    assert (run_dir / "storyboard.json").exists()
    assert (run_dir / "rerun_recipe.json").exists()
    assert (run_dir / "RERUN.md").exists()
    assert (run_dir / "rerun.sh").exists()
    assert (run_dir / "agent_audit.json").exists()
    assert (run_dir / "artifact_audit.json").exists()
    assert (run_dir / "run_bundle.zip").exists()
    assert (run_dir / "README.md").exists()
    assert (run_dir / "review_notes.json").exists()
    readme_text = (run_dir / "README.md").read_text(encoding="utf-8")
    assert "SpatialScope Run README" in readme_text
    assert "Human Review" in readme_text
    assert "Quality Gates" in readme_text
    assert "Dataset Card" in readme_text
    assert "Rerun recipe" in readme_text
    report_text = (run_dir / "report.html").read_text(encoding="utf-8")
    assert "SpatialScope Agent Research Brief" in report_text
    assert "Key Findings" in report_text
    assert "Evidence Packs" in report_text
    assert "Repair Diagnostics" in report_text
    assert "Quality Gates" not in report_text
    assert "Agent Audit" not in report_text
    metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert metadata["repair_log"][0]["tool"] == "run_svg"
    assert "evidence_packs" in metadata
    assert "scientific_findings" in metadata
    assert metadata["review_notes"]["decision"] == "accepted_with_caveats"
    assert metadata["review_notes"]["quality_gate_overrides"][0]["gate_name"] == "Evidence outputs"
    assert "quality" in metadata
    assert "agent_audit" in metadata
    assert "dataset_card" in metadata
    assert "storyboard" in metadata
    assert "rerun_recipe" in metadata
    assert metadata["query"] == "demo"
    assert metadata["data_path"] == "data/demo_tiny.h5ad"
    assert "quality" in manifest
    assert "agent_audit" in manifest
    assert "dataset_card" in manifest
    assert "storyboard" in manifest
    assert "rerun_recipe" in manifest
    assert any(item["kind"] == "review" and item["exists"] for item in manifest["artifacts"])
    assert any(item["kind"] == "readme" and item["exists"] for item in manifest["artifacts"])
    assert any(item["kind"] == "dataset_card" and item["exists"] for item in manifest["artifacts"])
    assert any(item["kind"] == "dataset_card_data" and item["exists"] for item in manifest["artifacts"])
    assert any(item["kind"] == "dataset_card_markdown" and item["exists"] for item in manifest["artifacts"])
    assert any(item["kind"] == "storyboard" and item["exists"] for item in manifest["artifacts"])
    assert any(item["kind"] == "storyboard_data" and item["exists"] for item in manifest["artifacts"])
    assert any(item["kind"] == "rerun_recipe" and item["exists"] for item in manifest["artifacts"])
    assert any(item["kind"] == "rerun_markdown" and item["exists"] for item in manifest["artifacts"])
    assert any(item["kind"] == "rerun_script" and item["exists"] for item in manifest["artifacts"])
    assert any(item["kind"] == "agent_audit" and item["exists"] for item in manifest["artifacts"])
    assert any(item["kind"] == "artifact_audit" and item["exists"] for item in manifest["artifacts"])
    assert any(item["kind"] == "bundle" and item["exists"] for item in manifest["artifacts"])
    assert manifest["repairs_count"] == 1
    assert result.observations["run_bundle_path"].endswith("run_bundle.zip")
    assert result.observations["run_readme_path"].endswith("README.md")
    assert result.observations["dataset_card_path"].endswith("dataset_card.html")
    assert result.observations["dataset_card_json_path"].endswith("dataset_card.json")
    assert result.observations["dataset_card_markdown_path"].endswith("DATASET_CARD.md")
    assert result.observations["storyboard_path"].endswith("storyboard.html")
    assert result.observations["storyboard_json_path"].endswith("storyboard.json")
    assert result.observations["rerun_recipe_path"].endswith("rerun_recipe.json")
    assert result.observations["rerun_markdown_path"].endswith("RERUN.md")
    assert result.observations["rerun_script_path"].endswith("rerun.sh")
    assert result.observations["agent_audit_path"].endswith("agent_audit.json")
    assert result.observations["artifact_audit_path"].endswith("artifact_audit.json")
    assert result.observations["artifact_manifest_path"].endswith("artifact_manifest.json")
    with zipfile.ZipFile(run_dir / "run_bundle.zip") as archive:
        assert "README.md" in archive.namelist()
        assert "dataset_card.html" in archive.namelist()
        assert "dataset_card.json" in archive.namelist()
        assert "DATASET_CARD.md" in archive.namelist()
        assert "storyboard.html" in archive.namelist()
        assert "storyboard.json" in archive.namelist()
        assert "rerun_recipe.json" in archive.namelist()
        assert "RERUN.md" in archive.namelist()
        assert "rerun.sh" in archive.namelist()
        assert "agent_audit.json" in archive.namelist()
        assert "artifact_audit.json" in archive.namelist()


def test_discover_runs_reads_manifest(tmp_path):
    run_dir = tmp_path / "runs" / "run"
    (run_dir / "figures").mkdir(parents=True)
    (run_dir / "tables").mkdir()
    state = {
        "run_id": "run",
        "run_dir": str(run_dir),
        "data_path": "data/demo_tiny.h5ad",
        "mode": "quick",
        "user_query": "demo",
        "dataset_summary": {"n_obs": 1, "n_vars": 1},
        "approved_plan": [{"tool": "run_qc", "params": {}, "rationale": "QC"}],
        "tool_contracts": list_tool_contracts(),
        "generated_figures": [],
        "generated_tables": [],
        "execution_trace": [{"status": "success", "node": "x", "tool": "y"}],
        "parameters": {"mode": "quick"},
        "environment": {},
        "final_answer": "done",
        "warnings": [],
        "errors": [],
        "repair_log": [
            {
                "tool": "plot_spatial",
                "category": "missing_spatial_coordinates",
                "action": "skip_failed_step",
                "likely_cause": "No spatial coordinates.",
                "recommended_actions": ["Use spatial AnnData."],
            }
        ],
    }
    generate_report(state)
    runs = discover_runs(tmp_path / "runs")
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run"
    assert runs[0]["mode"] == "quick"
    assert runs[0]["trace_steps"] == 1
    assert runs[0]["repairs"] == 1
    assert runs[0]["status_success"] == 1
    assert "quality_score" in runs[0]
    assert "quality_status" in runs[0]
    assert "agent_audit_score" in runs[0]
    assert "agent_audit_status" in runs[0]
    assert "storyboard_cards" in runs[0]
    assert runs[0]["dataset_card_path"].endswith("dataset_card.html")
    assert runs[0]["dataset_card_json_path"].endswith("dataset_card.json")
    assert runs[0]["dataset_card_markdown_path"].endswith("DATASET_CARD.md")
    assert runs[0]["dataset_recommended_mode"] == "quick"
    assert runs[0]["storyboard_path"].endswith("storyboard.html")
    assert runs[0]["storyboard_json_path"].endswith("storyboard.json")
    assert runs[0]["rerun_recipe_path"].endswith("rerun_recipe.json")
    assert runs[0]["rerun_markdown_path"].endswith("RERUN.md")
    assert runs[0]["rerun_script_path"].endswith("rerun.sh")
    assert runs[0]["agent_audit_path"].endswith("agent_audit.json")
    assert runs[0]["audit_path"].endswith("artifact_audit.json")
    assert runs[0]["readme_path"].endswith("README.md")
    assert runs[0]["bundle_path"].endswith("run_bundle.zip")
    assert runs[0]["complete"] is True


def test_report_html_prioritizes_primary_visual_evidence(tmp_path):
    run_dir = tmp_path / "visual_run"
    figures_dir = run_dir / "figures"
    figures_dir.mkdir(parents=True)
    for name in [
        "qc_metrics.png",
        "highly_variable_genes.png",
        "gene_panel_spatial.png",
        "umap_leiden.png",
        "spatial_leiden.png",
    ]:
        (figures_dir / name).write_bytes(b"png")
    state = {
        "run_id": "visual_run",
        "run_dir": str(run_dir),
        "data_path": "data/demo_tiny.h5ad",
        "mode": "standard",
        "user_query": "demo",
        "dataset_summary": {"n_obs": 10, "n_vars": 20, "has_spatial": True},
        "approved_plan": [],
        "tool_contracts": list_tool_contracts(),
        "generated_figures": [
            {"title": "QC metric distributions", "path": str(figures_dir / "qc_metrics.png")},
            {"title": "Highly variable genes", "path": str(figures_dir / "highly_variable_genes.png")},
            {"title": "Gene Panel Spatial View", "path": str(figures_dir / "gene_panel_spatial.png")},
            {"title": "UMAP by leiden", "path": str(figures_dir / "umap_leiden.png")},
            {"title": "Spatial view: leiden", "path": str(figures_dir / "spatial_leiden.png")},
        ],
        "generated_tables": [],
        "execution_trace": [],
        "parameters": {"mode": "standard"},
        "environment": {},
        "final_answer": "done",
        "repair_log": [],
    }

    result = generate_report(state)

    assert result.status == "success"
    html = (run_dir / "report.html").read_text(encoding="utf-8")
    visual_index = html.index("Visual Evidence")
    spatial_index = html.index("Spatial view: leiden")
    umap_index = html.index("UMAP by leiden")
    gene_index = html.index("Gene Panel Spatial View")
    qc_index = html.index("QC metric distributions")
    assert visual_index < spatial_index < umap_index < gene_index < qc_index
