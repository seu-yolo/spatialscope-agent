import json
import zipfile

from spatialscope.utils.review import load_review_notes, normalize_tags, save_quality_gate_override, save_review_notes
from spatialscope.utils.run_index import load_run_state, summarize_run


def test_normalize_tags_deduplicates_and_limits():
    tags = normalize_tags("Demo, marker review, demo, 需要复核;long tag name with spaces")
    assert tags[:3] == ["demo", "marker-review", "需要复核"]
    assert "long-tag-name-with-spaces" in tags


def test_save_review_notes_updates_manifest_bundle_and_public_state(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "report.html").write_text("<h1>report</h1>", encoding="utf-8")
    (run_dir / "agent_trace.json").write_text("[]", encoding="utf-8")
    (run_dir / "run_metadata.json").write_text("{}", encoding="utf-8")
    (run_dir / "parameters.yaml").write_text("mode: quick\n", encoding="utf-8")
    (run_dir / "state_public.json").write_text(json.dumps({"run_id": "run", "run_dir": str(run_dir)}), encoding="utf-8")
    manifest = {
        "schema_version": "1.0",
        "run_id": "run",
        "artifacts": [
            {"kind": "report", "path": str(run_dir / "report.html"), "relpath": "report.html", "exists": True},
            {"kind": "trace", "path": str(run_dir / "agent_trace.json"), "relpath": "agent_trace.json", "exists": True},
        ],
    }
    (run_dir / "artifact_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    state = {"run_id": "run", "run_dir": str(run_dir), "dataset_hash": "hash"}

    review = save_review_notes(
        state,
        {
            "decision": "accepted_with_caveats",
            "confidence": "high",
            "reviewer": "SEU reviewer",
            "tags": "demo, marker-review",
            "notes": "Useful for presentation.",
            "limitations": "Synthetic data only.",
        },
    )

    assert review["decision"] == "accepted_with_caveats"
    assert review["confidence"] == "high"
    assert (run_dir / "review_notes.json").exists()
    updated_manifest = json.loads((run_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert updated_manifest["review"]["decision"] == "accepted_with_caveats"
    assert any(item["kind"] == "review" and item["exists"] for item in updated_manifest["artifacts"])
    public_state = json.loads((run_dir / "state_public.json").read_text(encoding="utf-8"))
    assert public_state["review_notes"]["reviewer"] == "SEU reviewer"
    with zipfile.ZipFile(run_dir / "run_bundle.zip") as archive:
        assert "review_notes.json" in archive.namelist()
    restored = load_run_state(run_dir)
    assert restored["review_notes"]["decision"] == "accepted_with_caveats"
    summary = summarize_run(run_dir)
    assert summary["review_decision"] == "accepted_with_caveats"
    assert summary["review_confidence"] == "high"
    loaded = load_review_notes(run_dir)
    assert loaded["tags"] == ["demo", "marker-review"]


def test_quality_gate_override_is_preserved_and_clearable(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "state_public.json").write_text(json.dumps({"run_id": "run", "run_dir": str(run_dir)}), encoding="utf-8")
    (run_dir / "artifact_manifest.json").write_text(json.dumps({"schema_version": "1.0", "run_id": "run", "artifacts": []}), encoding="utf-8")
    state = {"run_id": "run", "run_dir": str(run_dir), "dataset_hash": "hash"}

    saved = save_quality_gate_override(
        state,
        {
            "gate_name": "Evidence outputs",
            "original_status": "warn",
            "original_score": 65,
            "decision": "requires_rerun",
            "rationale": "Missing marker table.",
            "reviewer": "Domain reviewer",
        },
    )
    assert saved["quality_gate_overrides"][0]["gate_name"] == "Evidence outputs"
    assert saved["quality_gate_overrides"][0]["decision"] == "requires_rerun"
    manifest = json.loads((run_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert manifest["review"]["quality_gate_overrides_count"] == 1
    with zipfile.ZipFile(run_dir / "run_bundle.zip") as archive:
        assert "review_notes.json" in archive.namelist()

    preserved = save_review_notes(
        state,
        {
            "decision": "accepted_with_caveats",
            "confidence": "medium",
            "reviewer": "Domain reviewer",
            "tags": "reviewed",
            "notes": "Keep the gate-level rationale.",
            "limitations": "",
        },
    )
    assert preserved["quality_gate_overrides"][0]["gate_name"] == "Evidence outputs"

    cleared = save_quality_gate_override(
        state,
        {
            "gate_name": "Evidence outputs",
            "decision": "clear_override",
            "rationale": "",
            "reviewer": "Domain reviewer",
        },
    )
    assert cleared["quality_gate_overrides"] == []
