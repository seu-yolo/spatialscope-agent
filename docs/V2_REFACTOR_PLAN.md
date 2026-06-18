# SpatialScope Agent v2 Refactor Plan

## Verified Baseline

- Repository branch: `main`
- Initial working tree before refactor: clean
- Conda Python: 3.11.15
- Base Python: 3.13.9
- Key dependency versions: Streamlit 1.58.0, LangGraph 1.2.5, Scanpy 1.11.5, AnnData 0.12.16, Pydantic 2.13.4, Plotly 6.8.0
- Baseline tests: `pytest -q` passed with 57 tests
- Baseline health script: `scripts/check_project.sh` passed and produced a no-key quick demo with warnings 0 and errors 0
- Synthetic demo generation: `python scripts/create_demo_data.py --output data/demo_tiny.h5ad` passed
- Baseline no-key CLI quick run passed with warnings 0 and errors 0

## Confirmed Problems

- `app.py` was a monolithic Streamlit dashboard containing UI, execution controls, audits, downloads, CSS, and product copy.
- Graph state included `_adata`, which is not checkpoint-serializable.
- Streamlit plan/run flows used hand-written execution loops rather than the compiled LangGraph runtime.
- Preprocessing named unknown `adata.X` as `counts` and then scaled `X`, which made expression lineage ambiguous.
- Candidate annotation was part of standard mode even when not explicitly requested.
- Advanced audits and downloads dominated the primary scientific journey.

## Refactor Decisions

- Add a serializable `DatasetProfile` and `ExpressionLineage` domain layer.
- Introduce `DatasetStore` so graph state stores dataset references, not AnnData objects.
- Use a single `AgentRuntime` backed by compiled LangGraph, SQLite checkpoints when available, and stable thread IDs.
- Use real LangGraph interrupt/resume for plan approval.
- Use bounded repair retry semantics: `failed -> retrying -> success_after_retry`; never mark a failed step repaired without re-execution.
- Treat `quick`, `standard`, and `advanced` as budget presets. Insert scientific dependencies only when needed.
- Keep deterministic fallback and CLI compatibility.
- Split Streamlit into six product pages: Workspace, Plan, Run, Explore, Report, Provenance.

## Migration Map

- `app.py` -> thin router using `spatialscope.ui.pages`.
- `spatialscope.agent.graph` -> authoritative compiled graph nodes and compatibility wrappers.
- `spatialscope.agent.runtime` -> start/resume/stream/get-state runtime adapter.
- `spatialscope.domain.*` -> dataset profile, store, expression lineage, evidence models.
- `spatialscope.llm.*` -> typed gateway, telemetry, schemas, guardrails.
- Existing audit/bundle/replay/report utilities remain compatible and move visually to Provenance.

## Acceptance Checklist

- [x] Baseline recorded.
- [x] Repository conventions documented in `AGENTS.md`.
- [x] `app.py` thin router.
- [x] UI split into six pages.
- [x] Streamlit and CLI use compiled graph runtime.
- [x] Graph state contains no AnnData object.
- [x] Stable thread ID and checkpointer used.
- [x] Plan approval uses real interrupt/resume.
- [x] Real retry repair path tested.
- [x] Expression lineage explicit.
- [x] Annotation disabled by default.
- [x] README/migration/demo docs updated.
