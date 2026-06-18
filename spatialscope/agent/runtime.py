from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from langgraph.types import Command

from spatialscope.agent.graph import build_langgraph, create_agent_state
from spatialscope.agent.state import RunMode, SpatialAgentState


def _checkpoint_path(path: str | Path | None = None) -> Path:
    checkpoint_path = Path(path or "outputs/checkpoints/spatialscope.sqlite")
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    return checkpoint_path


class AgentRuntime:
    """Owns the compiled LangGraph and persistent checkpoint state.

    Streamlit, CLI, and tests should go through this runtime instead of
    reimplementing graph node loops. That keeps plan review, resume, repair,
    tracing, and output generation on one code path.
    """

    def __init__(self, *, checkpoint_path: str | Path | None = None) -> None:
        from langgraph.checkpoint.sqlite import SqliteSaver

        self.checkpoint_path = _checkpoint_path(checkpoint_path)
        self._conn = sqlite3.connect(str(self.checkpoint_path), check_same_thread=False)
        self.checkpointer = SqliteSaver(self._conn)
        self.graph = build_langgraph(checkpointer=self.checkpointer)

    def config(self, thread_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": thread_id}}

    def state_snapshot(self, thread_id: str) -> Any:
        return self.graph.get_state(self.config(thread_id))

    def _values_with_interrupt(self, thread_id: str, result: dict[str, Any]) -> SpatialAgentState:
        snapshot = self.state_snapshot(thread_id)
        values = dict(getattr(snapshot, "values", {}) or {})
        if "__interrupt__" in result:
            values["__interrupt__"] = result["__interrupt__"]
            values["awaiting_plan_review"] = True
        values.setdefault("thread_id", thread_id)
        return values  # type: ignore[return-value]

    def start_run(
        self,
        *,
        data_path: str,
        query: str,
        mode: RunMode = "quick",
        outdir: str = "outputs/runs",
        auto_approve: bool = False,
    ) -> SpatialAgentState:
        state = create_agent_state(data_path=data_path, query=query, mode=mode, outdir=outdir)
        thread_id = str(state["thread_id"])
        result = self.graph.invoke(state, config=self.config(thread_id))
        if "__interrupt__" not in result:
            return result  # type: ignore[return-value]
        paused = self._values_with_interrupt(thread_id, result)
        if not auto_approve:
            return paused
        return self.resume_run(
            thread_id,
            approved_plan=list(paused.get("task_plan", [])),
            plan_source="auto_approved",
        )

    def resume_run(
        self,
        thread_id: str,
        *,
        approved_plan: list[dict[str, Any]] | None = None,
        plan_source: str = "user_edited",
        extra_payload: dict[str, Any] | None = None,
    ) -> SpatialAgentState:
        payload: dict[str, Any] = {
            "approved_plan": approved_plan,
            "plan_source": plan_source,
            "edited": plan_source == "user_edited",
        }
        if extra_payload:
            payload.update(extra_payload)
        result = self.graph.invoke(Command(resume=payload), config=self.config(thread_id))
        return result  # type: ignore[return-value]

    def stream_resume(
        self,
        thread_id: str,
        *,
        approved_plan: list[dict[str, Any]] | None = None,
        plan_source: str = "user_edited",
    ) -> Any:
        payload = {"approved_plan": approved_plan, "plan_source": plan_source, "edited": plan_source == "user_edited"}
        return self.graph.stream(Command(resume=payload), config=self.config(thread_id), stream_mode="updates")

    def close(self) -> None:
        self._conn.close()


_DEFAULT_RUNTIME: AgentRuntime | None = None


def get_default_runtime() -> AgentRuntime:
    global _DEFAULT_RUNTIME
    if _DEFAULT_RUNTIME is None:
        _DEFAULT_RUNTIME = AgentRuntime()
    return _DEFAULT_RUNTIME
