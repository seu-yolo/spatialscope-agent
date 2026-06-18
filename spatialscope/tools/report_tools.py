from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Template

from spatialscope.tools.base import ToolResult
from spatialscope.utils.agent_audit import write_agent_audit
from spatialscope.utils.artifact_audit import write_artifact_audit
from spatialscope.utils.bundle import build_run_bundle
from spatialscope.utils.dataset_card import write_dataset_card
from spatialscope.utils.paths import public_state_copy, write_json, write_yaml_simple
from spatialscope.utils.quality import build_quality_report
from spatialscope.utils.replay import write_rerun_recipe
from spatialscope.utils.run_readme import write_run_readme
from spatialscope.utils.run_index import build_artifact_manifest
from spatialscope.utils.storyboard import write_storyboard


PROJECT_SIGNATURE = "seu-yolo / 东南大学计算生物学"
ACKNOWLEDGEMENTS = [
    "We gratefully acknowledge Professor Peng Xie from the School of Biological Science and Medical Engineering, Southeast University.",
    "We also thank Teaching Assistant Binyu Gao for guidance and support throughout the course project.",
    "This agent was built as an open, reproducible spatial transcriptomics analysis system.",
]


REPORT_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>SpatialScope Agent 分析报告 - {{ run_id }}</title>
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
      font-family: "PingFang SC", "Noto Sans CJK SC", "Microsoft YaHei", Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
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
    .pass { background: var(--teal); }
    .warn { background: var(--amber); }
    .fail { background: var(--rose); }
    .note { color: var(--muted); font-size: 13px; }
    .tag { border: 1px solid var(--line); border-radius: 999px; color: var(--muted); display: inline-block; font-size: 12px; margin: 3px 4px 3px 0; padding: 2px 8px; }
    .signature { color: var(--teal); font-size: 12px; font-weight: 700; letter-spacing: 0.05em; margin-top: 10px; text-transform: uppercase; }
    .repair-list { margin: 0; padding-left: 18px; }
    footer { border-top: 1px solid var(--line); color: var(--muted); font-size: 13px; margin-top: 34px; padding-top: 16px; }
    a { color: var(--plum); }
  </style>
</head>
<body>
<main>
  <header>
    <h1>SpatialScope Agent 分析报告</h1>
    <p class="muted">{{ query }}</p>
    <div>
      <span class="tag">Spatial Omics Agent</span>
      <span class="tag">LangGraph Workflow</span>
      <span class="tag">Reproducible Trace</span>
      <span class="tag">Publication-minded figures</span>
    </div>
    <div class="signature">{{ project_signature }}</div>
    <div class="meta">
      <div class="metric"><span>Run ID</span><strong>{{ run_id }}</strong></div>
      <div class="metric"><span>Mode</span><strong>{{ mode }}</strong></div>
      <div class="metric"><span>Plan source</span><strong>{{ plan_source }}</strong></div>
      <div class="metric"><span>LLM</span><strong>{{ "enabled" if llm_enabled else "fallback" }}</strong></div>
    </div>
  </header>

  <h2>运行摘要 / Run Summary</h2>
  <div class="summary">{{ final_answer }}</div>

  <h2>数据概览 / Dataset Overview</h2>
  <pre>{{ dataset_summary }}</pre>

  <h2>证据快照 / Evidence Snapshot</h2>
  <div class="meta">
    <div class="metric"><span>Figures</span><strong>{{ figures|length }}</strong></div>
    <div class="metric"><span>Tables</span><strong>{{ tables|length }}</strong></div>
    <div class="metric"><span>Trace steps</span><strong>{{ trace|length }}</strong></div>
    <div class="metric"><span>Repairs</span><strong>{{ repairs|length }}</strong></div>
    <div class="metric"><span>Quality</span><strong>{{ quality.score }} / {{ quality.overall_status }}</strong></div>
    <div class="metric"><span>Agent Audit</span><strong>{{ agent_audit.score }} / {{ agent_audit.overall_status }}</strong></div>
    <div class="metric"><span>Candidate labels</span><strong>{{ annotations|length }}</strong></div>
  </div>
  {% if storyboard %}
  <p><a href="storyboard.html">Open Spatial Storyboard</a> · {{ storyboard.n_cards }} curated visual panels</p>
  {% endif %}
  {% if rerun_recipe %}
  <p><a href="RERUN.md">Open Rerun Recipe</a> · command and parameters for reproducing this run</p>
  {% endif %}
  {% if dataset_card %}
  <p><a href="dataset_card.html">Open Dataset Card</a> · recommended mode {{ dataset_card.recommended_mode }}</p>
  {% endif %}

  <h2>Quality Gates 质量自检</h2>
  <table>
    <thead><tr><th>Gate</th><th>Status</th><th>Score</th><th>Summary</th><th>Evidence</th><th>Recommendation</th></tr></thead>
    <tbody>
    {% for gate in quality.gates %}
      <tr>
        <td>{{ gate.name }}</td>
        <td><span class="badge {{ gate.status }}">{{ gate.status }}</span></td>
        <td>{{ gate.score }}</td>
        <td>{{ gate.summary }}</td>
        <td>{{ gate.evidence }}</td>
        <td>{{ gate.recommendation }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>

  <h2>Agent Audit 行为自检</h2>
  <p class="note">This audit evaluates whether the agent stayed contract-bound, traceable, repair-aware, and evidence-bounded.</p>
  <table>
    <thead><tr><th>Check</th><th>Status</th><th>Score</th><th>Summary</th><th>Evidence</th><th>Recommendation</th></tr></thead>
    <tbody>
    {% for check in agent_audit.checks %}
      <tr>
        <td>{{ check.name }}</td>
        <td><span class="badge {{ check.status }}">{{ check.status }}</span></td>
        <td>{{ check.score }}</td>
        <td>{{ check.summary }}</td>
        <td>{{ check.evidence }}</td>
        <td>{{ check.recommendation }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>

  {% if review %}
  <h2>Human Review 人工审阅</h2>
  <div class="meta">
    <div class="metric"><span>Decision</span><strong>{{ review.decision_label }}</strong></div>
    <div class="metric"><span>Confidence</span><strong>{{ review.confidence_label }}</strong></div>
    <div class="metric"><span>Reviewer</span><strong>{{ review.reviewer or "匿名" }}</strong></div>
    <div class="metric"><span>Updated</span><strong>{{ review.updated_at }}</strong></div>
  </div>
  {% if review.tags %}
    <p>{% for tag in review.tags %}<span class="tag">{{ tag }}</span>{% endfor %}</p>
  {% endif %}
  {% if review.notes %}<p><strong>Notes:</strong> {{ review.notes }}</p>{% endif %}
  {% if review.limitations %}<p><strong>Limitations:</strong> {{ review.limitations }}</p>{% endif %}
  {% if review.quality_gate_overrides %}
  <h3>Quality Gate Overrides</h3>
  <table>
    <thead><tr><th>Gate</th><th>Original</th><th>Reviewer Decision</th><th>Reviewer</th><th>Rationale</th></tr></thead>
    <tbody>
    {% for item in review.quality_gate_overrides %}
      <tr>
        <td>{{ item.gate_name }}</td>
        <td>{{ item.original_status }} / {{ item.original_score }}</td>
        <td>{{ item.decision_label }}</td>
        <td>{{ item.reviewer }}</td>
        <td>{{ item.rationale }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% endif %}
  {% endif %}

  <h2>分析方案 / Analysis Plan</h2>
  <p class="note">{{ plan_rationale }}</p>
  <ol>
  {% for step in plan %}
    <li><code>{{ step.tool }}</code> - {{ step.params }}<br><span class="note">{{ step.rationale }}</span></li>
  {% endfor %}
  </ol>

  {% if annotations %}
  <h2>候选 Cluster 注释 / Candidate Annotation Suggestions</h2>
  <p class="note">These are marker-overlap suggestions, not confirmed cell type calls.</p>
  <table>
    <thead><tr><th>Cluster</th><th>Candidate Label</th><th>Marker Evidence Score</th><th>Evidence Markers</th><th>Top Markers</th></tr></thead>
    <tbody>
    {% for item in annotations %}
      <tr>
        <td>{{ item.cluster }}</td>
        <td>{{ item.candidate_label }}</td>
        <td>{{ item.marker_evidence_score }}</td>
        <td>{{ item.evidence_markers }}</td>
        <td>{{ item.top_markers }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% endif %}

  <h2>Figures 图表</h2>
  <div class="grid">
  {% for fig in figures %}
    <div class="figure">
      <h3>{{ fig.title }}</h3>
      <img src="{{ fig.relpath }}" alt="{{ fig.title }}">
      <p>{{ fig.caption }}</p>
      {% if fig.svg_relpath %}<p class="note"><a href="{{ fig.svg_relpath }}">Editable SVG</a></p>{% endif %}
    </div>
  {% endfor %}
  </div>

  <h2>Tables 表格</h2>
  <ul>
  {% for table in tables %}
    <li><a href="{{ table.relpath }}">{{ table.title }}</a></li>
  {% endfor %}
  </ul>

  <h2>Agent Execution Trace 执行追踪</h2>
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

  {% if repairs %}
  <h2>Repair Diagnostics 修复诊断</h2>
  <p class="note">Each repair record is generated from tool summaries, errors, and tool contracts. No raw expression matrix is sent to an LLM.</p>
  <table>
    <thead><tr><th>Tool</th><th>Category</th><th>Action</th><th>Likely Cause</th><th>Recommended Actions</th></tr></thead>
    <tbody>
    {% for item in repairs %}
      <tr>
        <td><code>{{ item.tool }}</code></td>
        <td>{{ item.category }}</td>
        <td>{{ item.action }}</td>
        <td>{{ item.likely_cause }}</td>
        <td>
          <ul class="repair-list">
          {% for action in item.recommended_actions %}
            <li>{{ action }}</li>
          {% endfor %}
          </ul>
        </td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  {% endif %}

  {% if warnings or errors %}
  <h2>Warnings / Errors 提醒与错误</h2>
  {% if warnings %}
    <p><strong>Warnings:</strong></p>
    <ul>{% for warning in warnings %}<li>{{ warning }}</li>{% endfor %}</ul>
  {% endif %}
  {% if errors %}
    <p><strong>Errors:</strong></p>
    <ul>{% for error in errors %}<li>{{ error }}</li>{% endfor %}</ul>
  {% endif %}
  {% endif %}

  <h2>局限性 / Limitations</h2>
  <p>Interpretations are candidate, evidence-linked summaries for exploratory analysis. They do not establish causal mechanisms or confirmed cell type annotations.</p>

  <h2>Acknowledgements</h2>
  <ul>
  {% for item in acknowledgements %}
    <li>{{ item }}</li>
  {% endfor %}
  </ul>

  <footer>
    {{ project_signature }} · SpatialScope Agent · 可复现空间转录组分析工作台.
  </footer>
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
        if item.get("svg_path"):
            svg_path = Path(str(item.get("svg_path")))
            try:
                updated["svg_relpath"] = str(svg_path.relative_to(run_dir))
            except Exception:
                updated["svg_relpath"] = str(svg_path)
        out.append(updated)
    return out


def generate_report(state: dict[str, Any]) -> ToolResult:
    run_dir = Path(state["run_dir"])
    quality = build_quality_report(state)
    state["quality"] = quality
    dataset_card = write_dataset_card(state, run_dir)
    state["dataset_card"] = dataset_card
    agent_audit = write_agent_audit(state, run_dir)
    state["agent_audit"] = agent_audit
    storyboard = write_storyboard(state, run_dir)
    state["storyboard"] = storyboard
    rerun_recipe = write_rerun_recipe(state, run_dir)
    state["rerun_recipe"] = rerun_recipe
    write_json(run_dir / "agent_trace.json", state.get("execution_trace", []))
    write_json(
        run_dir / "run_metadata.json",
        {
            "run_id": state.get("run_id"),
            "query": state.get("user_query"),
            "data_path": state.get("data_path") or state.get("adata_path"),
            "dataset_hash": state.get("dataset_hash"),
            "dataset_summary": state.get("dataset_summary"),
            "environment": state.get("environment"),
            "parameters": state.get("parameters"),
            "approved_plan": state.get("approved_plan"),
            "plan_source": state.get("plan_source"),
            "plan_rationale": state.get("plan_rationale"),
            "llm_enabled": state.get("llm_enabled"),
            "project_signature": PROJECT_SIGNATURE,
            "acknowledgements": ACKNOWLEDGEMENTS,
            "tool_contracts": state.get("tool_contracts"),
            "llm_calls": state.get("llm_calls", []),
            "evidence_artifacts": state.get("evidence_artifacts", []),
            "evidence_claims": state.get("evidence_claims", []),
            "repair_log": state.get("repair_log", []),
            "quality": quality,
            "dataset_card": dataset_card,
            "agent_audit": agent_audit,
            "storyboard": storyboard,
            "rerun_recipe": rerun_recipe,
            "review_notes": state.get("review_notes"),
            "figures": state.get("generated_figures", []),
            "tables": state.get("generated_tables", []),
        },
    )
    write_yaml_simple(run_dir / "parameters.yaml", state.get("parameters", {}))
    if state.get("review_notes"):
        write_json(run_dir / "review_notes.json", state.get("review_notes", {}))

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
        repairs=state.get("repair_log", []),
        quality=quality,
        dataset_card=dataset_card,
        agent_audit=agent_audit,
        storyboard=storyboard,
        rerun_recipe=rerun_recipe,
        review=state.get("review_notes"),
        annotations=state.get("observations", {}).get("cluster_annotation_suggestions", []),
        warnings=state.get("warnings", []),
        errors=state.get("errors", []),
        project_signature=PROJECT_SIGNATURE,
        acknowledgements=ACKNOWLEDGEMENTS,
    )
    report_path = run_dir / "report.html"
    report_path.write_text(html, encoding="utf-8")
    readme_path = write_run_readme(state, run_dir=run_dir, report_path=report_path)

    write_json(run_dir / "state_public.json", public_state_copy(state))
    manifest = build_artifact_manifest(state, run_dir=run_dir, report_path=report_path)
    manifest_path = run_dir / "artifact_manifest.json"
    write_json(manifest_path, manifest)
    audit = write_artifact_audit(run_dir)
    state["artifact_audit"] = audit
    manifest = build_artifact_manifest(state, run_dir=run_dir, report_path=report_path)
    write_json(manifest_path, manifest)
    bundle = build_run_bundle(run_dir)
    audit = write_artifact_audit(run_dir)
    state["artifact_audit"] = audit
    manifest = build_artifact_manifest(state, run_dir=run_dir, report_path=report_path)
    write_json(manifest_path, manifest)
    return ToolResult(
        status="success",
        summary=f"Generated HTML report at {report_path}.",
        observations={
            "report_path": str(report_path),
            "run_readme_path": str(readme_path),
            "dataset_card_path": str(run_dir / "dataset_card.html"),
            "dataset_card_json_path": str(run_dir / "dataset_card.json"),
            "dataset_card_markdown_path": str(run_dir / "DATASET_CARD.md"),
            "agent_audit_path": str(run_dir / "agent_audit.json"),
            "storyboard_path": str(run_dir / "storyboard.html"),
            "storyboard_json_path": str(run_dir / "storyboard.json"),
            "rerun_recipe_path": str(run_dir / "rerun_recipe.json"),
            "rerun_markdown_path": str(run_dir / "RERUN.md"),
            "rerun_script_path": str(run_dir / "rerun.sh"),
            "artifact_audit_path": str(run_dir / "artifact_audit.json"),
            "artifact_manifest_path": str(manifest_path),
            "run_bundle_path": bundle["path"],
        },
    )
