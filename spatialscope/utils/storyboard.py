from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from jinja2 import Template

from spatialscope.utils.paths import write_json


PROJECT_SIGNATURE = "seu-yolo / Southeast University Computational Biology"

ROLE_RULES = [
    (
        "gene",
        ("gene panel", "gene_panel", "expression"),
        "Gene Signal",
        "How selected genes vary across spatial positions.",
        2,
    ),
    (
        "spatial",
        ("spatial", "tissue"),
        "Tissue Map",
        "Where expression-defined structure appears in physical space.",
        0,
    ),
    (
        "umap",
        ("umap", "embedding"),
        "Latent Structure",
        "How spots organize after preprocessing and neighborhood graph construction.",
        1,
    ),
    (
        "marker",
        ("marker", "heatmap", "rank"),
        "Marker Evidence",
        "Which genes support cluster-level interpretation.",
        3,
    ),
    (
        "annotation",
        ("annotation", "candidate", "label"),
        "Candidate Labels",
        "How marker evidence maps to cautious biological labels.",
        4,
    ),
    (
        "qc",
        ("qc", "quality", "highly variable", "variable genes", "hvg"),
        "Quality Context",
        "Whether the input data and filtering choices look reasonable.",
        5,
    ),
]


STORYBOARD_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>SpatialScope Storyboard - {{ run_id }}</title>
  <style>
    :root {
      --ink: #172026;
      --muted: #66737f;
      --line: #d9e2e8;
      --paper: #fbfcfd;
      --teal: #0f766e;
      --teal-soft: #d9efed;
      --plum: #6f4e8f;
      --plum-soft: #eee7f4;
      --amber: #b7791f;
      --amber-soft: #f7ead3;
      --rose: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background:
        linear-gradient(90deg, rgba(15, 118, 110, 0.035) 1px, transparent 1px),
        linear-gradient(0deg, rgba(111, 78, 143, 0.025) 1px, transparent 1px),
        var(--paper);
      background-size: 34px 34px;
      font-family: "PingFang SC", "Noto Sans CJK SC", "Microsoft YaHei", Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }
    main { max-width: 1260px; margin: 0 auto; padding: 34px 28px 54px; }
    header {
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(280px, 0.9fr);
      gap: 26px;
      align-items: end;
      border-bottom: 1px solid var(--line);
      padding-bottom: 24px;
    }
    h1 { font-size: 40px; line-height: 1.02; margin: 0 0 10px; letter-spacing: 0; }
    h2 { font-size: 18px; margin: 24px 0 12px; letter-spacing: 0; }
    p { margin: 8px 0; }
    .eyebrow { color: var(--teal); font-size: 12px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; }
    .muted { color: var(--muted); }
    .tag {
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      display: inline-block;
      font-size: 12px;
      margin: 4px 5px 0 0;
      padding: 3px 9px;
      background: rgba(255,255,255,0.72);
    }
    .metrics { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
    .metric {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255,255,255,0.8);
      padding: 12px;
    }
    .metric span { display: block; color: var(--muted); font-size: 11px; text-transform: uppercase; }
    .metric strong { display: block; font-size: 18px; margin-top: 4px; }
    .hero {
      display: grid;
      grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
      gap: 18px;
      margin: 24px 0 18px;
      align-items: stretch;
    }
    .panel, .tile {
      border: 1px solid var(--line);
      border-radius: 10px;
      background: rgba(255,255,255,0.86);
      box-shadow: 0 12px 30px rgba(23, 32, 38, 0.06);
    }
    .panel { padding: 18px; }
    .hero-img {
      width: 100%;
      min-height: 390px;
      object-fit: contain;
      border-radius: 8px;
      border: 1px solid #edf1f5;
      background: white;
    }
    .tile-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 14px; }
    .tile { overflow: hidden; }
    .tile img {
      display: block;
      width: 100%;
      height: 210px;
      object-fit: contain;
      background: white;
      border-bottom: 1px solid #edf1f5;
    }
    .tile-body { padding: 12px 13px 14px; }
    .tile h3 { font-size: 14px; margin: 0 0 5px; letter-spacing: 0; }
    .role { color: var(--plum); font-size: 11px; font-weight: 800; letter-spacing: 0.06em; text-transform: uppercase; }
    .caption { color: var(--muted); font-size: 13px; }
    .ribbon {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }
    .pill {
      border-radius: 999px;
      font-size: 12px;
      padding: 4px 10px;
      background: var(--teal-soft);
      color: var(--teal);
      font-weight: 700;
    }
    .pill.plum { background: var(--plum-soft); color: var(--plum); }
    .pill.amber { background: var(--amber-soft); color: var(--amber); }
    .empty { border: 1px dashed var(--line); border-radius: 10px; padding: 28px; color: var(--muted); }
    footer { border-top: 1px solid var(--line); color: var(--muted); font-size: 12px; margin-top: 28px; padding-top: 14px; }
    @media (max-width: 900px) {
      header, .hero { grid-template-columns: 1fr; }
      .tile-grid { grid-template-columns: 1fr; }
      .hero-img { min-height: 260px; }
    }
  </style>
</head>
<body>
<main>
  <header>
    <div>
      <div class="eyebrow">SpatialScope Storyboard</div>
      <h1>One Run, One Spatial Story</h1>
      <p class="muted">{{ query }}</p>
      <div>
        <span class="tag">run={{ run_id }}</span>
        <span class="tag">mode={{ mode }}</span>
        <span class="tag">plan={{ plan_source }}</span>
        <span class="tag">LLM={{ "enabled" if llm_enabled else "fallback" }}</span>
      </div>
    </div>
    <div class="metrics">
      <div class="metric"><span>Spots</span><strong>{{ metrics.spots }}</strong></div>
      <div class="metric"><span>Genes</span><strong>{{ metrics.genes }}</strong></div>
      <div class="metric"><span>Quality</span><strong>{{ metrics.quality }}</strong></div>
      <div class="metric"><span>Agent</span><strong>{{ metrics.agent }}</strong></div>
    </div>
  </header>

  {% if hero %}
  <section class="hero">
    <div class="panel">
      <div class="role">{{ hero.role_label }}</div>
      <h2>{{ hero.title }}</h2>
      <p class="caption">{{ hero.caption }}</p>
      <div class="ribbon">
        <span class="pill">{{ metrics.figures }} figures</span>
        <span class="pill plum">{{ metrics.tables }} tables</span>
        <span class="pill amber">{{ metrics.trace }} trace steps</span>
      </div>
    </div>
    <div class="panel">
      <img class="hero-img" src="{{ hero.relpath }}" alt="{{ hero.title }}">
    </div>
  </section>
  {% else %}
  <section class="empty">No figure artifacts were available for this storyboard.</section>
  {% endif %}

  {% if cards %}
  <section>
    <h2>Visual Evidence Board</h2>
    <div class="tile-grid">
      {% for card in cards %}
      <article class="tile">
        <img src="{{ card.relpath }}" alt="{{ card.title }}">
        <div class="tile-body">
          <div class="role">{{ card.role_label }}</div>
          <h3>{{ card.title }}</h3>
          <div class="caption">{{ card.caption }}</div>
        </div>
      </article>
      {% endfor %}
    </div>
  </section>
  {% endif %}

  <footer>
    {{ signature }} · Generated from traceable SpatialScope Agent artifacts.
  </footer>
</main>
</body>
</html>
"""


def _relpath(path_value: Any, *, run_dir: Path) -> str:
    path = Path(str(path_value or ""))
    try:
        return str(path.relative_to(run_dir))
    except Exception:
        return str(path)


def _figure_text(figure: dict[str, Any]) -> str:
    return (
        " ".join(
            [
                str(figure.get("title") or ""),
                Path(str(figure.get("path") or "")).name,
            ]
        )
        .replace("_", " ")
        .replace("-", " ")
        .lower()
    )


def _caption_text(figure: dict[str, Any]) -> str:
    return " ".join(
        [
            str(figure.get("caption") or ""),
        ]
    ).lower()


def _classify_figure(figure: dict[str, Any]) -> tuple[int, str, str, str]:
    strong_text = _figure_text(figure)
    caption_text = _caption_text(figure)
    for _, (role, keywords, label, default_caption, priority) in enumerate(ROLE_RULES):
        if any(keyword in strong_text for keyword in keywords):
            return priority, role, label, default_caption
    for _, (role, keywords, label, default_caption, priority) in enumerate(ROLE_RULES):
        if any(keyword in caption_text for keyword in keywords):
            return priority, role, label, default_caption
    return len(ROLE_RULES), "evidence", "Evidence", "A generated analysis artifact from this run."


def _story_cards(figures: list[dict[str, Any]], *, run_dir: Path, max_cards: int = 6) -> list[dict[str, Any]]:
    candidates: list[tuple[int, int, dict[str, Any]]] = []
    for original_index, figure in enumerate(figures):
        if not isinstance(figure, dict):
            continue
        raw_path = figure.get("path")
        if not raw_path or not Path(str(raw_path)).is_file():
            continue
        priority, role, role_label, default_caption = _classify_figure(figure)
        title = str(figure.get("title") or Path(str(raw_path)).name)
        caption = str(figure.get("caption") or default_caption)
        card = {
            "role": role,
            "role_label": role_label,
            "title": title,
            "caption": caption,
            "path": str(raw_path),
            "relpath": _relpath(raw_path, run_dir=run_dir),
            "svg_path": str(figure.get("svg_path") or ""),
            "svg_relpath": _relpath(figure.get("svg_path"), run_dir=run_dir) if figure.get("svg_path") else "",
        }
        candidates.append((priority, original_index, card))
    candidates.sort(key=lambda item: (item[0], item[1]))
    return [card for _, _, card in candidates[:max_cards]]


def build_storyboard(state: dict[str, Any], *, run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir)
    dataset = state.get("dataset_summary") if isinstance(state.get("dataset_summary"), dict) else {}
    quality = state.get("quality") if isinstance(state.get("quality"), dict) else {}
    agent_audit = state.get("agent_audit") if isinstance(state.get("agent_audit"), dict) else {}
    figures = [item for item in state.get("generated_figures", []) if isinstance(item, dict)]
    tables = [item for item in state.get("generated_tables", []) if isinstance(item, dict)]
    trace = [item for item in state.get("execution_trace", []) if isinstance(item, dict)]
    cards = _story_cards(figures, run_dir=root)
    hero = cards[0] if cards else {}
    metrics = {
        "spots": dataset.get("n_obs", "NA"),
        "genes": dataset.get("n_vars", "NA"),
        "figures": len(figures),
        "tables": len(tables),
        "trace": len(trace),
        "quality": f"{quality.get('score', 'NA')} / {quality.get('overall_status', 'unknown')}",
        "agent": f"{agent_audit.get('score', 'NA')} / {agent_audit.get('overall_status', 'unknown')}",
    }
    return {
        "schema_version": "1.0",
        "run_id": state.get("run_id") or root.name,
        "query": state.get("user_query") or "",
        "mode": state.get("mode") or "unknown",
        "plan_source": state.get("plan_source") or "unknown",
        "llm_enabled": bool(state.get("llm_enabled")),
        "metrics": metrics,
        "hero": hero,
        "cards": cards,
        "n_cards": len(cards),
        "storyboard_path": str(root / "storyboard.html"),
        "storyboard_json_path": str(root / "storyboard.json"),
    }


def render_storyboard_html(storyboard: dict[str, Any]) -> str:
    def escape_value(value: Any) -> Any:
        if isinstance(value, str):
            return html.escape(value, quote=True)
        if isinstance(value, dict):
            return {key: escape_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [escape_value(item) for item in value]
        return value

    safe_storyboard = escape_value(storyboard)
    template = Template(STORYBOARD_TEMPLATE)
    return template.render(
        run_id=safe_storyboard.get("run_id") or "",
        query=safe_storyboard.get("query") or "",
        mode=safe_storyboard.get("mode") or "unknown",
        plan_source=safe_storyboard.get("plan_source") or "unknown",
        llm_enabled=bool(storyboard.get("llm_enabled")),
        metrics=safe_storyboard.get("metrics") or {},
        hero=safe_storyboard.get("hero") or {},
        cards=safe_storyboard.get("cards") or [],
        signature=PROJECT_SIGNATURE,
    )


def write_storyboard(state: dict[str, Any], run_dir: str | Path | None = None) -> dict[str, Any]:
    root = Path(str(run_dir or state.get("run_dir") or "."))
    root.mkdir(parents=True, exist_ok=True)
    storyboard = build_storyboard(state, run_dir=root)
    html_text = render_storyboard_html(storyboard)
    (root / "storyboard.html").write_text(html_text, encoding="utf-8")
    write_json(root / "storyboard.json", storyboard)
    return storyboard
