from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Template

from spatialscope.utils.paths import write_json


DATASET_CARD_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>SpatialScope Dataset Card - {{ run_id }}</title>
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
      --rose-soft: #f9e3e0;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background: var(--paper);
      font-family: "PingFang SC", "Noto Sans CJK SC", "Microsoft YaHei", Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }
    main { max-width: 1120px; margin: 0 auto; padding: 34px 28px 52px; }
    header { border-bottom: 1px solid var(--line); padding-bottom: 20px; }
    h1 { font-size: 38px; margin: 0 0 8px; letter-spacing: 0; }
    h2 { font-size: 18px; margin: 26px 0 12px; letter-spacing: 0; }
    .eyebrow { color: var(--teal); font-size: 12px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; }
    .muted { color: var(--muted); }
    .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin: 18px 0; }
    .metric, .check {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 12px;
    }
    .metric span { display: block; color: var(--muted); font-size: 11px; text-transform: uppercase; }
    .metric strong { display: block; font-size: 18px; margin-top: 4px; }
    .checks { display: grid; gap: 10px; }
    .badge { border-radius: 999px; display: inline-block; font-size: 12px; font-weight: 700; padding: 3px 9px; }
    .pass { background: var(--teal-soft); color: var(--teal); }
    .warn { background: var(--amber-soft); color: var(--amber); }
    .fail { background: var(--rose-soft); color: var(--rose); }
    pre { background: #f3f6f8; border: 1px solid var(--line); border-radius: 8px; overflow-x: auto; padding: 12px; }
    footer { border-top: 1px solid var(--line); color: var(--muted); font-size: 12px; margin-top: 30px; padding-top: 14px; }
  </style>
</head>
<body>
<main>
  <header>
    <div class="eyebrow">SpatialScope Dataset Card</div>
    <h1>Data Before Interpretation</h1>
    <p class="muted">{{ data_path }}</p>
  </header>
  <section class="metrics">
    <div class="metric"><span>Observations</span><strong>{{ metrics.n_obs }}</strong></div>
    <div class="metric"><span>Genes</span><strong>{{ metrics.n_vars }}</strong></div>
    <div class="metric"><span>Spatial</span><strong>{{ metrics.spatial }}</strong></div>
    <div class="metric"><span>Recommended mode</span><strong>{{ recommended_mode }}</strong></div>
    <div class="metric"><span>Dataset hash</span><strong>{{ short_hash }}</strong></div>
  </section>

  <h2>Suitability Checks</h2>
  <section class="checks">
    {% for check in checks %}
    <article class="check">
      <span class="badge {{ check.status }}">{{ check.status }}</span>
      <strong>{{ check.name }}</strong>
      <p>{{ check.summary }}</p>
      <p class="muted">{{ check.recommendation }}</p>
    </article>
    {% endfor %}
  </section>

  <h2>Schema Preview</h2>
  <pre>{{ schema_preview_json }}</pre>

  <h2>Privacy Boundary</h2>
  <p class="muted">{{ privacy_note }}</p>

  <footer>{{ signature }}</footer>
</main>
</body>
</html>
"""


def _check(name: str, status: str, summary: str, recommendation: str = "") -> dict[str, str]:
    if status not in {"pass", "warn", "fail"}:
        status = "warn"
    return {"name": name, "status": status, "summary": summary, "recommendation": recommendation}


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _recommended_mode(dataset: dict[str, Any]) -> str:
    n_obs = _as_int(dataset.get("n_obs"))
    n_vars = _as_int(dataset.get("n_vars"))
    has_spatial = bool(dataset.get("has_spatial"))
    if not has_spatial:
        return "quick"
    if n_obs >= 50 and n_vars >= 50:
        return "standard"
    return "quick"


def build_dataset_card(state: dict[str, Any]) -> dict[str, Any]:
    dataset = state.get("dataset_summary") if isinstance(state.get("dataset_summary"), dict) else {}
    n_obs = _as_int(dataset.get("n_obs"))
    n_vars = _as_int(dataset.get("n_vars"))
    has_spatial = bool(dataset.get("has_spatial"))
    dataset_hash = str(state.get("dataset_hash") or dataset.get("dataset_hash") or "")
    data_path = str(state.get("data_path") or state.get("adata_path") or "")
    checks: list[dict[str, str]] = []

    if n_obs and n_vars:
        checks.append(_check("Shape", "pass", f"{n_obs} observations x {n_vars} genes were detected."))
    else:
        checks.append(_check("Shape", "fail", "Dataset dimensions were not recorded.", "Inspect the AnnData input and rerun dataset inspection."))

    if has_spatial:
        shape = dataset.get("spatial_shape") or "unknown shape"
        checks.append(_check("Spatial coordinates", "pass", f"`adata.obsm['spatial']` is available with shape {shape}."))
    else:
        checks.append(_check("Spatial coordinates", "warn", "No spatial coordinate matrix was detected.", "Spatial plots and neighborhood methods will be skipped or need a spatial AnnData input."))

    if dataset_hash:
        checks.append(_check("Dataset fingerprint", "pass", f"Dataset hash is recorded: {dataset_hash[:12]}..."))
    else:
        checks.append(_check("Dataset fingerprint", "warn", "Dataset hash is missing.", "Use `.h5ad` input through the standard loader to capture a reproducibility fingerprint."))

    if n_obs < 20 or n_vars < 20:
        checks.append(_check("Scale", "warn", "This looks like a tiny or demo-sized dataset.", "Use conclusions only for workflow demonstration unless this is expected."))
    else:
        checks.append(_check("Scale", "pass", "Dataset scale is sufficient for basic exploratory workflow checks."))

    recommended_mode = _recommended_mode(dataset)
    metrics = {
        "n_obs": n_obs or "NA",
        "n_vars": n_vars or "NA",
        "spatial": "yes" if has_spatial else "no",
        "obs_columns": len(dataset.get("obs_columns", []) or []),
        "var_columns": len(dataset.get("var_columns", []) or []),
    }
    schema_preview = {
        "obs_columns": dataset.get("obs_columns", []),
        "var_columns": dataset.get("var_columns", []),
        "obsm_keys": dataset.get("obsm_keys", []),
        "layer_keys": dataset.get("layer_keys", []),
        "var_names_preview": dataset.get("var_names_preview", []),
        "obs_names_preview": dataset.get("obs_names_preview", []),
        "spatial_bounds": dataset.get("spatial_bounds", {}),
    }
    return {
        "schema_version": "1.0",
        "run_id": state.get("run_id"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "data_path": data_path,
        "dataset_hash": dataset_hash,
        "short_hash": dataset_hash[:12] if dataset_hash else "NA",
        "metrics": metrics,
        "recommended_mode": recommended_mode,
        "checks": checks,
        "schema_preview": schema_preview,
        "privacy_note": "This card stores only summaries and schema previews. It does not include raw expression matrices or full spatial coordinate arrays.",
    }


def render_dataset_card_markdown(card: dict[str, Any]) -> str:
    checks = "\n".join(
        (
            f"- {item.get('name')}: {item.get('status')} - {item.get('summary')}"
            + (f" Recommendation: {item.get('recommendation')}" if item.get("recommendation") else "")
        )
        for item in card.get("checks", [])
    )
    schema_preview = json.dumps(card.get("schema_preview", {}), ensure_ascii=False, indent=2)
    return f"""# SpatialScope Dataset Card

## Dataset

- Run ID: `{card.get("run_id")}`
- Data path: `{card.get("data_path") or "N/A"}`
- Dataset hash: `{card.get("dataset_hash") or "N/A"}`
- Recommended mode: `{card.get("recommended_mode")}`

## Metrics

- Observations: {card.get("metrics", {}).get("n_obs")}
- Genes: {card.get("metrics", {}).get("n_vars")}
- Spatial coordinates: {card.get("metrics", {}).get("spatial")}

## Checks

{checks or "- No checks recorded."}

## Privacy

{card.get("privacy_note")}

## Schema Preview

```json
{schema_preview}
```
"""


def render_dataset_card_html(card: dict[str, Any]) -> str:
    def escape_value(value: Any) -> Any:
        if isinstance(value, str):
            return html.escape(value, quote=True)
        if isinstance(value, list):
            return [escape_value(item) for item in value]
        if isinstance(value, dict):
            return {key: escape_value(item) for key, item in value.items()}
        return value

    safe = escape_value(card)
    return Template(DATASET_CARD_TEMPLATE).render(
        run_id=safe.get("run_id") or "",
        data_path=safe.get("data_path") or "N/A",
        metrics=safe.get("metrics") or {},
        recommended_mode=safe.get("recommended_mode") or "unknown",
        short_hash=safe.get("short_hash") or "NA",
        checks=safe.get("checks") or [],
        schema_preview_json=html.escape(json.dumps(card.get("schema_preview", {}), ensure_ascii=False, indent=2)),
        privacy_note=safe.get("privacy_note") or "",
        signature="seu-yolo / SpatialScope Agent",
    )


def write_dataset_card(state: dict[str, Any], run_dir: str | Path | None = None) -> dict[str, Any]:
    root = Path(str(run_dir or state.get("run_dir") or "."))
    root.mkdir(parents=True, exist_ok=True)
    card = build_dataset_card(state)
    write_json(root / "dataset_card.json", card)
    (root / "DATASET_CARD.md").write_text(render_dataset_card_markdown(card), encoding="utf-8")
    (root / "dataset_card.html").write_text(render_dataset_card_html(card), encoding="utf-8")
    return card
