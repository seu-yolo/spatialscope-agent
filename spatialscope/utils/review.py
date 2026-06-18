from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from spatialscope.utils.artifact_audit import write_artifact_audit
from spatialscope.utils.bundle import build_run_bundle
from spatialscope.utils.paths import write_json
from spatialscope.utils.run_readme import write_run_readme
from spatialscope.utils.run_index import file_record


DECISIONS = {
    "exploratory_only": "Exploratory only",
    "accepted_with_caveats": "Accepted with caveats",
    "needs_rerun": "Needs rerun",
    "archived": "Archived",
}
CONFIDENCE_LEVELS = {"low": "Low", "medium": "Medium", "high": "High"}
GATE_OVERRIDE_DECISIONS = {
    "accepted_as_reported": "Accepted as reported",
    "override_to_pass": "Override to pass",
    "requires_rerun": "Requires rerun",
    "needs_context": "Needs more context",
    "clear_override": "Clear override",
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _clean_text(value: Any, *, max_chars: int = 5000) -> str:
    text = str(value or "").strip()
    return text[:max_chars]


def normalize_tags(value: str | list[Any]) -> list[str]:
    if isinstance(value, list):
        raw_items = [str(item) for item in value]
    else:
        raw = str(value or "").replace("，", ",").replace(";", ",").replace("\n", ",")
        raw_items = raw.split(",")
    tags: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        tag = item.strip().lower().replace(" ", "-")[:32]
        if not tag or tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
        if len(tags) >= 12:
            break
    return tags


def normalize_quality_gate_overrides(value: Any) -> list[dict[str, Any]]:
    raw_items = value if isinstance(value, list) else []
    overrides: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        gate_name = _clean_text(item.get("gate_name"), max_chars=120)
        decision = str(item.get("decision") or "")
        if not gate_name or gate_name in seen or decision not in GATE_OVERRIDE_DECISIONS or decision == "clear_override":
            continue
        seen.add(gate_name)
        overrides.append(
            {
                "gate_name": gate_name,
                "original_status": _clean_text(item.get("original_status"), max_chars=40),
                "original_score": item.get("original_score"),
                "decision": decision,
                "decision_label": GATE_OVERRIDE_DECISIONS[decision],
                "rationale": _clean_text(item.get("rationale")),
                "reviewer": _clean_text(item.get("reviewer"), max_chars=120),
                "updated_at": _clean_text(item.get("updated_at"), max_chars=40),
            }
        )
    return overrides


def empty_review_notes(run_id: str = "") -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "decision": "exploratory_only",
        "decision_label": DECISIONS["exploratory_only"],
        "confidence": "medium",
        "confidence_label": CONFIDENCE_LEVELS["medium"],
        "reviewer": "",
        "tags": [],
        "notes": "",
        "limitations": "",
        "quality_gate_overrides": [],
        "updated_at": "",
    }


def load_review_notes(run_dir: str | Path, *, run_id: str = "") -> dict[str, Any]:
    root = Path(run_dir)
    payload = _read_json(root / "review_notes.json")
    if not payload:
        return empty_review_notes(run_id)
    payload.setdefault("schema_version", "1.0")
    payload.setdefault("run_id", run_id or root.name)
    payload["decision"] = str(payload.get("decision") or "exploratory_only")
    payload["decision_label"] = DECISIONS.get(payload["decision"], payload["decision"])
    payload["confidence"] = str(payload.get("confidence") or "medium")
    payload["confidence_label"] = CONFIDENCE_LEVELS.get(payload["confidence"], payload["confidence"])
    payload["tags"] = normalize_tags(payload.get("tags", []))
    payload["reviewer"] = _clean_text(payload.get("reviewer"), max_chars=120)
    payload["notes"] = _clean_text(payload.get("notes"))
    payload["limitations"] = _clean_text(payload.get("limitations"))
    payload["quality_gate_overrides"] = normalize_quality_gate_overrides(payload.get("quality_gate_overrides", []))
    payload.setdefault("updated_at", "")
    return payload


def _upsert_manifest_review(manifest_path: Path, review_path: Path, review: dict[str, Any]) -> None:
    root = manifest_path.parent
    manifest = _read_json(manifest_path) or {"schema_version": "1.0", "run_id": review.get("run_id"), "artifacts": []}
    artifacts = [item for item in manifest.get("artifacts", []) if isinstance(item, dict)]
    artifacts = [item for item in artifacts if item.get("kind") not in {"review", "readme"}]
    readme_path = root / "README.md"
    if readme_path.exists():
        artifacts.append(file_record(readme_path, run_dir=root, kind="readme", title="Run README"))
    audit_path = root / "artifact_audit.json"
    if audit_path.exists() and not any(item.get("kind") == "artifact_audit" for item in artifacts):
        artifacts.append(file_record(audit_path, run_dir=root, kind="artifact_audit", title="Artifact audit"))
    artifacts.append(file_record(review_path, run_dir=root, kind="review", title="Human review notes"))
    manifest["artifacts"] = artifacts
    manifest["review"] = {
        "decision": review.get("decision"),
        "confidence": review.get("confidence"),
        "tags": review.get("tags", []),
        "quality_gate_overrides_count": len(review.get("quality_gate_overrides", [])),
        "updated_at": review.get("updated_at"),
    }
    write_json(manifest_path, manifest)


def _upsert_public_state_review(state_path: Path, review: dict[str, Any]) -> None:
    public_state = _read_json(state_path)
    if not public_state:
        return
    public_state["review_notes"] = review
    write_json(state_path, public_state)


def save_review_notes(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    raw_run_dir = state.get("run_dir")
    if not raw_run_dir:
        raise ValueError("run_dir is required to save review notes.")
    root = Path(str(raw_run_dir))
    root.mkdir(parents=True, exist_ok=True)
    decision = str(payload.get("decision") or "exploratory_only")
    confidence = str(payload.get("confidence") or "medium")
    if decision not in DECISIONS:
        decision = "exploratory_only"
    if confidence not in CONFIDENCE_LEVELS:
        confidence = "medium"
    existing = load_review_notes(root, run_id=str(state.get("run_id") or root.name))
    gate_overrides = normalize_quality_gate_overrides(
        payload.get("quality_gate_overrides", existing.get("quality_gate_overrides", []))
    )

    review = {
        "schema_version": "1.0",
        "run_id": str(state.get("run_id") or root.name),
        "dataset_hash": state.get("dataset_hash"),
        "decision": decision,
        "decision_label": DECISIONS[decision],
        "confidence": confidence,
        "confidence_label": CONFIDENCE_LEVELS[confidence],
        "reviewer": _clean_text(payload.get("reviewer"), max_chars=120),
        "tags": normalize_tags(payload.get("tags", [])),
        "notes": _clean_text(payload.get("notes")),
        "limitations": _clean_text(payload.get("limitations")),
        "quality_gate_overrides": gate_overrides,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    review_path = root / "review_notes.json"
    write_json(review_path, review)
    state["review_notes"] = review
    _upsert_public_state_review(root / "state_public.json", review)
    write_run_readme(state, run_dir=root, report_path=root / "report.html")
    _upsert_manifest_review(root / "artifact_manifest.json", review_path, review)
    write_artifact_audit(root)
    _upsert_manifest_review(root / "artifact_manifest.json", review_path, review)
    bundle = build_run_bundle(root)
    state["review_bundle"] = bundle
    return review


def save_quality_gate_override(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    raw_run_dir = state.get("run_dir")
    if not raw_run_dir:
        raise ValueError("run_dir is required to save a quality gate override.")
    root = Path(str(raw_run_dir))
    root.mkdir(parents=True, exist_ok=True)
    review = load_review_notes(root, run_id=str(state.get("run_id") or root.name))
    review["dataset_hash"] = review.get("dataset_hash") or state.get("dataset_hash")
    decision = str(payload.get("decision") or "accepted_as_reported")
    if decision not in GATE_OVERRIDE_DECISIONS:
        decision = "accepted_as_reported"
    gate_name = _clean_text(payload.get("gate_name"), max_chars=120)
    if not gate_name:
        raise ValueError("gate_name is required to save a quality gate override.")

    overrides = [item for item in normalize_quality_gate_overrides(review.get("quality_gate_overrides", [])) if item.get("gate_name") != gate_name]
    if decision != "clear_override":
        overrides.append(
            {
                "gate_name": gate_name,
                "original_status": _clean_text(payload.get("original_status"), max_chars=40),
                "original_score": payload.get("original_score"),
                "decision": decision,
                "decision_label": GATE_OVERRIDE_DECISIONS[decision],
                "rationale": _clean_text(payload.get("rationale")),
                "reviewer": _clean_text(payload.get("reviewer") or review.get("reviewer"), max_chars=120),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
    review["quality_gate_overrides"] = normalize_quality_gate_overrides(overrides)
    review["updated_at"] = datetime.now().isoformat(timespec="seconds")
    review_path = root / "review_notes.json"
    write_json(review_path, review)
    state["review_notes"] = review
    _upsert_public_state_review(root / "state_public.json", review)
    write_run_readme(state, run_dir=root, report_path=root / "report.html")
    _upsert_manifest_review(root / "artifact_manifest.json", review_path, review)
    write_artifact_audit(root)
    _upsert_manifest_review(root / "artifact_manifest.json", review_path, review)
    bundle = build_run_bundle(root)
    state["review_bundle"] = bundle
    return review
