# SpatialScope Agent

[![CI](https://github.com/seu-yolo/spatialscope-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/seu-yolo/spatialscope-agent/actions/workflows/ci.yml)

SpatialScope Agent is an OpenAI-compatible LLM-powered, LangGraph-orchestrated workspace for spatial transcriptomics exploration. It turns a natural-language request into a traceable Scanpy/Squidpy workflow with figures, tables, interpretation, and a reproducibility bundle.

Project site: `https://seu-yolo.github.io/spatialscope-agent/`

## Features

- OpenAI-compatible LLM interface, configurable for GLM 5.1 or compatible providers
- Safe LLM Control Center with masked key display, provider/model status, fallback explanation, and optional smoke test
- LangGraph workflow with SQLite checkpoints, stable thread IDs, and a deterministic fallback path
- Structured LLM parsing/planning with Pydantic validation and rule-based fallback
- Open tool registry with tool contracts, preconditions, common failures, and repair strategies
- Structured repair diagnostics for failed or skipped steps, visible in trace, report, and manifest
- Quality Gates self-audit for dataset readiness, trace integrity, evidence outputs, interpretation, and reproducibility metadata
- Agent Audit for contract-bound planning, execution coverage, repair accountability, evidence-bounded interpretation, and public-state privacy checks
- Dataset Card (`dataset_card.html`/`dataset_card.json`/`DATASET_CARD.md`) for data suitability, schema preview, spatial-coordinate status, recommended run depth, and privacy boundary
- Human Review notes with decision, confidence, tags, Quality Gate overrides, reviewer comments, and bundle integration
- `.h5ad` dataset inspection, QC, preprocessing, UMAP, Leiden clustering, marker genes
- Spatial cluster and gene expression visualization
- Gene fuzzy matching repair and gene panel plots
- Candidate cluster annotation suggestions from ranked marker genes and a compact marker lexicon when explicitly requested
- Optional SVG and neighborhood enrichment when Squidpy is available
- Spatial Storyboard (`storyboard.html`/`storyboard.json`) that turns key figures into a presentation-oriented visual narrative
- Run Replay Recipe (`RERUN.md`, `rerun_recipe.json`, `rerun.sh`) for safe, secret-free reruns
- HTML report, run-level `README.md`, `dataset_card.html`, `DATASET_CARD.md`, `agent_trace.json`, `run_metadata.json`, `parameters.yaml`, `review_notes.json`, `agent_audit.json`, `artifact_manifest.json`
- Artifact Audit with file existence, size, kind counts, missing-artifact warnings, and bundle status
- Complete `run_bundle.zip` export for report, trace, metadata, figures, tables, and reproducibility assets
- CLI and a polished Streamlit analysis workspace
- Run Library, historical run rehydration, and Run Compare for reproducibility bundles and side-by-side audit
- Streamlit Demo Launchpad for one-click standard showcase runs on bundled synthetic spatial data

## Setup

```bash
conda env create -f environment.yml
conda activate spatialscope-agent
python -m pip install -e ".[dev]"
cp .env.example .env
```

`environment.yml` installs the stable core environment: Streamlit, LangGraph, Scanpy,
AnnData, plotting, reporting, and tests. The advanced Squidpy extension can be added
after the core demo is working:

```bash
conda env update -n spatialscope-agent -f environment-squidpy.yml
```

If Squidpy is not installed, Advanced Mode records SVG/neighborhood steps as
structured warnings instead of crashing.

Edit `.env`:

```bash
SPATIALSCOPE_LLM_API_KEY=...
SPATIALSCOPE_LLM_BASE_URL=...
SPATIALSCOPE_LLM_MODEL=glm-5.1
SPATIALSCOPE_LLM_TIMEOUT_SECONDS=15
```

Use the base URL from your GLM/OpenAI-compatible provider console. The local `.env`
file is ignored by Git. If no API key is configured, SpatialScope still runs a
rule-based demo planner for smoke tests.

Check LLM configuration without exposing secrets:

```bash
python cli.py llm-check
python cli.py llm-check --json
python cli.py llm-check --live
```

`--live` sends a tiny JSON smoke prompt to the configured provider. Without
`--live`, the command only inspects local configuration and fallback behavior.

## Agent Architecture

SpatialScope uses a LangGraph state machine:

```text
parse_request -> inspect_dataset -> plan_analysis -> review_plan
-> execute_tool -> validate_result -> repair_or_continue
-> interpret -> report
```

`review_plan` uses a real LangGraph interrupt/resume checkpoint. The CLI auto-approves
the generated plan for unattended smoke runs, while Streamlit exposes the pause so the
user can inspect and edit the plan before execution.

The tool layer is registry-driven. Each analysis tool exposes a contract with
preconditions, postconditions, common failures, and repair strategies. The configured
LLM can use these contracts to generate structured analysis plans, while the
deterministic planner keeps demos reproducible when no API key is available.
When a step fails, SpatialScope writes a repair diagnosis with failure category,
likely cause, action taken, and recommended next actions instead of silently
continuing.

The LLM never receives raw expression matrices or raw coordinate matrices. It only
sees dataset summaries, tool contracts, execution summaries, figure/table metadata,
and warnings/errors.

Design references and rationale are summarized in
[`docs/AGENT_DESIGN_REFERENCES.md`](docs/AGENT_DESIGN_REFERENCES.md).
The product direction and quality bar are summarized in
[`docs/PRODUCT_BRIEF.md`](docs/PRODUCT_BRIEF.md).

## Demo Data

Generate a tiny synthetic spatial AnnData file:

```bash
python scripts/create_demo_data.py --output data/demo_tiny.h5ad
```

## CLI

```bash
python cli.py run \
  --data data/demo_tiny.h5ad \
  --query "Run quick spatial analysis and plot GeneA, GeneB" \
  --mode quick
```

Outputs are written to `outputs/runs/<run_id>/`.
Each run includes a handoff-ready `README.md`, a complete `run_bundle.zip`, plus
an `artifact_manifest.json` file that indexes the report,
trace, metadata, parameters, figures, tables, repair diagnostics, Quality Gates,
Agent Audit, Dataset Card, Spatial Storyboard, Run Replay Recipe, Human Review notes, Artifact Audit, and public state bundle.

One-command demo:

```bash
scripts/run_demo.sh
```

## Streamlit

```bash
scripts/run_app.sh
```

Navigation:

1. Workspace: run the Demo Launchpad, upload/select data, write the research request, tune QC/clustering/gene controls, and generate or directly run a plan.
2. Plan: review the interrupted LangGraph plan, inspect dataset profile fields, edit JSON, validate it, and resume execution.
3. Run: inspect workflow status, execution trace, repair diagnostics, Quality Gates, Agent Audit, and Artifact Audit.
4. Explore: browse figures/tables and use the evidence-bounded contextual copilot for cautious figure explanation.
5. Report: read the final summary, preview/download the report, and export the reproducibility bundle.
6. Provenance: inspect LLM status, telemetry, tool contracts, run library, and public state JSON.

## Public Web Deployment

`localhost:8501` is only visible on your own computer. To share a link that anyone
can open, deploy the Streamlit app to a Python-hosting platform.

Recommended path: Streamlit Community Cloud.

1. Make sure the latest `main` branch is pushed to GitHub.
2. Open Streamlit Community Cloud and create a new app from:
   - Repository: `seu-yolo/spatialscope-agent`
   - Branch: `main`
   - Main file path: `app.py`
3. In Advanced settings, choose Python `3.11`.
4. Add secrets in the app settings. Do not commit these values to GitHub:

```toml
SPATIALSCOPE_LLM_PROVIDER = "openai_compatible"
SPATIALSCOPE_LLM_API_KEY = "your_glm_api_key_here"
SPATIALSCOPE_LLM_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"
SPATIALSCOPE_LLM_MODEL = "glm-5.1"
SPATIALSCOPE_LLM_TIMEOUT_SECONDS = "15"
```

The repository already includes `environment.yml`, which Streamlit Community Cloud
can use to install the Python dependencies. The deployed app will get a public
`*.streamlit.app` URL.

GitHub Pages is different: it can host the static project site in `docs/`, but it
cannot run the interactive Streamlit/LangGraph/Scanpy backend by itself.

## Tests

```bash
pytest
```

Full local health check:

```bash
scripts/check_project.sh
```

The lightweight tests avoid requiring Scanpy/Squidpy so they can validate project logic before the full scientific environment is installed.

## GitHub Project Management

- `main` is the stable, presentation-ready branch.
- GitHub Actions runs tests and a CLI smoke demo on push and pull request.
- GitHub Pages can serve the static project site from the `docs/` directory.
- Product quality notes are in [`docs/PRODUCT_BRIEF.md`](docs/PRODUCT_BRIEF.md).
- Repository workflow notes are in [`docs/GIT_WORKFLOW.md`](docs/GIT_WORKFLOW.md).
- Contribution notes are in [`CONTRIBUTING.md`](CONTRIBUTING.md).

GitHub Pages must be enabled once in repository settings: Pages -> Deploy from a branch -> `main` -> `/docs`.
