# SpatialScope Agent Product Brief

SpatialScope Agent is a research-grade spatial transcriptomics analysis workspace
that combines LLM planning, deterministic scientific tools, transparent execution
trace, and presentation-ready outputs.

## Product Positioning

SpatialScope is not a chatbot that guesses biological conclusions. It is an
agentic analysis system:

- The LLM plans, explains, and repairs.
- The tool layer performs deterministic computation.
- The state graph records each step.
- The report shows evidence, warnings, parameters, and limitations.

The intended user is a student or researcher who wants to move from a spatial
transcriptomics `.h5ad` file to a reproducible first-pass analysis without losing
control over parameters or biological interpretation.

## Core Experience

1. Upload or select an AnnData file.
2. Describe the intended analysis in natural language.
3. Review an editable analysis plan.
4. Run Quick, Standard, or Advanced mode.
5. Inspect figures, tables, trace, warnings, and candidate annotations.
6. Export a reproducibility bundle and HTML report.
7. Revisit recent runs through Run Library, artifact manifests, and side-by-side Run Compare.

## Quality Bar

A good run should satisfy:

- No raw expression matrix is sent to the LLM.
- Every figure/table has a traceable generating tool.
- Warnings are visible instead of hidden.
- Failed steps produce structured repair diagnostics instead of silent skipping.
- Each run has Quality Gates for dataset readiness, plan provenance, trace
  integrity, evidence outputs, error review, interpretation, and reproducibility.
- Cluster annotation is framed as candidate evidence, not final truth.
- Missing genes trigger fuzzy matching rather than silent failure.
- Missing optional dependencies degrade gracefully.
- Output paths, parameters, software versions, and trace are preserved.
- Every run writes an artifact manifest that indexes reports, figures, tables,
  metadata, parameters, trace, repair diagnostics, Quality Gates, and public state.
- Recent runs can be compared by mode, plan source, trace steps, figures,
  warnings, errors, repairs, and dataset hash.

## Current Capabilities

- OpenAI-compatible LLM client, currently configured for GLM-style providers.
- LangGraph orchestration with deterministic fallback.
- Tool registry with contracts, preconditions, failures, and repair strategies.
- Structured repair diagnostics with likely cause, action taken, and recommended
  next actions.
- Quality Gates score and status for lightweight review before trusting or
  presenting a run.
- AnnData inspection, QC, preprocessing, PCA, UMAP, Leiden clustering.
- Spatial cluster and gene expression visualization.
- Marker gene ranking and candidate cluster annotation suggestions.
- Optional spatially variable gene and neighborhood enrichment analysis.
- CLI, Streamlit workspace, HTML report, GitHub Pages project site, CI smoke test.
- Run Library and Run Compare for recent reports, reproducibility assets, and
  lightweight audit across multiple runs.

## Product Roadmap

### Near Term

- Add a real public spatial transcriptomics demo dataset workflow.
- Add screenshots or recorded demo clips to the GitHub Pages site.
- Add a stronger marker evidence panel with heatmap/dotplot summaries.
- Run and document GLM-enabled planning/interpretation smoke tests.
- Add filtering and saved review notes for repair categories.
- Add saved reviewer notes and override decisions for Quality Gates.

### Medium Term

- Add richer biological annotation libraries with domain-specific marker sets.
- Add optional ligand-receptor and neighborhood communication modules.
- Add exportable analysis notebooks for reproducibility audits.
- Add pluggable LLM providers and model-level evaluation fixtures.
- Add integration tests for Streamlit user flows.

### Long Term

- Support multi-dataset comparison.
- Add human-in-the-loop biological review states.
- Add deployable hosted demo with sanitized example data.
- Evaluate graph neural spatial methods as optional research extensions.

## Non-Goals for v1

- No automated clinical interpretation.
- No claim of definitive cell-type annotation.
- No upload of large matrices to remote LLMs.
- No hard dependency on fragile advanced spatial packages for the core demo.
