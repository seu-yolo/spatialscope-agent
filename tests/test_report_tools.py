from spatialscope.tools.report_tools import generate_report


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

