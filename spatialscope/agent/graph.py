from __future__ import annotations

import time
from inspect import Parameter, signature
from pathlib import Path
from typing import Any, Callable

from spatialscope.agent.llm import LLMClient, interpret_with_llm, parse_query_with_llm, plan_with_llm
from spatialscope.agent.planner import fallback_parse_query, make_analysis_plan, validate_plan_steps
from spatialscope.agent.state import RunMode, SpatialAgentState, initial_state
from spatialscope.tools.base import ToolResult, safe_tool_call
from spatialscope.tools.io_tools import load_h5ad
from spatialscope.tools.report_tools import generate_report
from spatialscope.tools.registry import get_tool, list_tool_contracts
from spatialscope.utils.paths import ensure_run_dirs, environment_summary, make_run_id, write_json


ToolFunc = Callable[..., ToolResult]


def _record_trace(
    state: SpatialAgentState,
    *,
    node: str,
    tool: str,
    params: dict[str, Any],
    result: ToolResult,
    duration: float,
) -> None:
    state.setdefault("execution_trace", []).append(
        {
            "run_id": state.get("run_id"),
            "node": node,
            "tool": tool,
            "params": params,
            "status": result.status,
            "summary": result.summary,
            "warnings": result.warnings,
            "errors": result.errors,
            "duration_sec": round(duration, 3),
        }
    )
    state.setdefault("warnings", []).extend(result.warnings)
    state.setdefault("errors", []).extend(result.errors)
    state.setdefault("generated_figures", []).extend(result.figures)
    state.setdefault("generated_tables", []).extend(result.tables)
    state.setdefault("observations", {}).update(result.observations)
    state["last_result"] = result.to_dict()
    state["needs_repair"] = result.status == "failed"


def parse_request_node(state: SpatialAgentState) -> SpatialAgentState:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass
    client = LLMClient.from_env()
    parsed: dict[str, Any]
    if client.enabled:
        try:
            parsed = parse_query_with_llm(client, state["user_query"])
            state["llm_enabled"] = True
        except Exception as exc:  # noqa: BLE001
            parsed = fallback_parse_query(state["user_query"], state["mode"])
            state.setdefault("warnings", []).append(f"LLM parsing failed; fallback parser used: {exc}")
            state["llm_enabled"] = False
    else:
        parsed = fallback_parse_query(state["user_query"], state["mode"])
        state["llm_enabled"] = False
    state["parsed_request"] = parsed
    return state


def inspect_dataset_node(state: SpatialAgentState) -> SpatialAgentState:
    start = time.time()
    adata, result = load_h5ad(str(state["data_path"]))
    if adata is not None:
        state["_adata"] = adata
        summary = result.observations.get("dataset_summary", {})
        state["dataset_summary"] = summary
        state["dataset_hash"] = summary.get("dataset_hash")
        state["adata_path"] = str(state["data_path"])
    _record_trace(state, node="inspect_dataset", tool="load_h5ad", params={"path": state.get("data_path")}, result=result, duration=time.time() - start)
    return state


def plan_analysis_node(state: SpatialAgentState) -> SpatialAgentState:
    tool_contracts = list_tool_contracts()
    state["tool_contracts"] = tool_contracts
    client = LLMClient.from_env()
    if client.enabled:
        try:
            plan = plan_with_llm(
                client,
                query=state.get("user_query", ""),
                parsed_request=state.get("parsed_request", {}),
                dataset_summary=state.get("dataset_summary", {}),
                mode=state["mode"],
                tool_contracts=tool_contracts,
            )
            state["task_plan"] = validate_plan_steps(plan.get("steps", []))
            state["plan_source"] = "llm"
            state["plan_rationale"] = str(plan.get("rationale", ""))
            state["llm_enabled"] = True
            return state
        except Exception as exc:  # noqa: BLE001
            state.setdefault("warnings", []).append(f"LLM planning failed; rule-based plan used: {exc}")

    plan_model = make_analysis_plan(state.get("parsed_request", {}), state["mode"])
    state["task_plan"] = [step.model_dump() for step in plan_model.steps]
    state["plan_source"] = plan_model.source
    state["plan_rationale"] = plan_model.rationale
    return state


def preview_plan_node(state: SpatialAgentState) -> SpatialAgentState:
    state["approved_plan"] = validate_plan_steps(list(state.get("task_plan", [])))
    state.setdefault("observations", {})["plan_preview"] = state["approved_plan"]
    state.setdefault("observations", {})["plan_source"] = state.get("plan_source")
    state.setdefault("observations", {})["plan_rationale"] = state.get("plan_rationale")
    return state


def _prepare_tool_params(func: ToolFunc, params: dict[str, Any], state: SpatialAgentState) -> dict[str, Any]:
    sig = signature(func)
    accepted = set(sig.parameters)
    accepts_kwargs = any(param.kind == Parameter.VAR_KEYWORD for param in sig.parameters.values())
    prepared = dict(params)
    if "figures_dir" in accepted:
        prepared.setdefault("figures_dir", state["figures_dir"])
    if "tables_dir" in accepted:
        prepared.setdefault("tables_dir", state["tables_dir"])
    if accepts_kwargs:
        return prepared
    return {key: value for key, value in prepared.items() if key in accepted}


def execute_tool_node(state: SpatialAgentState) -> SpatialAgentState:
    plan = state.get("approved_plan", [])
    index = int(state.get("current_step_index", 0))
    if index >= len(plan):
        state["current_step"] = "complete"
        state["needs_repair"] = False
        state["last_result"] = ToolResult(status="success", summary="No remaining workflow steps.").to_dict()
        return state

    step = plan[index]
    tool_name = str(step["tool"])
    state["current_step"] = tool_name
    try:
        func = get_tool(tool_name).function
    except KeyError as exc:
        result = ToolResult(status="failed", summary=f"Unknown tool `{tool_name}`.", errors=[str(exc)])
        _record_trace(state, node="execute_tool", tool=tool_name, params={}, result=result, duration=0)
        return state
    params = _prepare_tool_params(func, dict(step.get("params", {})), state)

    start = time.time()
    result = safe_tool_call(func, state.get("_adata"), **params)
    _record_trace(state, node="execute_tool", tool=tool_name, params=params, result=result, duration=time.time() - start)
    return state


def validate_result_node(state: SpatialAgentState) -> SpatialAgentState:
    result = state.get("last_result", {})
    status = result.get("status")
    if status == "failed":
        state["needs_repair"] = True
    else:
        state["needs_repair"] = False
        state["current_step_index"] = int(state.get("current_step_index", 0)) + 1
    return state


def repair_or_continue_node(state: SpatialAgentState) -> SpatialAgentState:
    state["repair_attempts"] = int(state.get("repair_attempts", 0)) + 1
    failed_step = state.get("current_step", "unknown")
    message = f"Step `{failed_step}` failed and was skipped after recording the error."
    state.setdefault("warnings", []).append(message)
    state.setdefault("execution_trace", []).append(
        {
            "run_id": state.get("run_id"),
            "node": "repair_or_continue",
            "tool": failed_step,
            "params": {},
            "status": "repaired",
            "summary": message,
            "warnings": [message],
            "errors": [],
            "duration_sec": 0,
        }
    )
    state["needs_repair"] = False
    state["current_step_index"] = int(state.get("current_step_index", 0)) + 1
    return state


def interpret_node(state: SpatialAgentState) -> SpatialAgentState:
    client = LLMClient.from_env()
    tool_summaries = state.get("execution_trace", [])
    if client.enabled:
        try:
            state["final_answer"] = interpret_with_llm(
                client,
                query=state["user_query"],
                dataset_summary=state.get("dataset_summary", {}),
                tool_summaries=tool_summaries,
            )
            state["llm_enabled"] = True
            return state
        except Exception as exc:  # noqa: BLE001
            state.setdefault("warnings", []).append(f"LLM interpretation failed; fallback summary used: {exc}")
    success_count = sum(1 for item in tool_summaries if item.get("status") == "success")
    state["final_answer"] = (
        f"SpatialScope completed {success_count} successful tool steps in {state.get('mode')} mode. "
        "The report summarizes generated figures, tables, parameters, warnings, and trace records. "
        "Interpretations are exploratory and should be validated with biological context."
    )
    return state


def report_node(state: SpatialAgentState) -> SpatialAgentState:
    start = time.time()
    result = generate_report(state)
    state["report_path"] = result.observations.get("report_path")
    _record_trace(state, node="generate_report", tool="generate_report", params={}, result=result, duration=time.time() - start)
    write_json(Path(state["run_dir"]) / "agent_trace.json", state.get("execution_trace", []))
    return state


def _route_after_validate(state: SpatialAgentState) -> str:
    if state.get("needs_repair"):
        return "repair"
    if int(state.get("current_step_index", 0)) < len(state.get("approved_plan", [])):
        return "execute"
    return "interpret"


def build_langgraph():
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(SpatialAgentState)
    graph.add_node("parse_request", parse_request_node)
    graph.add_node("inspect_dataset", inspect_dataset_node)
    graph.add_node("plan_analysis", plan_analysis_node)
    graph.add_node("preview_plan", preview_plan_node)
    graph.add_node("execute_tool", execute_tool_node)
    graph.add_node("validate_result", validate_result_node)
    graph.add_node("repair_or_continue", repair_or_continue_node)
    graph.add_node("interpret", interpret_node)
    graph.add_node("report", report_node)
    graph.add_edge(START, "parse_request")
    graph.add_edge("parse_request", "inspect_dataset")
    graph.add_edge("inspect_dataset", "plan_analysis")
    graph.add_edge("plan_analysis", "preview_plan")
    graph.add_edge("preview_plan", "execute_tool")
    graph.add_edge("execute_tool", "validate_result")
    graph.add_conditional_edges(
        "validate_result",
        _route_after_validate,
        {"repair": "repair_or_continue", "execute": "execute_tool", "interpret": "interpret"},
    )
    graph.add_edge("repair_or_continue", "execute_tool")
    graph.add_edge("interpret", "report")
    graph.add_edge("report", END)
    return graph.compile()


def run_fallback_graph(state: SpatialAgentState) -> SpatialAgentState:
    state = parse_request_node(state)
    state = inspect_dataset_node(state)
    state = plan_analysis_node(state)
    state = preview_plan_node(state)
    while int(state.get("current_step_index", 0)) < len(state.get("approved_plan", [])):
        state = execute_tool_node(state)
        state = validate_result_node(state)
        if state.get("needs_repair"):
            state = repair_or_continue_node(state)
    state = interpret_node(state)
    state = report_node(state)
    return state


def create_agent_state(
    *,
    data_path: str,
    query: str,
    mode: RunMode = "quick",
    outdir: str = "outputs/runs",
) -> SpatialAgentState:
    run_id = make_run_id()
    dirs = ensure_run_dirs(outdir, run_id)
    state = initial_state(
        run_id=run_id,
        data_path=data_path,
        query=query,
        mode=mode,
        outdir=outdir,
        run_dir=str(dirs["run_dir"]),
        figures_dir=str(dirs["figures_dir"]),
        tables_dir=str(dirs["tables_dir"]),
        intermediate_dir=str(dirs["intermediate_dir"]),
    )
    state["environment"] = environment_summary()
    return state


def preview_agent_plan(
    *,
    data_path: str,
    query: str,
    mode: RunMode = "quick",
    outdir: str = "outputs/runs",
) -> SpatialAgentState:
    state = create_agent_state(data_path=data_path, query=query, mode=mode, outdir=outdir)
    state = parse_request_node(state)
    state = inspect_dataset_node(state)
    state = plan_analysis_node(state)
    state = preview_plan_node(state)
    return state


def _reset_execution_state(state: SpatialAgentState) -> SpatialAgentState:
    kept_trace = [item for item in state.get("execution_trace", []) if item.get("node") == "inspect_dataset"]
    state["execution_trace"] = kept_trace
    state["generated_figures"] = []
    state["generated_tables"] = []
    state["repair_attempts"] = 0
    state["current_step_index"] = 0
    state["current_step"] = ""
    state["last_result"] = {}
    state["needs_repair"] = False
    state["warnings"] = [warning for item in kept_trace for warning in item.get("warnings", [])]
    state["errors"] = [error for item in kept_trace for error in item.get("errors", [])]
    return state


def execute_agent_state(
    state: SpatialAgentState,
    *,
    approved_plan: list[dict[str, Any]] | None = None,
    plan_source: str | None = None,
) -> SpatialAgentState:
    if approved_plan is not None:
        state["approved_plan"] = validate_plan_steps(approved_plan)
        state["task_plan"] = state["approved_plan"]
        state["plan_source"] = plan_source or "user_edited"
    state = _reset_execution_state(state)
    while int(state.get("current_step_index", 0)) < len(state.get("approved_plan", [])):
        state = execute_tool_node(state)
        state = validate_result_node(state)
        if state.get("needs_repair"):
            state = repair_or_continue_node(state)
    state = interpret_node(state)
    state = report_node(state)
    return state


def run_agent(
    *,
    data_path: str,
    query: str,
    mode: RunMode = "quick",
    outdir: str = "outputs/runs",
) -> SpatialAgentState:
    state = create_agent_state(data_path=data_path, query=query, mode=mode, outdir=outdir)

    try:
        graph = build_langgraph()
        result = graph.invoke(state)
        return result  # type: ignore[return-value]
    except ImportError:
        return run_fallback_graph(state)
