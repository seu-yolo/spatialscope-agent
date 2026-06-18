# SpatialScope v2 Migration Notes

SpatialScope v2 keeps the CLI, demo data path, report bundle, run metadata, trace,
Dataset Card, Storyboard, Replay Recipe, and audit artifacts compatible where
practical. The main change is the runtime boundary: Streamlit and CLI now execute
through the compiled LangGraph runtime instead of duplicate hand-written loops.

## UI Changes

- The Streamlit app is split into six pages: Workspace, Plan, Run, Explore, Report, Provenance.
- Audits, run history, individual JSON/YAML downloads, LLM settings, and tool registry move to Provenance.
- Workspace focuses on dataset selection and the research question.
- Report focuses on findings, caveats, methods, and one primary bundle download.

## State Changes

- Checkpointed graph state stores dataset references and public summaries, not AnnData objects.
- Existing run bundles can still be loaded through the run library where their public metadata is available.
- Legacy runs that lack v2 profile fields fall back to the persisted `dataset_summary` and Dataset Card.

## Scientific Changes

- Unknown `adata.X` is no longer renamed as raw counts.
- Preprocessing records expression lineage and creates an explicit interpretation layer.
- Marker ranking and gene plots use the selected interpretation layer by default.
- Candidate cluster annotation no longer runs automatically in standard mode.

## Compatibility

Existing commands remain valid:

```bash
python cli.py run --data data/demo_tiny.h5ad --query "Run quick spatial analysis" --mode quick
scripts/run_app.sh
```
