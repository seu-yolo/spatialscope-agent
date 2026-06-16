from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
import uuid
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


def make_run_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    return f"{timestamp}_{uuid.uuid4().hex[:6]}"


def ensure_run_dirs(outdir: str | Path, run_id: str) -> dict[str, Path]:
    root = Path(outdir)
    run_dir = root / run_id
    dirs = {
        "run_dir": run_dir,
        "figures_dir": run_dir / "figures",
        "tables_dir": run_dir / "tables",
        "intermediate_dir": run_dir / "intermediate",
    }
    for directory in dirs.values():
        directory.mkdir(parents=True, exist_ok=True)
    return dirs


def file_sha256(path: str | Path, *, max_bytes: int | None = None) -> str:
    h = hashlib.sha256()
    remaining = max_bytes
    with Path(path).open("rb") as handle:
        while True:
            if remaining is not None and remaining <= 0:
                break
            size = 1024 * 1024
            if remaining is not None:
                size = min(size, remaining)
            chunk = handle.read(size)
            if not chunk:
                break
            h.update(chunk)
            if remaining is not None:
                remaining -= len(chunk)
    return h.hexdigest()


def write_json(path: str | Path, payload: dict[str, Any] | list[Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)


def write_yaml_simple(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    try:
        import yaml
    except Exception:
        lines = [f"{key}: {value}" for key, value in payload.items()]
        Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    with Path(path).open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)


def environment_summary() -> dict[str, Any]:
    versions: dict[str, str] = {}
    for package in ["anndata", "scanpy", "squidpy", "langgraph", "openai", "streamlit"]:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = "not installed"
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "software_versions": versions,
    }


def public_state_copy(state: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in state.items() if not key.startswith("_")}
