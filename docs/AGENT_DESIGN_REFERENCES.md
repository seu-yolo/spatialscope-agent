# Agent Design References

SpatialScope Agent follows a conservative, inspectable agent design rather than a black-box autonomous loop.

## References Studied

- LangGraph documentation emphasizes long-running, stateful orchestration, durable execution, human-in-the-loop oversight, persistence, memory, and trace visibility.
  - https://docs.langchain.com/oss/python/langgraph/overview
  - https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph
- OpenAI Agents SDK documentation frames production agents around a small set of primitives: agents with instructions/tools, guardrails, sessions, human-in-the-loop, and tracing.
  - https://openai.github.io/openai-agents-python/
- Anthropic's engineering guidance recommends simple, composable patterns, clear tool interfaces, and complexity only when task performance justifies it.
  - https://www.anthropic.com/engineering/building-effective-agents
- Streamlit documentation and patterns encourage clear app structure, visible navigation, and compact interactive workspaces.
  - https://docs.streamlit.io/

## How This Project Applies Them

1. **State first.** The LangGraph state stores dataset metadata, plan, parameters, trace, generated artifacts, warnings, and errors. LLM prompts are formatted from state rather than stored as opaque text.
2. **Tool contracts.** Every analysis tool exposes preconditions, postconditions, common failures, and repair strategies through the registry.
3. **Human-in-the-loop.** The Streamlit `Analyze` page lets users review and edit the generated plan before execution.
4. **Guarded autonomy.** LLM planning is allowed, but mode-specific baseline steps are enforced so required spatial transcriptomics analyses are not accidentally omitted.
5. **Traceability.** Every tool call writes an execution trace and the final report links results to figures, tables, parameters, and warnings.
6. **Evidence-first visualization.** Figures use consistent typography, color, SVG export, and captions. Plotting choices prioritize readable scientific evidence over decoration.

## Current Design Bias

SpatialScope is intentionally a workflow-agent hybrid:

- The workflow gives reproducibility and grading reliability.
- The LLM gives flexible natural-language parsing, planning rationale, repair suggestions, and cautious interpretation.
- Advanced tools are optional and gracefully skipped when dependencies are absent.
