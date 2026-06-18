# SpatialScope v2 Demo Script

## Fixed Classroom Flow

Research task:

> Inspect an early mouse embryo spatial dataset, assess quality, show Sox17/T/Mesp1
> spatial expression, identify spatially variable genes, and avoid recomputing
> compatible existing results unless necessary.

## Local Demo Commands

```bash
conda activate spatialscope-agent
python scripts/create_demo_data.py --output data/demo_tiny.h5ad
SPATIALSCOPE_LLM_API_KEY='' DEEPSEEK_API_KEY='' python cli.py run \
  --data data/demo_tiny.h5ad \
  --query "Inspect an early mouse embryo spatial dataset, assess quality, show Sox17 T Mesp1 spatial expression, and find spatially variable genes" \
  --mode advanced \
  --outdir outputs/runs
scripts/run_app.sh
```

## In-App Flow

1. Open Workspace and choose the bundled demo dataset.
2. Enter the research task above.
3. Generate a research plan.
4. On Plan, inspect Agent-understood fields, parameter origins, dependencies, and expected evidence.
5. Approve the plan to resume the LangGraph thread.
6. On Run, show the execution stepper and any retry/skipped optional steps.
7. On Explore, compare spatial and embedding evidence and use the contextual Copilot.
8. On Report, download the complete reproducibility bundle.
9. On Provenance, show Dataset Card, trace, replay recipe, tool contracts, and telemetry.

## Repair Demonstration

Use a deliberately invalid observation key in an approved plan:

```text
plot_spatial(color="missing_column") on a dataset that already has obs["leiden"].
```

The expected v2 behavior is to patch the failed color parameter to `leiden`,
retry the same step, and record `failed -> retrying -> success_after_retry`.
