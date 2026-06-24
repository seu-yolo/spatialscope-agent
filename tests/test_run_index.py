import json
import os

from spatialscope.ui.run_restore import latest_run_state
from spatialscope.utils.run_index import compare_run_summaries, load_run_state


def test_compare_run_summaries_reports_deltas_and_notes():
    left = {
        "run_id": "a",
        "mode": "advanced",
        "dataset_hash": "same",
        "plan_source": "llm",
        "llm_enabled": True,
        "complete": True,
        "figures": 8,
        "tables": 4,
        "trace_steps": 12,
        "status_success": 10,
        "status_failed": 1,
        "status_repaired": 1,
        "warnings": 2,
        "errors": 1,
        "repairs": 1,
        "quality_score": 78,
        "quality_status": "warn",
    }
    right = {
        "run_id": "b",
        "mode": "quick",
        "dataset_hash": "same",
        "plan_source": "rule_based",
        "llm_enabled": False,
        "complete": True,
        "figures": 5,
        "tables": 2,
        "trace_steps": 8,
        "status_success": 8,
        "status_failed": 0,
        "status_repaired": 0,
        "warnings": 0,
        "errors": 0,
        "repairs": 0,
        "quality_score": 100,
        "quality_status": "pass",
    }
    comparison = compare_run_summaries(left, right)
    assert comparison["same_dataset"] is True
    assert comparison["left_run_id"] == "a"
    assert comparison["right_run_id"] == "b"
    rows = {row["Metric"]: row for row in comparison["rows"]}
    assert rows["Figures"]["Delta A-B"] == 3
    assert rows["Errors"]["Delta A-B"] == 1
    assert rows["Quality score"]["Delta A-B"] == -22
    assert rows["Quality status"]["A"] == "warn"
    assert any("repair" in note.lower() for note in comparison["notes"])


def test_load_run_state_restores_public_state_without_raw_adata(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "report.html").write_text("<h1>report</h1>", encoding="utf-8")
    (run_dir / "dataset_card.json").write_text(
        json.dumps({"run_id": "run", "recommended_mode": "quick", "metrics": {"spatial": "yes"}}),
        encoding="utf-8",
    )
    trace = [{"node": "inspect_dataset", "tool": "load_h5ad", "status": "success", "warnings": [], "errors": []}]
    state = {
        "run_id": "run",
        "run_dir": "old/path",
        "report_path": None,
        "user_query": "demo",
        "dataset_hash": "abc123",
        "dataset_summary": {"n_obs": 10, "n_vars": 20, "has_spatial": True},
        "parameters": {"mode": "quick"},
        "approved_plan": [{"tool": "load_h5ad", "params": {}, "rationale": "inspect"}],
        "plan_source": "rule_based",
        "llm_enabled": False,
        "generated_figures": [{"path": str(run_dir / "figures" / "plot.png"), "title": "Plot"}],
        "generated_tables": [{"path": str(run_dir / "tables" / "table.csv"), "title": "Table"}],
        "execution_trace": [],
        "environment": {"python": "3.11"},
        "warnings": [],
        "errors": [],
        "_adata": "must not be restored",
    }
    (run_dir / "state_public.json").write_text(json.dumps(state), encoding="utf-8")
    (run_dir / "agent_trace.json").write_text(json.dumps(trace), encoding="utf-8")

    restored = load_run_state(run_dir)

    assert restored["run_id"] == "run"
    assert restored["run_dir"] == str(run_dir)
    assert restored["report_path"] == str(run_dir / "report.html")
    assert restored["execution_trace"] == trace
    assert restored["dataset_card"]["recommended_mode"] == "quick"
    assert restored["restored_from_bundle"] is True
    assert restored["loaded_from_run_dir"] == str(run_dir)
    assert "_adata" not in restored
    assert "adata" not in restored


def test_load_run_state_supports_legacy_metadata_manifest(tmp_path):
    run_dir = tmp_path / "legacy"
    (run_dir / "figures").mkdir(parents=True)
    (run_dir / "tables").mkdir()
    figure = run_dir / "figures" / "spatial.png"
    table = run_dir / "tables" / "summary.csv"
    report = run_dir / "report.html"
    figure.write_text("png", encoding="utf-8")
    table.write_text("x,y\n1,2\n", encoding="utf-8")
    report.write_text("<h1>legacy</h1>", encoding="utf-8")
    metadata = {
        "run_id": "legacy",
        "dataset_hash": "hash",
        "dataset_summary": {"n_obs": 3, "n_vars": 4},
        "environment": {"python": "3.11"},
        "parameters": {"mode": "standard"},
        "approved_plan": [{"tool": "qc_summary", "params": {}, "rationale": "QC"}],
        "plan_source": "llm",
        "llm_enabled": True,
    }
    manifest = {
        "run_id": "legacy",
        "mode": "standard",
        "query": "legacy query",
        "dataset_hash": "hash",
        "plan_source": "llm",
        "llm_enabled": True,
        "artifacts": [
            {"kind": "report", "path": str(report), "title": "HTML report", "exists": True},
            {"kind": "figure", "path": str(figure), "title": "Spatial", "exists": True},
            {"kind": "table", "path": str(table), "title": "Summary", "exists": True},
        ],
    }
    trace = [{"node": "qc", "tool": "qc_summary", "status": "success"}]
    (run_dir / "run_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (run_dir / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (run_dir / "agent_trace.json").write_text(json.dumps(trace), encoding="utf-8")

    restored = load_run_state(run_dir)

    assert restored["run_id"] == "legacy"
    assert restored["mode"] == "standard"
    assert restored["user_query"] == "legacy query"
    assert restored["llm_enabled"] is True
    assert restored["generated_figures"][0]["path"] == str(figure)
    assert restored["generated_tables"][0]["path"] == str(table)
    assert restored["execution_trace"] == trace
    assert restored["quality"]["overall_status"] in {"pass", "warn", "fail"}


def test_latest_run_state_restores_most_recent_report_run(tmp_path):
    outdir = tmp_path / "runs"
    older = outdir / "older"
    newer = outdir / "newer"
    for run_dir, run_id in [(older, "older"), (newer, "newer")]:
        run_dir.mkdir(parents=True)
        (run_dir / "report.html").write_text("<h1>report</h1>", encoding="utf-8")
        (run_dir / "state_public.json").write_text(
            json.dumps({"run_id": run_id, "user_query": run_id, "parameters": {"mode": "quick"}}),
            encoding="utf-8",
        )
        (run_dir / "agent_trace.json").write_text(json.dumps([{"node": "report", "status": "success"}]), encoding="utf-8")

    for path in older.rglob("*"):
        if path.is_file():
            os.utime(path, (1000, 1000))
    for path in newer.rglob("*"):
        if path.is_file():
            os.utime(path, (2000, 2000))

    restored = latest_run_state(str(outdir))

    assert restored is not None
    assert restored["run_id"] == "newer"
