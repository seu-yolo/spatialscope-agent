# SpatialScope Agent v1 Plan

SpatialScope Agent is a research-grade spatial transcriptomics exploration workspace. It uses an OpenAI-compatible LLM such as GLM 5.1 for natural-language planning and interpretation, LangGraph for inspectable workflow orchestration, and Scanpy/Squidpy for deterministic scientific analysis.

Core product:

- Upload or pass an `.h5ad` file.
- Inspect AnnData structure and spatial coordinates.
- Generate an editable analysis plan from a natural-language query.
- Run Quick, Standard, or Advanced workflows.
- Produce publication-style figures, tables, Dataset Card, Agent Trace, metadata, and an HTML report.

Showcase features:

- Gene fuzzy matching repair.
- Gene Panel Spatial View.
- Spatially variable gene analysis.
- Neighborhood enrichment.
- Dataset Card for data suitability, schema preview, spatial-coordinate status, recommended run depth, and privacy boundary.
- Reproducibility Bundle.
- Spatial Storyboard and Run Replay Recipe.
- Quality Gates, Agent Audit, Artifact Audit, Human Review, Run Library, and Run Compare.
- Open tool registry with inspectable tool contracts.
- Editable plan approval before execution in the Streamlit workspace.

Scientific guardrails:

- LLM receives only summaries, captions, and table excerpts.
- Full expression matrices are never sent to the LLM.
- Every interpretation is grounded in generated figures/tables.
- Dataset suitability is reported before interpretation.
- Cluster interpretation is marker-based candidate interpretation, not confirmed annotation.

Current v1 implementation status:

- Core conda environment is installable with Python 3.11.
- Quick and Standard modes run with zero warnings/errors on the tiny demo data.
- Advanced mode runs without hard errors; Squidpy-only steps are optional when Squidpy is absent.
- LangGraph orchestration, structured plan validation, HTML report generation, Dataset Card generation, and Streamlit plan approval are implemented.
- Each run writes a README, report, dataset card, storyboard, rerun recipe, metadata, parameters, trace, manifest, audits, and ZIP bundle.
