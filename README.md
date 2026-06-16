# SpatialScope Agent

SpatialScope Agent is an OpenAI-compatible LLM-powered, LangGraph-orchestrated workspace for spatial transcriptomics exploration. It turns a natural-language request into a traceable Scanpy/Squidpy workflow with figures, tables, interpretation, and a reproducibility bundle.

## Features

- OpenAI-compatible LLM interface, configurable for GLM 5.1 or compatible providers
- LangGraph workflow with a deterministic fallback runner
- Structured LLM parsing/planning with Pydantic validation and rule-based fallback
- Open tool registry with tool contracts, preconditions, common failures, and repair strategies
- `.h5ad` dataset inspection, QC, preprocessing, UMAP, Leiden clustering, marker genes
- Spatial cluster and gene expression visualization
- Gene fuzzy matching repair and gene panel plots
- Optional SVG and neighborhood enrichment when Squidpy is available
- HTML report, `agent_trace.json`, `run_metadata.json`, `parameters.yaml`
- CLI and Streamlit UI

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

The LLM never receives raw expression matrices or raw coordinate matrices. It only
sees dataset summaries, tool contracts, execution summaries, figure/table metadata,
and warnings/errors.

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

## Streamlit

```bash
streamlit run app.py
```

Navigation:

1. Start: upload data, enter a task, and generate a draft plan.
2. Analyze: review/edit plan JSON, validate it, and execute the approved plan.
3. Explore: inspect figures and tables.
4. Report: download the reproducibility bundle.

## Tests

```bash
pytest
```

The lightweight tests avoid requiring Scanpy/Squidpy so they can validate project logic before the full scientific environment is installed.
