import json
import zipfile

from spatialscope.utils.bundle import build_run_bundle


def test_build_run_bundle_uses_manifest_artifacts(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "report.html").write_text("<h1>report</h1>", encoding="utf-8")
    (run_dir / "agent_trace.json").write_text("[]", encoding="utf-8")
    manifest = {
        "artifacts": [
            {"path": str(run_dir / "report.html"), "relpath": "report.html", "exists": True},
            {"path": str(run_dir / "agent_trace.json"), "relpath": "agent_trace.json", "exists": True},
        ]
    }
    (run_dir / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = build_run_bundle(run_dir)
    assert result["exists"] is True
    assert result["file_count"] == 2
    with zipfile.ZipFile(result["path"]) as archive:
        names = set(archive.namelist())
    assert "report.html" in names
    assert "agent_trace.json" in names


def test_build_run_bundle_accepts_manifest_paths_relative_to_cwd(tmp_path, monkeypatch):
    project = tmp_path / "project"
    run_dir = project / "outputs" / "runs" / "run"
    run_dir.mkdir(parents=True)
    report = run_dir / "report.html"
    trace = run_dir / "agent_trace.json"
    report.write_text("<h1>report</h1>", encoding="utf-8")
    trace.write_text("[]", encoding="utf-8")
    monkeypatch.chdir(project)
    manifest = {
        "artifacts": [
            {"path": "outputs/runs/run/report.html", "relpath": "report.html", "exists": True},
            {"path": "outputs/runs/run/agent_trace.json", "relpath": "agent_trace.json", "exists": True},
        ]
    }
    (run_dir / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    result = build_run_bundle(run_dir)

    assert result["file_count"] == 2
    with zipfile.ZipFile(result["path"]) as archive:
        names = set(archive.namelist())
    assert "report.html" in names
    assert "agent_trace.json" in names
