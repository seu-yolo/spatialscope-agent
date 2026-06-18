from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any


def _read_manifest(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "artifact_manifest.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _artifact_paths_from_manifest(manifest: dict[str, Any], run_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for item in manifest.get("artifacts", []):
        if not isinstance(item, dict):
            continue
        raw = str(item.get("path") or "")
        if not raw:
            continue
        path = Path(raw)
        if not path.is_absolute() and not path.exists():
            path = run_dir / path
        if path.is_file():
            paths.append(path)
    return paths


def build_run_bundle(run_dir: str | Path, *, bundle_name: str = "run_bundle.zip") -> dict[str, Any]:
    root = Path(run_dir)
    root.mkdir(parents=True, exist_ok=True)
    manifest = _read_manifest(root)
    bundle_path = root / bundle_name
    paths = _artifact_paths_from_manifest(manifest, root)
    if not paths:
        paths = [path for path in root.rglob("*") if path.is_file() and path.name != bundle_name]

    unique_paths: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved == bundle_path.resolve() or resolved in seen:
            continue
        seen.add(resolved)
        unique_paths.append(path)

    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in unique_paths:
            try:
                arcname = path.relative_to(root)
            except ValueError:
                arcname = Path(path.name)
            archive.write(path, arcname.as_posix())

    return {
        "path": str(bundle_path),
        "relpath": bundle_path.name,
        "exists": bundle_path.exists(),
        "size_bytes": bundle_path.stat().st_size if bundle_path.exists() else 0,
        "file_count": len(unique_paths),
    }
