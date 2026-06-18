from __future__ import annotations

from pathlib import Path
from typing import Any


def _status_counts(trace: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"success": 0, "skipped": 0, "failed": 0, "repaired": 0}
    for item in trace:
        status = str(item.get("status", ""))
        if status in counts:
            counts[status] += 1
    return counts


def _markdown_list(items: list[str]) -> str:
    if not items:
        return "- None recorded"
    return "\n".join(f"- {item}" for item in items)


def build_run_readme(state: dict[str, Any], *, report_path: str | Path | None = None) -> str:
    trace = [item for item in state.get("execution_trace", []) if isinstance(item, dict)]
    counts = _status_counts(trace)
    quality = state.get("quality") or {}
    agent_audit = state.get("agent_audit") or {}
    dataset = state.get("dataset_summary") or {}
    review = state.get("review_notes") or {}
    figures = state.get("generated_figures", [])
    tables = state.get("generated_tables", [])
    warnings = [str(item) for item in state.get("warnings", [])]
    errors = [str(item) for item in state.get("errors", [])]
    report_name = Path(report_path).name if report_path else "report.html"
    review_lines: list[str] = []
    if review:
        review_lines.extend(
            [
                f"- Decision: {review.get('decision_label') or review.get('decision')}",
                f"- Confidence: {review.get('confidence_label') or review.get('confidence')}",
                f"- Reviewer: {review.get('reviewer') or 'anonymous'}",
                f"- Updated: {review.get('updated_at') or 'not saved'}",
            ]
        )
        if review.get("quality_gate_overrides"):
            review_lines.append(f"- Quality gate overrides: {len(review.get('quality_gate_overrides', []))}")
    else:
        review_lines.append("- No human review notes saved yet.")

    figure_lines = [
        f"{item.get('title') or Path(str(item.get('path', ''))).name}: `{item.get('path')}`"
        for item in figures
    ]
    table_lines = [
        f"{item.get('title') or Path(str(item.get('path', ''))).name}: `{item.get('path')}`"
        for item in tables
    ]
    gate_lines = [
        f"{gate.get('name')}: {gate.get('status')} ({gate.get('score')}) - {gate.get('summary')}"
        for gate in quality.get("gates", [])
        if isinstance(gate, dict)
    ]
    return f"""# SpatialScope Run README

This folder is a reproducible SpatialScope Agent run bundle.

## Run

- Run ID: `{state.get("run_id")}`
- Mode: `{state.get("mode")}`
- Query: {state.get("user_query") or "N/A"}
- Plan source: `{state.get("plan_source") or "unknown"}`
- LLM: {"enabled" if state.get("llm_enabled") else "fallback"}
- Dataset hash: `{state.get("dataset_hash") or "N/A"}`

## Dataset

- Observations: {dataset.get("n_obs", "N/A")}
- Genes: {dataset.get("n_vars", "N/A")}
- Spatial coordinates: {"yes" if dataset.get("has_spatial") else "no/unknown"}

## Evidence Snapshot

- Figures: {len(figures)}
- Tables: {len(tables)}
- Trace steps: {len(trace)}
- Success / skipped / failed / repaired: {counts["success"]} / {counts["skipped"]} / {counts["failed"]} / {counts["repaired"]}
- Quality: {quality.get("score", "N/A")} / {quality.get("overall_status", "unknown")}
- Agent Audit: {agent_audit.get("score", "N/A")} / {agent_audit.get("overall_status", "unknown")}
- Storyboard panels: {(state.get("storyboard") or {}).get("n_cards", "N/A")}

## Human Review

{_markdown_list(review_lines)}

## Quality Gates

{_markdown_list(gate_lines)}

## Key Files

- `report.html`: main visual report
- `storyboard.html`: presentation-oriented visual storyboard
- `storyboard.json`: structured storyboard card metadata
- `agent_trace.json`: tool execution trace
- `run_metadata.json`: parameters, environment, plan, quality, and review metadata
- `parameters.yaml`: compact parameter export
- `agent_audit.json`: behavior-level agent self-audit
- `artifact_manifest.json`: indexed artifact list
- `artifact_audit.json`: artifact existence, size, and bundle status audit
- `review_notes.json`: human review and gate overrides, if saved
- `run_bundle.zip`: complete portable bundle

## Figures

{_markdown_list(figure_lines)}

## Tables

{_markdown_list(table_lines)}

## Warnings

{_markdown_list(warnings)}

## Errors

{_markdown_list(errors)}

## How To Inspect

Open `{report_name}` in a browser for the polished report. Use `agent_trace.json`
and `artifact_manifest.json` to audit how every output was produced. Treat biological
interpretations as exploratory unless Human Review notes explicitly document the
supporting evidence and limitations.
"""


def write_run_readme(state: dict[str, Any], *, run_dir: str | Path, report_path: str | Path | None = None) -> Path:
    root = Path(run_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "README.md"
    path.write_text(build_run_readme(state, report_path=report_path), encoding="utf-8")
    return path
