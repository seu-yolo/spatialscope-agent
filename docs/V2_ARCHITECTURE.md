# SpatialScope v2 Architecture

## Product Thesis

SpatialScope is a research-question-first spatial transcriptomics workspace. The
LLM helps interpret intent, propose plans, repair failures, and explain evidence;
deterministic Scanpy/Squidpy tools perform computation; LangGraph records and
checkpoints the workflow.

## Runtime

- `AgentRuntime` compiles one LangGraph and owns checkpointer configuration.
- Each run has a stable `thread_id`, normally equal to the `run_id`.
- `review_plan` uses LangGraph `interrupt()` and resumes with `Command(resume=...)`.
- CLI uses auto-approval on the same runtime path; Streamlit exposes the interrupt.
- The graph state is serializable and stores `dataset_ref` / `working_dataset_ref`, not AnnData.

## Domain Layer

- `DatasetProfile` summarizes dimensions, spatial coordinates, layers, embeddings,
  gene IDs, matrix-state heuristics, safe expression source, warnings, and run depth.
- `DatasetStore` loads/saves working `.h5ad` files across runtime/tool boundaries.
- `ExpressionLineage` records whether the input looked count-like, log-normalized,
  scaled, or unknown and chooses an interpretation layer.
- `EvidenceArtifact` and `EvidenceClaim` provide typed evidence and cautious claims.

## UI

The Streamlit UI is organized into:

1. Workspace
2. Plan
3. Run
4. Explore
5. Report
6. Provenance

Provenance contains audits, trace, replay, telemetry, environment, and advanced downloads.
