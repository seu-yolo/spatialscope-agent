# SpatialScope Agent

[![CI](https://github.com/seu-yolo/spatialscope-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/seu-yolo/spatialscope-agent/actions/workflows/ci.yml)

SpatialScope Agent is an OpenAI-compatible LLM-powered, LangGraph-orchestrated workspace for spatial transcriptomics exploration. It turns a natural-language request into a traceable Scanpy/Squidpy workflow with figures, tables, interpretation, and a reproducibility bundle.

Project site: `https://seu-yolo.github.io/spatialscope-agent/`

## Features

- OpenAI-compatible LLM interface, configurable for GLM 5.1 or compatible providers
- LangGraph workflow with a deterministic fallback runner
- Structured LLM parsing/planning with Pydantic validation and rule-based fallback
- Open tool registry with tool contracts, preconditions, common failures, and repair strategies
- Structured repair diagnostics for failed or skipped steps, visible in trace, report, and manifest
- Quality Gates self-audit for dataset readiness, trace integrity, evidence outputs, interpretation, and reproducibility metadata
- `.h5ad` dataset inspection, QC, preprocessing, UMAP, Leiden clustering, marker genes
- Spatial cluster and gene expression visualization
- Gene fuzzy matching repair and gene panel plots
- Candidate cluster annotation suggestions from ranked marker genes and a compact marker lexicon
- Optional SVG and neighborhood enrichment when Squidpy is available
- HTML report, `agent_trace.json`, `run_metadata.json`, `parameters.yaml`, `artifact_manifest.json`
- Complete `run_bundle.zip` export for report, trace, metadata, figures, tables, and reproducibility assets
- CLI and a polished Streamlit analysis workspace
- Run Library and Run Compare for recent reports, reproducibility bundles, and side-by-side run audit
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
SPATIALSCOPE_LLM_TIMEOUT_SECONDS=45
```

Use the base URL from your GLM/OpenAI-compatible provider console. The local `.env`
file is ignored by Git. If no API key is configured, SpatialScope still runs a
rule-based demo planner for smoke tests.

## Agent Architecture

SpatialScope uses a LangGraph state machine:

```text
parse_request -> inspect_dataset -> plan_analysis -> preview_plan
-> execute_tool -> validate_result -> repair_or_continue
-> interpret -> report
```

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
Each run includes a complete `run_bundle.zip` plus an `artifact_manifest.json`
file that indexes the report,
trace, metadata, parameters, figures, tables, repair diagnostics, Quality Gates,
and public state bundle.

One-command demo:

```bash
scripts/run_demo.sh
```

## Streamlit

```bash
scripts/run_app.sh
```

Navigation:

1. Start: run the one-click Demo Launchpad, or upload data, enter a task, choose a run mode, tune QC/clustering/gene-panel controls, inspect recent runs in Run Library, and compare two runs side by side.
2. Analyze: review plan cards, inspect the LangGraph workflow state, edit JSON if needed, and execute the approved plan.
3. Explore: inspect figures, tables, trace records, Quality Gates, repair diagnostics, resolved genes, and candidate cluster labels.
4. Report: read the cautious interpretation and download the full reproducibility bundle or individual files.

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
