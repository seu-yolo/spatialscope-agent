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
    body { font-family: Arial, sans-serif; margin: 32px; color: #1f2937; line-height: 1.5; }
    h1, h2 { color: #0f172a; }
    .card { border: 1px solid #d0d7de; border-radius: 8px; padding: 16px; margin: 12px 0; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; }
    img { max-width: 100%; border: 1px solid #e5e7eb; border-radius: 6px; }
    code, pre { background: #f6f8fa; padding: 2px 4px; border-radius: 4px; }
    table { border-collapse: collapse; width: 100%; }
    th, td { border-bottom: 1px solid #e5e7eb; padding: 6px 8px; text-align: left; }
  </style>
</head>
<body>
  <h1>SpatialScope Agent Report</h1>
  <p><strong>Run ID:</strong> {{ run_id }}</p>
  <p><strong>User query:</strong> {{ query }}</p>

  <h2>Run Summary</h2>
  <div class="card">{{ final_answer }}</div>

  <h2>Dataset Overview</h2>
  <pre>{{ dataset_summary }}</pre>

  <h2>Analysis Plan</h2>
  <ol>
  {% for step in plan %}
    <li><code>{{ step.tool }}</code> - {{ step.params }}</li>
  {% endfor %}
  </ol>

  <h2>Figures</h2>
  <div class="grid">
  {% for fig in figures %}
    <div class="card">
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
        <td>{{ item.status }}</td>
        <td>{{ item.duration_sec }}</td>
        <td>{{ item.summary }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>

  <h2>Limitations</h2>
  <p>Interpretations are candidate, evidence-linked summaries for exploratory analysis. They do not establish causal mechanisms or confirmed cell type annotations.</p>
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
            "figures": state.get("generated_figures", []),
            "tables": state.get("generated_tables", []),
        },
    )
    write_yaml_simple(run_dir / "parameters.yaml", state.get("parameters", {}))

    template = Template(REPORT_TEMPLATE)
    html = template.render(
        run_id=state.get("run_id"),
        query=state.get("user_query"),
        final_answer=state.get("final_answer") or "No interpretation was generated.",
        dataset_summary=state.get("dataset_summary"),
        plan=state.get("approved_plan", []),
        figures=_with_relpaths(state.get("generated_figures", []), run_dir),
        tables=_with_relpaths(state.get("generated_tables", []), run_dir),
        trace=state.get("execution_trace", []),
    )
    report_path = run_dir / "report.html"
    report_path.write_text(html, encoding="utf-8")

    write_json(run_dir / "state_public.json", public_state_copy(state))
    return ToolResult(
        status="success",
        summary=f"Generated HTML report at {report_path}.",
        observations={"report_path": str(report_path)},
    )

