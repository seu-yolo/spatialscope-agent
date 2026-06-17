from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def file_record(path: Path, *, run_dir: Path, kind: str, title: str | None = None) -> dict[str, Any]:
    try:
        relpath = str(path.relative_to(run_dir))
    except ValueError:
        relpath = str(path)
    return {
        "kind": kind,
        "title": title or path.name,
        "path": str(path),
        "relpath": relpath,
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }


def build_artifact_manifest(state: dict[str, Any], *, run_dir: str | Path, report_path: str | Path) -> dict[str, Any]:
    root = Path(run_dir)
    report = Path(report_path)
    artifacts: list[dict[str, Any]] = [
        file_record(report, run_dir=root, kind="report", title="HTML report"),
        file_record(root / "agent_trace.json", run_dir=root, kind="trace", title="Agent trace"),
        file_record(root / "run_metadata.json", run_dir=root, kind="metadata", title="Run metadata"),
        file_record(root / "parameters.yaml", run_dir=root, kind="parameters", title="Parameters"),
        file_record(root / "state_public.json", run_dir=root, kind="state", title="Public state"),
    ]
    for fig in state.get("generated_figures", []):
        raw_path = str(fig.get("path") or "")
        if raw_path:
            path = Path(raw_path)
            artifacts.append(file_record(path, run_dir=root, kind="figure", title=str(fig.get("title") or path.name)))
        raw_svg_path = str(fig.get("svg_path") or "")
        if raw_svg_path:
            svg_path = Path(raw_svg_path)
            artifacts.append(file_record(svg_path, run_dir=root, kind="figure_svg", title=f"{fig.get('title') or svg_path.name} SVG"))
    for table in state.get("generated_tables", []):
        raw_path = str(table.get("path") or "")
        if raw_path:
            path = Path(raw_path)
            artifacts.append(file_record(path, run_dir=root, kind="table", title=str(table.get("title") or path.name)))

    status_counts = {"success": 0, "skipped": 0, "failed": 0, "repaired": 0}
    for item in state.get("execution_trace", []):
        status = str(item.get("status", ""))
        if status in status_counts:
            status_counts[status] += 1

    manifest = {
        "schema_version": "1.0",
        "run_id": state.get("run_id"),
        "mode": state.get("mode"),
        "query": state.get("user_query"),
        "dataset_hash": state.get("dataset_hash"),
        "plan_source": state.get("plan_source"),
        "llm_enabled": state.get("llm_enabled"),
        "status_counts": status_counts,
        "warnings_count": len(state.get("warnings", [])),
        "errors_count": len(state.get("errors", [])),
        "repairs_count": len(state.get("repair_log", [])),
        "repair_log": state.get("repair_log", []),
        "figures_count": len(state.get("generated_figures", [])),
        "tables_count": len(state.get("generated_tables", [])),
        "artifacts": artifacts,
    }
    manifest["complete"] = all(item["exists"] for item in artifacts[:5])
    return manifest


def discover_runs(outdir: str | Path = "outputs/runs", *, limit: int = 12) -> list[dict[str, Any]]:
    root = Path(outdir)
    if not root.exists():
        return []
    runs: list[dict[str, Any]] = []
    for run_dir in root.iterdir():
        if not run_dir.is_dir():
            continue
        metadata = _read_json(run_dir / "run_metadata.json")
        manifest = _read_json(run_dir / "artifact_manifest.json")
        trace = _read_json(run_dir / "agent_trace.json")
        if not isinstance(metadata, dict):
            metadata = {}
        if not isinstance(manifest, dict):
            manifest = {}
        if not isinstance(trace, list):
            trace = []
        report_path = run_dir / "report.html"
        modified = max((path.stat().st_mtime for path in run_dir.rglob("*") if path.is_file()), default=run_dir.stat().st_mtime)
        runs.append(
            {
                "run_id": metadata.get("run_id") or manifest.get("run_id") or run_dir.name,
                "run_dir": str(run_dir),
                "mode": metadata.get("parameters", {}).get("mode") or manifest.get("mode") or "unknown",
                "plan_source": metadata.get("plan_source") or manifest.get("plan_source") or "unknown",
                "llm_enabled": bool(metadata.get("llm_enabled") or manifest.get("llm_enabled")),
                "figures": int(manifest.get("figures_count") or len(metadata.get("figures", []))),
                "tables": int(manifest.get("tables_count") or len(metadata.get("tables", []))),
                "trace_steps": len(trace),
                "warnings": int(manifest.get("warnings_count") or 0),
                "errors": int(manifest.get("errors_count") or 0),
                "repairs": int(manifest.get("repairs_count") or len(metadata.get("repair_log", []))),
                "report_path": str(report_path) if report_path.exists() else "",
                "manifest_path": str(run_dir / "artifact_manifest.json") if (run_dir / "artifact_manifest.json").exists() else "",
                "modified_time": modified,
                "complete": bool(manifest.get("complete")) if manifest else report_path.exists(),
            }
        )
    runs.sort(key=lambda item: float(item.get("modified_time", 0)), reverse=True)
    return runs[:limit]
