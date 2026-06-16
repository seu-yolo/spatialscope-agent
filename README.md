# SpatialScope Agent

SpatialScope Agent is a DeepSeek-powered, LangGraph-orchestrated workspace for spatial transcriptomics exploration. It turns a natural-language request into a traceable Scanpy/Squidpy workflow with figures, tables, interpretation, and a reproducibility bundle.

## Features

- DeepSeek-only LLM interface using `deepseek-v4-flash`
- LangGraph workflow with a deterministic fallback runner
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
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://api.deepseek.com
SPATIALSCOPE_LLM_MODEL=deepseek-v4-flash
```

If no API key is configured, SpatialScope still runs a rule-based demo planner for smoke tests.

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

1. Start: upload data and enter a task.
2. Analyze: preview the plan and execute it.
3. Explore: inspect figures and tables.
4. Report: download the reproducibility bundle.

## Tests

```bash
pytest
```

The lightweight tests avoid requiring Scanpy/Squidpy so they can validate project logic before the full scientific environment is installed.
