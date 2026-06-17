import json

from spatialscope.tools.report_tools import generate_report
from spatialscope.utils.run_index import discover_runs


def test_generate_report_bundle(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "figures").mkdir(parents=True)
    (run_dir / "tables").mkdir()
    state = {
        "run_id": "run",
        "run_dir": str(run_dir),
        "user_query": "demo",
        "dataset_summary": {"n_obs": 1, "n_vars": 1},
        "approved_plan": [],
        "generated_figures": [],
        "generated_tables": [],
        "execution_trace": [],
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
    }
    result = generate_report(state)
    assert result.status == "success"
    assert (run_dir / "report.html").exists()
    assert (run_dir / "agent_trace.json").exists()
    assert (run_dir / "run_metadata.json").exists()
    assert (run_dir / "artifact_manifest.json").exists()
    assert (run_dir / "run_bundle.zip").exists()
    assert "Repair Diagnostics" in (run_dir / "report.html").read_text(encoding="utf-8")
    assert "Quality Gates" in (run_dir / "report.html").read_text(encoding="utf-8")
    metadata = json.loads((run_dir / "run_metadata.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert metadata["repair_log"][0]["tool"] == "run_svg"
    assert "quality" in metadata
    assert "quality" in manifest
    assert any(item["kind"] == "bundle" and item["exists"] for item in manifest["artifacts"])
    assert manifest["repairs_count"] == 1
    assert result.observations["run_bundle_path"].endswith("run_bundle.zip")
    assert result.observations["artifact_manifest_path"].endswith("artifact_manifest.json")


def test_discover_runs_reads_manifest(tmp_path):
    run_dir = tmp_path / "runs" / "run"
    (run_dir / "figures").mkdir(parents=True)
    (run_dir / "tables").mkdir()
    state = {
        "run_id": "run",
        "run_dir": str(run_dir),
        "mode": "quick",
        "user_query": "demo",
        "dataset_summary": {"n_obs": 1, "n_vars": 1},
        "approved_plan": [],
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
    assert runs[0]["bundle_path"].endswith("run_bundle.zip")
    assert runs[0]["complete"] is True
