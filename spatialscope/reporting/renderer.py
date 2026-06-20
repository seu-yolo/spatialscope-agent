from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _with_relpaths(items: list[dict[str, Any]], run_dir: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        updated = dict(item)
        path = Path(str(item.get("path", "")))
        try:
            updated["relpath"] = str(path.relative_to(run_dir))
        except Exception:
            updated["relpath"] = str(path)
        if item.get("svg_path"):
            svg_path = Path(str(item.get("svg_path")))
            try:
                updated["svg_relpath"] = str(svg_path.relative_to(run_dir))
            except Exception:
                updated["svg_relpath"] = str(svg_path)
        out.append(updated)
    return out


def render_report_html(
    state: dict[str, Any],
    *,
    run_dir: Path,
    project_signature: str,
    acknowledgements: list[str],
) -> str:
    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("report.html.j2")
    return template.render(
        run_id=state.get("run_id"),
        mode=state.get("mode"),
        query=state.get("user_query"),
        llm_enabled=state.get("llm_enabled"),
        plan_source=state.get("plan_source"),
        plan_rationale=state.get("plan_rationale"),
        final_answer=state.get("final_answer") or "No interpretation was generated.",
        dataset_summary=state.get("dataset_summary") or {},
        research_brief=state.get("research_brief") or {},
        findings=state.get("scientific_findings", []),
        evidence_packs=state.get("evidence_packs", []),
        plan=state.get("approved_plan", []),
        figures=_with_relpaths(state.get("generated_figures", []), run_dir),
        tables=_with_relpaths(state.get("generated_tables", []), run_dir),
        trace=state.get("execution_trace", []),
        repairs=state.get("repair_log", []),
        clarifications=state.get("clarification_items", []),
        warnings=state.get("warnings", []),
        errors=state.get("errors", []),
        project_signature=project_signature,
        acknowledgements=acknowledgements,
    )
