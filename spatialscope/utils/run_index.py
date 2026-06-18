from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spatialscope.utils.quality import build_quality_report


def _read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _trace_messages(trace: list[Any], field: str) -> list[str]:
    messages: list[str] = []
    for item in trace:
        if not isinstance(item, dict):
            continue
        raw = item.get(field)
        if isinstance(raw, list):
            messages.extend(str(message) for message in raw if message)
        elif raw:
            messages.append(str(raw))
    return messages


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
        file_record(root / "run_bundle.zip", run_dir=root, kind="bundle", title="Complete run bundle"),
        file_record(root / "agent_trace.json", run_dir=root, kind="trace", title="Agent trace"),
        file_record(root / "run_metadata.json", run_dir=root, kind="metadata", title="Run metadata"),
        file_record(root / "parameters.yaml", run_dir=root, kind="parameters", title="Parameters"),
        file_record(root / "README.md", run_dir=root, kind="readme", title="Run README"),
        file_record(root / "artifact_audit.json", run_dir=root, kind="artifact_audit", title="Artifact audit"),
        file_record(root / "state_public.json", run_dir=root, kind="state", title="Public state"),
    ]
    review_path = root / "review_notes.json"
    if review_path.exists() or state.get("review_notes"):
        artifacts.append(file_record(review_path, run_dir=root, kind="review", title="Human review notes"))
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
        "quality": state.get("quality") or build_quality_report(state),
        "review": state.get("review_notes"),
        "artifacts": artifacts,
    }
    manifest["complete"] = all(item["exists"] for item in artifacts[:5])
    return manifest


def _records_from_manifest(manifest: dict[str, Any], *, kind: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for artifact in _as_list(manifest.get("artifacts")):
        if not isinstance(artifact, dict) or artifact.get("kind") != kind:
            continue
        records.append(
            {
                "path": artifact.get("path"),
                "title": artifact.get("title") or Path(str(artifact.get("path") or "")).name,
            }
        )
    return records


def _figure_records_from_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    figures: list[dict[str, Any]] = []
    svg_by_title: dict[str, str] = {}
    for artifact in _as_list(manifest.get("artifacts")):
        if not isinstance(artifact, dict) or artifact.get("kind") != "figure_svg":
            continue
        title = str(artifact.get("title") or "").replace(" SVG", "")
        if title:
            svg_by_title[title] = str(artifact.get("path") or "")
    for figure in _records_from_manifest(manifest, kind="figure"):
        title = str(figure.get("title") or "")
        if svg_by_title.get(title):
            figure["svg_path"] = svg_by_title[title]
        figures.append(figure)
    return figures


def load_run_state(run_dir: str | Path) -> dict[str, Any]:
    """Rehydrate the public, display-safe state for a historical run.

    This intentionally restores only persisted summaries, traces, figures,
    tables, and parameters. It never attempts to reconstruct AnnData or raw
    expression matrices from disk.
    """

    root = Path(run_dir)
    public_state = _as_dict(_read_json(root / "state_public.json"))
    metadata = _as_dict(_read_json(root / "run_metadata.json"))
    manifest = _as_dict(_read_json(root / "artifact_manifest.json"))
    trace = _as_list(_read_json(root / "agent_trace.json"))

    state: dict[str, Any] = dict(public_state)
    report_path = root / "report.html"
    parameters = _as_dict(_first_present(state.get("parameters"), metadata.get("parameters"), {}))

    state["run_id"] = _first_present(state.get("run_id"), metadata.get("run_id"), manifest.get("run_id"), root.name)
    state["run_dir"] = str(root)
    state["outdir"] = str(root.parent)
    state["figures_dir"] = str(root / "figures")
    state["tables_dir"] = str(root / "tables")
    state["intermediate_dir"] = str(root / "intermediate")
    state["report_path"] = str(report_path) if report_path.exists() else state.get("report_path")
    state["dataset_hash"] = _first_present(state.get("dataset_hash"), metadata.get("dataset_hash"), manifest.get("dataset_hash"))
    state["dataset_summary"] = _as_dict(_first_present(state.get("dataset_summary"), metadata.get("dataset_summary"), {}))
    state["environment"] = _as_dict(_first_present(state.get("environment"), metadata.get("environment"), {}))
    state["parameters"] = parameters
    state["mode"] = _first_present(state.get("mode"), parameters.get("mode"), manifest.get("mode"), "unknown")
    state["user_query"] = _first_present(state.get("user_query"), metadata.get("query"), manifest.get("query"), "")
    state["approved_plan"] = _as_list(_first_present(state.get("approved_plan"), metadata.get("approved_plan"), []))
    state["task_plan"] = _as_list(_first_present(state.get("task_plan"), state.get("approved_plan"), []))
    state["plan_source"] = _first_present(state.get("plan_source"), metadata.get("plan_source"), manifest.get("plan_source"), "unknown")
    state["plan_rationale"] = _first_present(state.get("plan_rationale"), metadata.get("plan_rationale"), "")
    state["llm_enabled"] = bool(_first_present(state.get("llm_enabled"), metadata.get("llm_enabled"), manifest.get("llm_enabled"), False))
    state["tool_contracts"] = _as_list(_first_present(state.get("tool_contracts"), metadata.get("tool_contracts"), []))
    state["repair_log"] = _as_list(_first_present(state.get("repair_log"), metadata.get("repair_log"), manifest.get("repair_log"), []))
    state["generated_figures"] = _as_list(
        _first_present(state.get("generated_figures"), metadata.get("figures"), _figure_records_from_manifest(manifest))
    )
    state["generated_tables"] = _as_list(
        _first_present(state.get("generated_tables"), metadata.get("tables"), _records_from_manifest(manifest, kind="table"))
    )
    state["observations"] = _as_dict(state.get("observations"))
    state["execution_trace"] = trace if trace else _as_list(state.get("execution_trace"))
    state["warnings"] = _as_list(state.get("warnings")) or _trace_messages(state["execution_trace"], "warnings")
    state["errors"] = _as_list(state.get("errors")) or _trace_messages(state["execution_trace"], "errors")
    state["quality"] = _as_dict(_first_present(state.get("quality"), metadata.get("quality"), manifest.get("quality")))
    if not state["quality"]:
        state["quality"] = build_quality_report(state)
    review_notes = _as_dict(_first_present(state.get("review_notes"), _read_json(root / "review_notes.json")))
    if review_notes:
        state["review_notes"] = review_notes
    if state.get("final_answer") is None:
        state["final_answer"] = ""
    state["loaded_from_run_dir"] = str(root)
    state["restored_from_bundle"] = True
    state["needs_repair"] = False
    state.pop("_adata", None)
    state.pop("adata", None)
    return state


def _status_counts(manifest: dict[str, Any], trace: list[Any]) -> dict[str, int]:
    counts = {"success": 0, "skipped": 0, "failed": 0, "repaired": 0}
    raw_counts = manifest.get("status_counts")
    if isinstance(raw_counts, dict):
        for key in counts:
            counts[key] = int(raw_counts.get(key) or 0)
        return counts
    for item in trace:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", ""))
        if status in counts:
            counts[status] += 1
    return counts


def summarize_run(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir)
    metadata = _read_json(root / "run_metadata.json")
    manifest = _read_json(root / "artifact_manifest.json")
    trace = _read_json(root / "agent_trace.json")
    review = _read_json(root / "review_notes.json")
    if not isinstance(metadata, dict):
        metadata = {}
    if not isinstance(manifest, dict):
        manifest = {}
    if not isinstance(trace, list):
        trace = []
    if not isinstance(review, dict):
        review = {}
    manifest_review = manifest.get("review") if isinstance(manifest.get("review"), dict) else {}

    report_path = root / "report.html"
    modified = max((path.stat().st_mtime for path in root.rglob("*") if path.is_file()), default=root.stat().st_mtime)
    status_counts = _status_counts(manifest, trace)
    dataset_hash = metadata.get("dataset_hash") or manifest.get("dataset_hash")
    return {
        "run_id": metadata.get("run_id") or manifest.get("run_id") or root.name,
        "run_dir": str(root),
        "mode": metadata.get("parameters", {}).get("mode") or manifest.get("mode") or "unknown",
        "query": metadata.get("query") or manifest.get("query") or "",
        "dataset_hash": dataset_hash or "",
        "plan_source": metadata.get("plan_source") or manifest.get("plan_source") or "unknown",
        "llm_enabled": bool(metadata.get("llm_enabled") or manifest.get("llm_enabled")),
        "figures": int(manifest.get("figures_count") or len(metadata.get("figures", []))),
        "tables": int(manifest.get("tables_count") or len(metadata.get("tables", []))),
        "trace_steps": len(trace),
        "warnings": int(manifest.get("warnings_count") or 0),
        "errors": int(manifest.get("errors_count") or 0),
        "repairs": int(manifest.get("repairs_count") or len(metadata.get("repair_log", []))),
        "status_success": status_counts["success"],
        "status_failed": status_counts["failed"],
        "status_repaired": status_counts["repaired"],
        "status_skipped": status_counts["skipped"],
        "report_path": str(report_path) if report_path.exists() else "",
        "manifest_path": str(root / "artifact_manifest.json") if (root / "artifact_manifest.json").exists() else "",
        "audit_path": str(root / "artifact_audit.json") if (root / "artifact_audit.json").exists() else "",
        "readme_path": str(root / "README.md") if (root / "README.md").exists() else "",
        "bundle_path": str(root / "run_bundle.zip") if (root / "run_bundle.zip").exists() else "",
        "bundle_size": (root / "run_bundle.zip").stat().st_size if (root / "run_bundle.zip").exists() else 0,
        "modified_time": modified,
        "complete": bool(manifest.get("complete")) if manifest else report_path.exists(),
        "quality_score": int((manifest.get("quality") or metadata.get("quality") or {}).get("score") or 0),
        "quality_status": str((manifest.get("quality") or metadata.get("quality") or {}).get("overall_status") or "unknown"),
        "review_decision": str(review.get("decision") or manifest_review.get("decision") or ""),
        "review_confidence": str(review.get("confidence") or manifest_review.get("confidence") or ""),
        "review_updated_at": str(review.get("updated_at") or manifest_review.get("updated_at") or ""),
    }


def discover_runs(outdir: str | Path = "outputs/runs", *, limit: int = 12) -> list[dict[str, Any]]:
    root = Path(outdir)
    if not root.exists():
        return []
    runs: list[dict[str, Any]] = []
    for run_dir in root.iterdir():
        if not run_dir.is_dir():
            continue
        runs.append(summarize_run(run_dir))
    runs.sort(key=lambda item: float(item.get("modified_time", 0)), reverse=True)
    return runs[:limit]


def _delta(left: Any, right: Any) -> int | None:
    try:
        return int(left) - int(right)
    except Exception:
        return None


def compare_run_summaries(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    metric_keys = [
        ("Figures", "figures"),
        ("Tables", "tables"),
        ("Trace steps", "trace_steps"),
        ("Success steps", "status_success"),
        ("Failed steps", "status_failed"),
        ("Repaired steps", "status_repaired"),
        ("Warnings", "warnings"),
        ("Errors", "errors"),
        ("Quality score", "quality_score"),
    ]
    rows: list[dict[str, Any]] = [
        {"Metric": "Mode", "A": left.get("mode"), "B": right.get("mode"), "Delta A-B": ""},
        {"Metric": "Plan source", "A": left.get("plan_source"), "B": right.get("plan_source"), "Delta A-B": ""},
        {"Metric": "LLM enabled", "A": bool(left.get("llm_enabled")), "B": bool(right.get("llm_enabled")), "Delta A-B": ""},
        {"Metric": "Bundle complete", "A": bool(left.get("complete")), "B": bool(right.get("complete")), "Delta A-B": ""},
        {"Metric": "Quality status", "A": left.get("quality_status"), "B": right.get("quality_status"), "Delta A-B": ""},
        {"Metric": "Review decision", "A": left.get("review_decision") or "unreviewed", "B": right.get("review_decision") or "unreviewed", "Delta A-B": ""},
    ]
    for label, key in metric_keys:
        diff = _delta(left.get(key, 0), right.get(key, 0))
        rows.append({"Metric": label, "A": left.get(key, 0), "B": right.get(key, 0), "Delta A-B": diff if diff is not None else ""})

    same_dataset = bool(left.get("dataset_hash") and left.get("dataset_hash") == right.get("dataset_hash"))
    notes: list[str] = []
    if same_dataset:
        notes.append("Both runs use the same dataset hash, so metric differences are easier to interpret.")
    else:
        notes.append("Dataset hashes differ or are missing; compare outputs cautiously.")
    if left.get("mode") != right.get("mode"):
        notes.append("Run modes differ, so extra figures or trace steps may reflect mode depth rather than better performance.")
    if int(left.get("errors", 0)) != int(right.get("errors", 0)):
        notes.append("Error counts differ; inspect Repair Diagnostics before comparing biological outputs.")
    if int(left.get("repairs", 0)) or int(right.get("repairs", 0)):
        notes.append("At least one run used repair handling; review the repair categories and recommended actions.")
    if not left.get("complete") or not right.get("complete"):
        notes.append("One bundle is incomplete, so report or manifest downloads may be missing.")

    return {
        "left_run_id": left.get("run_id"),
        "right_run_id": right.get("run_id"),
        "same_dataset": same_dataset,
        "rows": rows,
        "notes": notes,
    }
