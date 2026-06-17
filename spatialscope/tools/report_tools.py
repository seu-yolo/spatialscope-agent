from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Template

from spatialscope.tools.base import ToolResult
from spatialscope.utils.paths import public_state_copy, write_json, write_yaml_simple


REPORT_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>SpatialScope Agent Report - {{ run_id }}</title>
  <style>
    :root {
      --ink: #17202a;
      --muted: #5b6472;
      --line: #d9e0e8;
      --surface: #f7f9fb;
      --teal: #0f766e;
      --plum: #6d3f8c;
      --amber: #b7791f;
      --rose: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 0;
      color: var(--ink);
      background: #ffffff;
      line-height: 1.55;
    }
    main { max-width: 1180px; margin: 0 auto; padding: 36px 28px 56px; }
    header { border-bottom: 1px solid var(--line); padding-bottom: 22px; margin-bottom: 24px; }
    h1 { font-size: 34px; margin: 0 0 8px; letter-spacing: 0; }
    h2 { font-size: 20px; margin: 30px 0 12px; letter-spacing: 0; }
    h3 { font-size: 15px; margin: 0 0 8px; letter-spacing: 0; }
    p { margin: 8px 0; }
    .muted { color: var(--muted); }
    .summary { border-left: 4px solid var(--teal); background: var(--surface); padding: 14px 16px; border-radius: 6px; }
    .meta { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-top: 18px; }
    .metric { border: 1px solid var(--line); border-radius: 8px; padding: 12px; }
    .metric span { display: block; color: var(--muted); font-size: 12px; }
    .metric strong { display: block; font-size: 16px; margin-top: 4px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
    .figure { border: 1px solid var(--line); border-radius: 8px; padding: 14px; background: #fff; }
    img { max-width: 100%; border: 1px solid #edf1f5; border-radius: 6px; }
    code, pre { background: #f3f6f8; padding: 2px 4px; border-radius: 4px; }
    pre { overflow-x: auto; padding: 12px; border: 1px solid var(--line); }
    table { border-collapse: collapse; width: 100%; font-size: 14px; }
    th, td { border-bottom: 1px solid #e8edf2; padding: 8px 10px; text-align: left; vertical-align: top; }
    th { color: var(--muted); font-weight: 600; background: #fafbfc; }
    .badge { border-radius: 999px; color: #fff; display: inline-block; font-size: 12px; padding: 2px 8px; }
    .success { background: var(--teal); }
    .failed { background: var(--rose); }
    .skipped, .repaired { background: var(--amber); }
    .note { color: var(--muted); font-size: 13px; }
    a { color: var(--plum); }
  </style>
</head>
<body>
<main>
  <header>
    <h1>SpatialScope Agent Report</h1>
    <p class="muted">{{ query }}</p>
    <div class="meta">
      <div class="metric"><span>Run ID</span><strong>{{ run_id }}</strong></div>
      <div class="metric"><span>Mode</span><strong>{{ mode }}</strong></div>
      <div class="metric"><span>Plan Source</span><strong>{{ plan_source }}</strong></div>
      <div class="metric"><span>LLM</span><strong>{{ "enabled" if llm_enabled else "fallback" }}</strong></div>
    </div>
  </header>

  <h2>Run Summary</h2>
  <div class="summary">{{ final_answer }}</div>

  <h2>Dataset Overview</h2>
  <pre>{{ dataset_summary }}</pre>

  <h2>Evidence Snapshot</h2>
  <div class="meta">
    <div class="metric"><span>Figures</span><strong>{{ figures|length }}</strong></div>
    <div class="metric"><span>Tables</span><strong>{{ tables|length }}</strong></div>
    <div class="metric"><span>Trace Steps</span><strong>{{ trace|length }}</strong></div>
    <div class="metric"><span>Candidate Labels</span><strong>{{ annotations|length }}</strong></div>
  </div>

  <h2>Analysis Plan</h2>
  <p class="note">{{ plan_rationale }}</p>
  <ol>
  {% for step in plan %}
    <li><code>{{ step.tool }}</code> - {{ step.params }}<br><span class="note">{{ step.rationale }}</span></li>
  {% endfor %}
  </ol>

  {% if annotations %}
  <h2>Candidate Cluster Annotation Suggestions</h2>
  <p class="note">These are marker-overlap suggestions, not confirmed cell type calls.</p>
  <table>
    <thead><tr><th>Cluster</th><th>Candidate Label</th><th>Confidence</th><th>Evidence Markers</th><th>Top Markers</th></tr></thead>
    <tbody>
    {% for item in annotations %}
      <tr>
        <td>{{ item.cluster }}</td>
        <td>{{ item.candidate_label }}</td>
        <td>{{ item.confidence }}</td>
        <td>{{ item.evidence_markers }}</td>
        <td>{{ item.top_markers }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% endif %}

  <h2>Figures</h2>
  <div class="grid">
  {% for fig in figures %}
    <div class="figure">
      <h3>{{ fig.title }}</h3>
      <img src="{{ fig.relpath }}" alt="{{ fig.title }}">
      <p>{{ fig.caption }}</p>
    </div>
  {% endfor %}
  </div>

  <h2>Tables</h2>
  <ul>
  {% for table in tables %}
    <li><a href="{{ table.relpath }}">{{ table.title }}</a></li>
  {% endfor %}
  </ul>

  <h2>Agent Execution Trace</h2>
  <table>
    <thead><tr><th>Node</th><th>Tool</th><th>Status</th><th>Duration</th><th>Summary</th></tr></thead>
    <tbody>
    {% for item in trace %}
      <tr>
        <td>{{ item.node }}</td>
        <td>{{ item.tool }}</td>
        <td><span class="badge {{ item.status }}">{{ item.status }}</span></td>
        <td>{{ item.duration_sec }}</td>
        <td>{{ item.summary }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>

  {% if warnings or errors %}
  <h2>Warnings And Errors</h2>
  {% if warnings %}
    <p><strong>Warnings:</strong></p>
    <ul>{% for warning in warnings %}<li>{{ warning }}</li>{% endfor %}</ul>
  {% endif %}
  {% if errors %}
    <p><strong>Errors:</strong></p>
    <ul>{% for error in errors %}<li>{{ error }}</li>{% endfor %}</ul>
  {% endif %}
  {% endif %}

  <h2>Limitations</h2>
  <p>Interpretations are candidate, evidence-linked summaries for exploratory analysis. They do not establish causal mechanisms or confirmed cell type annotations.</p>
</main>
</body>
</html>
"""


def _with_relpaths(items: list[dict[str, Any]], run_dir: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        updated = dict(item)
        path = Path(str(item.get("path", "")))
        try:
            updated["relpath"] = str(path.relative_to(run_dir))
        except Exception:
            updated["relpath"] = str(path)
        out.append(updated)
    return out


def generate_report(state: dict[str, Any]) -> ToolResult:
    run_dir = Path(state["run_dir"])
    write_json(run_dir / "agent_trace.json", state.get("execution_trace", []))
    write_json(
        run_dir / "run_metadata.json",
        {
            "run_id": state.get("run_id"),
            "dataset_hash": state.get("dataset_hash"),
            "dataset_summary": state.get("dataset_summary"),
            "environment": state.get("environment"),
            "parameters": state.get("parameters"),
            "approved_plan": state.get("approved_plan"),
            "plan_source": state.get("plan_source"),
            "plan_rationale": state.get("plan_rationale"),
            "llm_enabled": state.get("llm_enabled"),
            "tool_contracts": state.get("tool_contracts"),
            "figures": state.get("generated_figures", []),
            "tables": state.get("generated_tables", []),
        },
    )
    write_yaml_simple(run_dir / "parameters.yaml", state.get("parameters", {}))

    template = Template(REPORT_TEMPLATE)
    html = template.render(
        run_id=state.get("run_id"),
        mode=state.get("mode"),
        query=state.get("user_query"),
        llm_enabled=state.get("llm_enabled"),
        plan_source=state.get("plan_source"),
        plan_rationale=state.get("plan_rationale"),
        final_answer=state.get("final_answer") or "No interpretation was generated.",
        dataset_summary=state.get("dataset_summary"),
        plan=state.get("approved_plan", []),
        figures=_with_relpaths(state.get("generated_figures", []), run_dir),
        tables=_with_relpaths(state.get("generated_tables", []), run_dir),
        trace=state.get("execution_trace", []),
        annotations=state.get("observations", {}).get("cluster_annotation_suggestions", []),
        warnings=state.get("warnings", []),
        errors=state.get("errors", []),
    )
    report_path = run_dir / "report.html"
    report_path.write_text(html, encoding="utf-8")

    write_json(run_dir / "state_public.json", public_state_copy(state))
    return ToolResult(
        status="success",
        summary=f"Generated HTML report at {report_path}.",
        observations={"report_path": str(report_path)},
    )
