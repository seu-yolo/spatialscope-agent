from __future__ import annotations

import shlex
from datetime import datetime
from pathlib import Path
from typing import Any

from spatialscope.utils.paths import write_json


def _shell_join(parts: list[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in parts)


def _data_path_for_recipe(state: dict[str, Any]) -> str:
    return str(state.get("data_path") or state.get("adata_path") or "<DATA_PATH>")


def build_rerun_recipe(state: dict[str, Any]) -> dict[str, Any]:
    data_path = _data_path_for_recipe(state)
    outdir = str(state.get("outdir") or "outputs/runs")
    query = str(state.get("user_query") or "")
    mode = str(state.get("mode") or "quick")
    command = [
        "python",
        "cli.py",
        "run",
        "--data",
        data_path,
        "--query",
        query,
        "--mode",
        mode,
        "--outdir",
        outdir,
    ]
    conda_command = ["conda", "run", "--no-capture-output", "-n", "spatialscope-agent", *command]
    return {
        "schema_version": "1.0",
        "run_id": state.get("run_id"),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dataset_hash": state.get("dataset_hash"),
        "data_path": data_path,
        "query": query,
        "mode": mode,
        "outdir": outdir,
        "parameters": state.get("parameters", {}),
        "plan_source": state.get("plan_source"),
        "approved_plan": state.get("approved_plan", []),
        "command": command,
        "command_string": _shell_join(command),
        "conda_command": conda_command,
        "conda_command_string": _shell_join(conda_command),
        "notes": [
            "API keys are intentionally not stored in this recipe.",
            "Set LLM provider variables in `.env` before rerunning if LLM planning or interpretation is desired.",
            "If this run used an uploaded temporary file, replace data_path with a stable local `.h5ad` path.",
        ],
    }


def render_rerun_markdown(recipe: dict[str, Any]) -> str:
    notes = "\n".join(f"- {item}" for item in recipe.get("notes", [])) or "- None"
    plan_lines = []
    for step in recipe.get("approved_plan", []):
        if not isinstance(step, dict):
            continue
        plan_lines.append(f"- `{step.get('tool')}`: `{step.get('params', {})}`")
    if not plan_lines:
        plan_lines.append("- No approved plan was recorded.")
    return f"""# SpatialScope Rerun Recipe

This recipe captures how to rerun the SpatialScope Agent workflow without
storing secrets or raw expression matrices.

## Run

- Run ID: `{recipe.get("run_id")}`
- Mode: `{recipe.get("mode")}`
- Dataset hash: `{recipe.get("dataset_hash") or "N/A"}`
- Data path: `{recipe.get("data_path")}`
- Outdir: `{recipe.get("outdir")}`

## One-command Rerun

```bash
{recipe.get("conda_command_string")}
```

## Query

```text
{recipe.get("query") or ""}
```

## Parameters

```text
{recipe.get("parameters") or {}}
```

## Approved Plan

{chr(10).join(plan_lines)}

## Notes

{notes}
"""


def render_rerun_script(recipe: dict[str, Any]) -> str:
    query = shlex.quote(str(recipe.get("query") or ""))
    default_data_path = shlex.quote(str(recipe.get("data_path") or "<DATA_PATH>"))
    default_outdir = shlex.quote(str(recipe.get("outdir") or "outputs/runs"))
    mode = shlex.quote(str(recipe.get("mode") or "quick"))
    return f"""#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${{SPATIALSCOPE_PROJECT_DIR:-$(cd "$(dirname "$0")/../../.." && pwd)}}"
DATA_PATH="${{1:-}}"
OUTDIR="${{2:-}}"
if [[ -z "$DATA_PATH" ]]; then
  DATA_PATH={default_data_path}
fi
if [[ -z "$OUTDIR" ]]; then
  OUTDIR={default_outdir}
fi

cd "$PROJECT_DIR"
conda run --no-capture-output -n spatialscope-agent python cli.py run \\
  --data "$DATA_PATH" \\
  --query {query} \\
  --mode {mode} \\
  --outdir "$OUTDIR"
"""


def write_rerun_recipe(state: dict[str, Any], run_dir: str | Path | None = None) -> dict[str, Any]:
    root = Path(str(run_dir or state.get("run_dir") or "."))
    root.mkdir(parents=True, exist_ok=True)
    recipe = build_rerun_recipe(state)
    write_json(root / "rerun_recipe.json", recipe)
    (root / "RERUN.md").write_text(render_rerun_markdown(recipe), encoding="utf-8")
    script_path = root / "rerun.sh"
    script_path.write_text(render_rerun_script(recipe), encoding="utf-8")
    try:
        script_path.chmod(script_path.stat().st_mode | 0o111)
    except Exception:
        pass
    return recipe
