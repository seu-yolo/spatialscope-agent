import json

from spatialscope.utils.artifact_audit import audit_artifacts, format_bytes, write_artifact_audit


def test_format_bytes_scales_units():
    assert format_bytes(0) == "0 B"
    assert format_bytes(512) == "512 B"
    assert format_bytes(2048) == "2.0 KB"


def test_artifact_audit_counts_existing_and_missing(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    report = run_dir / "report.html"
    report.write_text("<h1>report</h1>", encoding="utf-8")
    manifest = {
        "run_id": "run",
        "artifacts": [
            {"kind": "report", "title": "Report", "path": str(report), "relpath": "report.html"},
            {"kind": "table", "title": "Missing table", "path": str(run_dir / "missing.csv"), "relpath": "missing.csv"},
        ],
    }
    (run_dir / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    audit = write_artifact_audit(run_dir)

    assert audit["run_id"] == "run"
    assert audit["artifacts_count"] == 2
    assert audit["existing_count"] == 1
    assert audit["missing_count"] == 1
    assert audit["complete"] is False
    assert audit["kinds"]["report"] == 1
    assert (run_dir / "artifact_audit.json").exists()

    loaded = audit_artifacts(run_dir)
    assert loaded["missing"][0]["relpath"] == "missing.csv"


def test_artifact_audit_accepts_manifest_paths_relative_to_cwd(tmp_path, monkeypatch):
    project = tmp_path / "project"
    run_dir = project / "outputs" / "runs" / "run"
    run_dir.mkdir(parents=True)
    report = run_dir / "report.html"
    report.write_text("<h1>report</h1>", encoding="utf-8")
    monkeypatch.chdir(project)
    manifest = {
        "run_id": "run",
        "artifacts": [
            {
                "kind": "report",
                "title": "Report",
                "path": "outputs/runs/run/report.html",
                "relpath": "report.html",
            }
        ],
    }
    (run_dir / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    audit = audit_artifacts(run_dir)

    assert audit["existing_count"] == 1
    assert audit["missing_count"] == 0
    assert audit["complete"] is True
