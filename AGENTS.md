# SpatialScope Agent Repository Guide

## Architecture Boundaries

- Streamlit must call the compiled LangGraph through `spatialscope.agent.runtime.AgentRuntime`.
- `app.py` is a router/bootstrap file. UI code belongs under `spatialscope/ui/`.
- Graph checkpoint state must stay JSON-serializable. Never store AnnData objects, LLM clients, file handles, or raw matrices in graph state.
- Scientific tools may operate on AnnData only across the runtime/tool boundary through `DatasetStore`.
- Provenance, audits, bundles, replay recipes, and raw JSON downloads belong in Provenance or advanced sections, not the primary Workspace journey.

## Scientific Guardrails

- Do not assume unknown `adata.X` is raw counts.
- Use explicit expression lineage and layer selection for preprocessing, marker ranking, and gene/spatial plots.
- Marker and gene-expression plots should use the interpretation expression layer unless the user explicitly selects another safe layer.
- Candidate cluster annotation is off by default and must be framed as marker-overlap evidence, not confirmed cell identity.
- LLM calls must never receive raw expression matrices, full coordinate arrays, secrets, or large unbounded tables.

## Test Commands

```bash
conda run --no-capture-output -n spatialscope-agent pytest -q
conda run --no-capture-output -n spatialscope-agent bash scripts/check_project.sh
SPATIALSCOPE_LLM_API_KEY='' DEEPSEEK_API_KEY='' conda run --no-capture-output -n spatialscope-agent python cli.py run --data data/demo_tiny.h5ad --query "Run quick spatial analysis and plot GeneA GeneB" --mode quick --outdir outputs/runs
```

## Git Hygiene

- Do not commit `.env`, generated run outputs, large `.h5ad` files beyond the tiny demo, caches, or secrets.
- Keep `main` runnable. Prefer small, reviewable commits that preserve CLI/demo fallback behavior.
