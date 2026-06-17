from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from spatialscope.utils.bundle import build_run_bundle
from spatialscope.utils.paths import write_json
from spatialscope.utils.run_index import file_record


DECISIONS = {
    "exploratory_only": "Exploratory only",
    "accepted_with_caveats": "Accepted with caveats",
    "needs_rerun": "Needs rerun",
    "archived": "Archived",
}
CONFIDENCE_LEVELS = {"low": "Low", "medium": "Medium", "high": "High"}


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
    payload.setdefault("updated_at", "")
    return payload


def _upsert_manifest_review(manifest_path: Path, review_path: Path, review: dict[str, Any]) -> None:
    root = manifest_path.parent
    manifest = _read_json(manifest_path) or {"schema_version": "1.0", "run_id": review.get("run_id"), "artifacts": []}
    artifacts = [item for item in manifest.get("artifacts", []) if isinstance(item, dict)]
    artifacts = [item for item in artifacts if item.get("kind") != "review"]
    artifacts.append(file_record(review_path, run_dir=root, kind="review", title="Human review notes"))
    manifest["artifacts"] = artifacts
    manifest["review"] = {
        "decision": review.get("decision"),
        "confidence": review.get("confidence"),
        "tags": review.get("tags", []),
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
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    review_path = root / "review_notes.json"
    write_json(review_path, review)
    _upsert_public_state_review(root / "state_public.json", review)
    _upsert_manifest_review(root / "artifact_manifest.json", review_path, review)
    bundle = build_run_bundle(root)
    state["review_notes"] = review
    state["review_bundle"] = bundle
    return review
