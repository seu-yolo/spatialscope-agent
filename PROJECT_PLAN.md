# SpatialScope Agent v1 Plan

SpatialScope Agent is a research-grade spatial transcriptomics exploration workspace. It uses DeepSeek `deepseek-v4-flash` for natural-language planning and interpretation, LangGraph for inspectable workflow orchestration, and Scanpy/Squidpy for deterministic scientific analysis.

Core product:

- Upload or pass an `.h5ad` file.
- Inspect AnnData structure and spatial coordinates.
- Generate an editable analysis plan from a natural-language query.
- Run Quick, Standard, or Advanced workflows.
- Produce publication-style figures, tables, Agent Trace, metadata, and an HTML report.

Showcase features:

- Gene fuzzy matching repair.
- Gene Panel Spatial View.
- Spatially variable gene analysis.
- Neighborhood enrichment.
- Reproducibility Bundle.

Scientific guardrails:

- LLM receives only summaries, captions, and table excerpts.
- Full expression matrices are never sent to the LLM.
- Every interpretation is grounded in generated figures/tables.
- Cluster interpretation is marker-based candidate interpretation, not confirmed annotation.

