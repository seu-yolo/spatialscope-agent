# Changelog

All notable changes for the course submission are summarized here.

## 0.1.0 - 2026-06-24

- Built a public Streamlit spatial transcriptomics agent workspace.
- Added LangGraph workflow with dataset inspection, plan review, execution,
  validation, repair, interpretation, and report generation.
- Added OpenAI-compatible LLM configuration for GLM 5.1 and safe deterministic
  fallback for tests.
- Added evidence-linked Spatial + UMAP exploration, contextual Copilot, and
  report findings with caveats.
- Added synthetic early embryo demo and real GEO data download workflow.
- Added GitHub Pages project site and Streamlit Community Cloud deployment.
- Added reproducibility artifacts: `agent_trace.json`, `run_metadata.json`,
  `parameters.yaml`, `report.html`, figures, tables, run bundle, dataset card,
  storyboard, and rerun recipe.
- Hardened hosted demo `.h5ad` generation and AnnData saving against pandas
  nullable string defaults.
- Refined report visual hierarchy so spatial/UMAP/gene evidence appears before
  QC/HVG supporting evidence.
