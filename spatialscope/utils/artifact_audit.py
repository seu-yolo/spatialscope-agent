from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spatialscope.utils.paths import write_json


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def format_bytes(size: int | float | None) -> str:
    value = float(size or 0)
    units = ["B", "KB", "MB", "GB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _resolve_artifact_path(raw_path: Any, *, run_dir: Path) -> Path | None:
    raw = str(raw_path or "")
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute():
        return path
    if path.exists():
        return path
    path = run_dir / path
    return path


def audit_artifacts(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir)
    manifest = _read_json(root / "artifact_manifest.json")
    artifacts = [item for item in manifest.get("artifacts", []) if isinstance(item, dict)]
    rows: list[dict[str, Any]] = []
    kinds: dict[str, int] = {}
    total_size = 0
    for item in artifacts:
        path = _resolve_artifact_path(item.get("path"), run_dir=root)
        exists = path.is_file() if path else False
        size = path.stat().st_size if path and exists else 0
        kind = str(item.get("kind") or "unknown")
        kinds[kind] = kinds.get(kind, 0) + 1
        total_size += size
        rows.append(
            {
                "kind": kind,
                "title": item.get("title") or (path.name if path else ""),
                "relpath": item.get("relpath") or (str(path.relative_to(root)) if path and path.exists() and root in path.parents else str(path or "")),
                "exists": exists,
                "size_bytes": size,
                "size": format_bytes(size),
            }
        )

    missing = [row for row in rows if not row["exists"]]
    bundle_path = root / "run_bundle.zip"
    return {
        "schema_version": "1.0",
        "run_id": manifest.get("run_id") or root.name,
        "complete": len(rows) > 0 and not missing,
        "artifacts_count": len(rows),
        "existing_count": len(rows) - len(missing),
        "missing_count": len(missing),
        "total_size_bytes": total_size,
        "total_size": format_bytes(total_size),
        "kinds": kinds,
        "missing": missing,
        "artifacts": rows,
        "bundle": {
            "path": str(bundle_path),
            "exists": bundle_path.exists(),
            "size_bytes": bundle_path.stat().st_size if bundle_path.exists() else 0,
            "size": format_bytes(bundle_path.stat().st_size) if bundle_path.exists() else "0 B",
        },
    }


def write_artifact_audit(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir)
    audit = audit_artifacts(root)
    write_json(root / "artifact_audit.json", audit)
    return audit
