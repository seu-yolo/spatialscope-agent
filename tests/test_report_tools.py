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
    }
    result = generate_report(state)
    assert result.status == "success"
    assert (run_dir / "report.html").exists()
    assert (run_dir / "agent_trace.json").exists()
    assert (run_dir / "run_metadata.json").exists()
    assert (run_dir / "artifact_manifest.json").exists()
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
    }
    generate_report(state)
    runs = discover_runs(tmp_path / "runs")
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run"
    assert runs[0]["mode"] == "quick"
    assert runs[0]["trace_steps"] == 1
    assert runs[0]["complete"] is True
