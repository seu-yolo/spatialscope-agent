# SpatialScope Agent v2 Gap Audit

This document tracks the remaining distance between the v2 reset prompt and the current implementation. It is intentionally explicit so future commits can continue from a known, reviewable state.

## Implemented

- `app.py` is now a thin Streamlit bootstrap.
- Streamlit and CLI execute through `AgentRuntime`, which uses the compiled LangGraph with a SQLite checkpointer and stable `thread_id`.
- Plan review uses a real LangGraph `interrupt()` and resumes through `Command(resume=...)`.
- Graph state no longer stores AnnData objects; datasets are referenced through persisted working `.h5ad` paths.
- Run state records research brief, approved plan, generated artifacts, warnings/errors, repair log, execution trace, and safe LLM telemetry.
- Candidate annotation is opt-in and remains caveated.
- Gene plots and marker ranking use an explicit interpretation layer.
- The UI exposes the scientific journey: Workspace, Plan, Run, Explore, Report, Provenance.
- Research Brief, parameter origins, dependencies, preconditions, and expected evidence are visible during plan review.
- Main pages no longer show self-congratulatory Quality/Agent scores; audit details are in Provenance or collapsed advanced sections.
- No-key fallback remains functional.
- Tests cover runtime interrupt/resume, bounded repair retry, no-key fallback, UI router separation, planner differentiation, and a deterministic structured mock LLM path.

## Partially Implemented

- The UI uses six Streamlit tabs rather than `st.Page`/`st.navigation` files. The app is functionally multipage, but the physical layout is not yet the target `ui/pages/*.py` structure.
- `AgentRuntime.stream_resume()` exists, but the Run page still executes as a blocking operation and then renders the final trace. Live graph event streaming is a v2.1 priority.
- Repair supports bounded retries and only marks repaired after a successful retry, but ambiguous failures do not yet ask the user through a secondary interrupt.
- LLM calls are centralized in `spatialscope.llm.gateway`, but graph nodes still instantiate the gateway from environment rather than receiving one injected runtime-wide instance.
- Evidence claim validation exists, but report generation does not yet reject all definitive-language interpretations automatically.
- Report rendering still lives in `spatialscope/tools/report_tools.py`; a future commit should move the HTML template to `spatialscope/reporting/templates/report.html.j2`.
- Explore has contextual figure/table review, but not a fully interactive side-by-side spatial/embedding workspace yet.

## Remaining v2.1 Backlog

1. Convert tab rendering to true Streamlit navigation with per-page modules.
2. Wire `stream_resume()` into the Run page so node events appear live while tools execute.
3. Add secondary interrupts for user clarification and ambiguous repairs.
4. Inject one `LLMGateway` into the runtime instead of constructing it in graph nodes.
5. Preserve the original input matrix under an explicit neutral source reference when possible, then keep modeling transforms off the interpretation layer.
6. Move reporting to a template-backed `spatialscope/reporting` package.
7. Add interactive Explore controls for gene selection, coordinate layer selection, linked table excerpts, and figure-to-claim evidence cards.
8. Add a browser-based Streamlit smoke test to CI when the environment is stable enough.
