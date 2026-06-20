from __future__ import annotations

import time
from dataclasses import asdict
from inspect import Parameter, signature
from pathlib import Path
from typing import Any, Callable

import pandas as pd
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt

from spatialscope.agent.planner import fallback_parse_query, validate_plan_steps
from spatialscope.agent.repair import diagnose_tool_failure
from spatialscope.agent.state import RunMode, SpatialAgentState, initial_state
from spatialscope.domain.dataset_store import DEFAULT_DATASET_STORE
from spatialscope.domain.evidence import EvidenceArtifact, EvidencePack
from spatialscope.llm.gateway import LLMGateway
from spatialscope.tools.base import ToolResult, safe_tool_call
from spatialscope.tools.io_tools import load_h5ad
from spatialscope.tools.report_tools import generate_report
from spatialscope.tools.registry import get_tool, list_tool_contracts
from spatialscope.utils.paths import ensure_run_dirs, environment_summary, make_run_id, write_json


ToolFunc = Callable[..., ToolResult]


def _extend_llm_telemetry(state: SpatialAgentState, gateway: LLMGateway) -> None:
    records = [record.model_dump() if hasattr(record, "model_dump") else dict(record) for record in gateway.telemetry]
    if records:
        state.setdefault("llm_calls", []).extend(records)
        gateway.telemetry.clear()


def _record_trace(
    state: SpatialAgentState,
    *,
    node: str,
    tool: str,
    params: dict[str, Any],
    result: ToolResult,
    duration: float,
    status_override: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    evidence_artifacts = _evidence_from_result(result, tool=tool, node=node)
    evidence_packs = _evidence_packs_from_result(result, tool=tool, node=node, params=params, artifacts=evidence_artifacts)
    figures = [dict(item) for item in result.figures]
    tables = [dict(item) for item in result.tables]
    figure_ids = [item["evidence_id"] for item in evidence_artifacts if item.get("kind") == "figure"]
    table_ids = [item["evidence_id"] for item in evidence_artifacts if item.get("kind") == "table"]
    for fig, evidence_id in zip(figures, figure_ids):
        fig.setdefault("evidence_id", evidence_id)
    for table, evidence_id in zip(tables, table_ids):
        table.setdefault("evidence_id", evidence_id)
    trace_record: dict[str, Any] = {
        "run_id": state.get("run_id"),
        "node": node,
        "tool": tool,
        "params": params,
        "status": status_override or result.status,
        "summary": result.summary,
        "warnings": result.warnings,
        "errors": result.errors,
        "duration_sec": round(duration, 3),
    }
    if extra:
        trace_record.update(extra)
    state.setdefault("execution_trace", []).append(trace_record)
    state.setdefault("warnings", []).extend(result.warnings)
    state.setdefault("errors", []).extend(result.errors)
    state.setdefault("generated_figures", []).extend(figures)
    state.setdefault("generated_tables", []).extend(tables)
    state.setdefault("observations", {}).update(result.observations)
    state.setdefault("evidence_artifacts", []).extend(evidence_artifacts)
    state.setdefault("evidence_packs", []).extend(evidence_packs)
    _record_clarifications(state, result=result, tool=tool, params=params)
    state["last_result"] = result.to_dict()
    state["needs_repair"] = result.status == "failed"


def _evidence_from_result(result: ToolResult, *, tool: str, node: str) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for index, fig in enumerate(result.figures):
        artifacts.append(
            EvidenceArtifact(
                evidence_id=f"{node}:{tool}:figure:{index}",
                kind="figure",
                path=str(fig.get("path") or ""),
                title=str(fig.get("title") or tool),
                caption=str(fig.get("caption") or result.summary),
                tool=tool,
                data_layer=str(fig.get("data_layer") or ""),
            ).model_dump()
        )
    for index, table in enumerate(result.tables):
        artifacts.append(
            EvidenceArtifact(
                evidence_id=f"{node}:{tool}:table:{index}",
                kind="table",
                path=str(table.get("path") or ""),
                title=str(table.get("title") or tool),
                caption=result.summary,
                tool=tool,
            ).model_dump()
        )
    return artifacts


def _compact_value(value: Any, *, depth: int = 0) -> Any:
    if depth > 2:
        return str(value)[:140]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in list(value.items())[:16]:
            normalized = str(key).lower()
            if normalized in {"x", "raw_x", "matrix", "coordinates", "spatial_coordinates"} or normalized.endswith("_matrix"):
                out[str(key)] = "[redacted matrix-like payload]"
            else:
                out[str(key)] = _compact_value(item, depth=depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        values = list(value)
        if len(values) > 20 and any(isinstance(item, (list, tuple, dict)) for item in values):
            return f"[{len(values)} structured records redacted]"
        return [_compact_value(item, depth=depth + 1) for item in values[:20]]
    try:
        return value.item()
    except Exception:
        return str(value)[:140]


def _summary_metrics_from_result(result: ToolResult) -> dict[str, Any]:
    keys = [
        "dataset_summary",
        "qc_before",
        "qc_after",
        "qc_quantiles",
        "qc_thresholds",
        "retention_fraction",
        "n_clusters",
        "cluster_sizes",
        "cluster_fractions",
        "cluster_palette",
        "resolution",
        "requested_genes",
        "resolved_genes",
        "gene_expression_summary",
        "expression_layer",
        "clip_percentiles",
        "marker_rows",
        "top_marker_summary",
        "groupby",
        "expression_lineage",
    ]
    metrics: dict[str, Any] = {}
    observations = result.observations or {}
    for key in keys:
        if key in observations:
            metrics[key] = _compact_value(observations[key])
    if "dataset_summary" in metrics and isinstance(metrics["dataset_summary"], dict):
        summary = metrics.pop("dataset_summary")
        for key in ["n_obs", "n_vars", "has_spatial", "matrix_state", "recommended_run_depth"]:
            if key in summary:
                metrics[key] = summary[key]
    return metrics


def _table_excerpt(path: str, *, rows: int = 6, columns: int = 8) -> list[dict[str, Any]]:
    table_path = Path(path)
    if not table_path.exists():
        return []
    try:
        if table_path.suffix.lower() == ".csv":
            frame = pd.read_csv(table_path, nrows=rows)
        else:
            frame = pd.read_table(table_path, nrows=rows)
    except Exception:
        return []
    if frame.empty:
        return []
    frame = frame.iloc[:, :columns].copy()
    return [
        {str(key): _compact_value(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _evidence_packs_from_result(
    result: ToolResult,
    *,
    tool: str,
    node: str,
    params: dict[str, Any],
    artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    metrics = _summary_metrics_from_result(result)
    caveats = list(dict.fromkeys([*map(str, result.warnings), *map(str, result.errors)]))
    packs: list[dict[str, Any]] = []
    if not artifacts and metrics:
        packs.append(
            EvidencePack(
                evidence_id=f"{node}:{tool}:metric:0",
                kind="metric",
                title=f"{tool} metrics",
                tool=tool,
                caption=result.summary,
                summary_metrics=metrics,
                parameters=_compact_value(params),
                caveats=caveats,
            ).model_dump()
        )
        return packs
    for artifact in artifacts:
        path = str(artifact.get("path") or "")
        kind = str(artifact.get("kind") or "text")
        packs.append(
            EvidencePack(
                evidence_id=str(artifact.get("evidence_id")),
                kind=kind,  # type: ignore[arg-type]
                title=str(artifact.get("title") or tool),
                tool=tool,
                path=path,
                data_layer=str(artifact.get("data_layer") or ""),
                caption=str(artifact.get("caption") or result.summary),
                summary_metrics=metrics,
                table_excerpt=_table_excerpt(path) if kind == "table" else [],
                parameters=_compact_value(params),
                caveats=caveats,
            ).model_dump()
        )
    return packs


def _record_clarifications(state: SpatialAgentState, *, result: ToolResult, tool: str, params: dict[str, Any]) -> None:
    if result.status != "failed":
        return
    observations = result.observations or {}
    if "gene_suggestions" in observations:
        state.setdefault("clarification_items", []).append(
            {
                "kind": "gene_resolution",
                "tool": tool,
                "params": params,
                "message": "One or more genes need confirmation before expression plotting.",
                "suggestions": observations.get("gene_suggestions", {}),
                "status": "repaired_or_waiting",
            }
        )
    if "unsafe_expression_source" in set(map(str, result.errors)):
        state.setdefault("clarification_items", []).append(
            {
                "kind": "unsafe_expression_layer",
                "tool": tool,
                "params": params,
                "message": result.summary,
                "status": "blocked",
            }
        )


def parse_request_node(state: SpatialAgentState, *, llm_gateway: LLMGateway | None = None) -> SpatialAgentState:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass

    gateway = llm_gateway or LLMGateway.from_env()
    brief = gateway.parse_research_brief(
        state.get("user_query", ""),
        mode=state.get("mode", "quick"),
        dataset_profile=state.get("dataset_profile", {}),
    )
    state["research_brief"] = brief.model_dump()
    state["parsed_request"] = {
        "intent": brief.normalized_question,
        "requested_steps": brief.requested_analyses,
        "genes": brief.requested_genes,
        "preferred_mode": state.get("mode", "quick"),
        "constraints": brief.user_constraints,
        "notes": "; ".join(brief.unsupported_requests),
        "confidence": brief.confidence,
    }
    state["llm_enabled"] = gateway.enabled
    state["llm_mode"] = gateway.active_mode
    state["llm_status"] = gateway.safe_status()
    _extend_llm_telemetry(state, gateway)
    return state


def inspect_dataset_node(state: SpatialAgentState) -> SpatialAgentState:
    start = time.time()
    data_path = str(state.get("data_path") or "")
    adata, result = load_h5ad(data_path)
    if adata is not None:
        working_ref = DEFAULT_DATASET_STORE.prepare_working_copy(
            data_path,
            intermediate_dir=str(state["intermediate_dir"]),
            run_id=str(state["run_id"]),
        )
        DEFAULT_DATASET_STORE.save(adata, working_ref)
        summary = result.observations.get("dataset_summary", {})
        state["dataset_ref"] = data_path
        state["working_dataset_ref"] = working_ref
        state["dataset_summary"] = summary
        state["dataset_profile"] = summary.get("dataset_profile", {})
        state["dataset_hash"] = summary.get("dataset_hash")
        state["adata_path"] = working_ref
        state.setdefault("parameters", {})["working_dataset_ref"] = working_ref
    _record_trace(
        state,
        node="inspect_dataset",
        tool="load_h5ad",
        params={"path": data_path},
        result=result,
        duration=time.time() - start,
    )
    return state


def plan_analysis_node(state: SpatialAgentState, *, llm_gateway: LLMGateway | None = None) -> SpatialAgentState:
    tool_contracts = list_tool_contracts()
    state["tool_contracts"] = tool_contracts
    gateway = llm_gateway or LLMGateway.from_env()
    plan = gateway.propose_plan(
        state.get("research_brief", {}) or fallback_parse_query(state.get("user_query", ""), state.get("mode", "quick")),
        mode=state.get("mode", "quick"),
        dataset_profile=state.get("dataset_profile") or state.get("dataset_summary", {}),
        tool_contracts=tool_contracts,
    )
    state["task_plan"] = validate_plan_steps([step.model_dump() for step in plan.steps])
    state["plan_source"] = plan.source
    state["plan_rationale"] = plan.rationale
    state["llm_enabled"] = state.get("llm_enabled", False) or gateway.enabled
    state["llm_mode"] = gateway.active_mode
    state["llm_status"] = gateway.safe_status()
    state["current_step_index"] = 0
    state["needs_repair"] = False
    _extend_llm_telemetry(state, gateway)
    return state


def review_plan_node(state: SpatialAgentState) -> SpatialAgentState:
    """Pause for human plan review, then resume with an approved plan."""

    payload = {
        "kind": "plan_review",
        "run_id": state.get("run_id"),
        "thread_id": state.get("thread_id") or state.get("run_id"),
        "mode": state.get("mode"),
        "query": state.get("user_query"),
        "dataset_summary": state.get("dataset_summary", {}),
        "research_brief": state.get("research_brief", {}),
        "plan_source": state.get("plan_source"),
        "plan_rationale": state.get("plan_rationale"),
        "task_plan": state.get("task_plan", []),
        "tool_contracts": state.get("tool_contracts", []),
    }
    state["plan_review_payload"] = payload
    decision = interrupt(payload)
    if not isinstance(decision, dict):
        decision = {}
    approved = decision.get("approved_plan") or state.get("task_plan", [])
    state["approved_plan"] = validate_plan_steps(list(approved))
    state["task_plan"] = state["approved_plan"]
    if decision.get("plan_source"):
        state["plan_source"] = str(decision["plan_source"])
    elif decision.get("edited"):
        state["plan_source"] = "user_edited"
    else:
        state["plan_source"] = f"{state.get('plan_source', 'rule_based')}:approved"
    state.setdefault("observations", {})["plan_preview"] = state["approved_plan"]
    state.setdefault("observations", {})["plan_source"] = state.get("plan_source")
    state.setdefault("observations", {})["plan_rationale"] = state.get("plan_rationale")
    state.setdefault("execution_trace", []).append(
        {
            "run_id": state.get("run_id"),
            "node": "review_plan",
            "tool": "human_plan_review",
            "params": {"approved_steps": len(state["approved_plan"])},
            "status": "success",
            "summary": f"Plan approved with {len(state['approved_plan'])} steps.",
            "warnings": [],
            "errors": [],
            "duration_sec": 0,
        }
    )
    return state


def preview_plan_node(state: SpatialAgentState) -> SpatialAgentState:
    """Legacy non-interrupt preview helper retained for compatibility tests."""

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


def _current_step(state: SpatialAgentState) -> dict[str, Any] | None:
    plan = state.get("approved_plan", [])
    index = int(state.get("current_step_index", 0))
    if index >= len(plan):
        return None
    return dict(plan[index])


def execute_tool_node(state: SpatialAgentState) -> SpatialAgentState:
    step = _current_step(state)
    if step is None:
        state["current_step"] = "complete"
        state["needs_repair"] = False
        state["last_result"] = ToolResult(status="success", summary="No remaining workflow steps.").to_dict()
        return state

    tool_name = str(step["tool"])
    state["current_step"] = tool_name
    step_id = str(step.get("id") or tool_name)
    attempts = dict(state.get("step_attempts", {}))
    attempt_no = int(attempts.get(step_id, 0)) + 1
    attempts[step_id] = attempt_no
    state["step_attempts"] = attempts
    try:
        func = get_tool(tool_name).function
    except KeyError as exc:
        result = ToolResult(status="failed", summary=f"Unknown tool `{tool_name}`.", errors=[str(exc)])
        _record_trace(state, node="execute_tool", tool=tool_name, params={}, result=result, duration=0)
        return state

    params = _prepare_tool_params(func, dict(step.get("params", {})), state)
    dataset_ref = str(state.get("working_dataset_ref") or state.get("data_path") or "")
    start = time.time()
    try:
        adata = DEFAULT_DATASET_STORE.load(dataset_ref)
    except Exception as exc:  # noqa: BLE001
        result = ToolResult(
            status="failed",
            summary=f"Failed to load working AnnData for `{tool_name}`: {exc}",
            errors=[f"{type(exc).__name__}: {exc}"],
        )
        _record_trace(state, node="execute_tool", tool=tool_name, params=params, result=result, duration=time.time() - start)
        return state

    result = safe_tool_call(func, adata, **params)
    if result.status in {"success", "skipped", "skipped_optional"}:
        try:
            DEFAULT_DATASET_STORE.save(adata, dataset_ref)
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"Working AnnData save failed after `{tool_name}`: {exc}")
    status = "success_after_retry" if result.status == "success" and attempt_no > 1 else None
    _record_trace(
        state,
        node="execute_tool",
        tool=tool_name,
        params=params,
        result=result,
        duration=time.time() - start,
        status_override=status,
        extra={"attempt": attempt_no, "step_id": step_id},
    )
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


def _first_valid_color(state: SpatialAgentState) -> str | None:
    summary = state.get("dataset_summary", {})
    for key in ["leiden", "cluster", "clusters"]:
        if key in summary.get("obs_columns", []):
            return key
    try:
        adata = DEFAULT_DATASET_STORE.load(str(state.get("working_dataset_ref") or ""))
    except Exception:
        return None
    for key in ["leiden", "cluster", "clusters"]:
        if key in adata.obs:
            return key
    obs = getattr(adata, "obs", None)
    obs_columns = list(map(str, obs.columns[:20])) if obs is not None else []
    return obs_columns[0] if obs_columns else None


def _repair_patch_for_step(
    state: SpatialAgentState,
    step: dict[str, Any],
    diagnosis: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any] | None:
    tool = str(step.get("tool") or "")
    category = str(diagnosis.get("category") or "")
    params = dict(step.get("params", {}))
    if tool in {"plot_umap", "plot_spatial"} and category == "missing_input_or_column":
        color = _first_valid_color(state)
        if color and color != params.get("color"):
            return {"color": color}
    if tool == "rank_markers" and category == "missing_input_or_column":
        color = _first_valid_color(state)
        if color and color != params.get("groupby"):
            return {"groupby": color}
    if tool == "plot_gene_panel" and category in {"unmatched_genes", "missing_input_or_column"}:
        suggested = result.get("observations", {}).get("suggested_genes", [])
        if suggested:
            return {"genes": list(dict.fromkeys(map(str, suggested)))[:8]}
    if tool == "suggest_cluster_annotations" and not params.get("reference"):
        return {"reference": "generic_marker_lexicon"}
    return None


def repair_or_continue_node(state: SpatialAgentState, *, llm_gateway: LLMGateway | None = None) -> SpatialAgentState:
    state["repair_attempts"] = int(state.get("repair_attempts", 0)) + 1
    plan = list(state.get("approved_plan", []))
    index = int(state.get("current_step_index", 0))
    failed_step = dict(plan[index]) if index < len(plan) else {"tool": state.get("current_step", "unknown"), "params": {}}
    tool_name = str(failed_step.get("tool") or state.get("current_step", "unknown"))
    result = dict(state.get("last_result", {}))
    contract_payload: dict[str, Any] = {}
    contract = None
    optional_dependency = None
    try:
        spec = get_tool(tool_name)
        contract = spec.contract
        optional_dependency = spec.optional_dependency
        contract_payload = asdict(spec.contract)
    except Exception:
        contract_payload = {}

    gateway = llm_gateway or LLMGateway.from_env()
    repair_decision = gateway.propose_repair(
        failed_step=failed_step,
        tool_result=result,
        tool_contract=contract_payload,
        dataset_profile=state.get("dataset_profile") or state.get("dataset_summary", {}),
    )
    state["llm_enabled"] = state.get("llm_enabled", False) or gateway.enabled
    state["llm_mode"] = gateway.active_mode
    state["llm_status"] = gateway.safe_status()
    _extend_llm_telemetry(state, gateway)
    diagnosis = diagnose_tool_failure(
        failed_step,
        result,
        contract,
        optional_dependency=optional_dependency,
        llm_suggestion=repair_decision.model_dump(),
    )
    step_id = str(failed_step.get("id") or tool_name)
    attempt_no = int(state.get("step_attempts", {}).get(step_id, 1))
    max_attempts = int(failed_step.get("max_attempts") or 2)
    patch = _repair_patch_for_step(state, failed_step, diagnosis, result)
    if patch and attempt_no < max_attempts:
        plan[index] = {**failed_step, "params": {**dict(failed_step.get("params", {})), **patch}}
        state["approved_plan"] = validate_plan_steps(plan)
        diagnosis["action"] = "retry_with_parameter_patch"
        diagnosis["patch"] = patch
        message = f"`{tool_name}` will retry with adjusted parameters: {patch}."
        state.setdefault("repair_log", []).append(diagnosis)
        state.setdefault("observations", {})["repair_log"] = state.get("repair_log", [])
        state.setdefault("warnings", []).append(message)
        state.setdefault("execution_trace", []).append(
            {
                "run_id": state.get("run_id"),
                "node": "repair_or_continue",
                "tool": tool_name,
                "params": {"step_id": step_id, "action": "retry_with_parameter_patch", "patch": patch},
                "status": "retrying",
                "summary": message,
                "warnings": [message],
                "errors": [],
                "duration_sec": 0,
                "repair": diagnosis,
            }
        )
        state["needs_repair"] = False
        return state

    action = str(diagnosis.get("action") or "")
    skip_status = "skipped_optional" if failed_step.get("optional") or action == "skip_optional_step" else "failed"
    message = str(diagnosis.get("user_message") or f"`{tool_name}` failed and was recorded.")
    state.setdefault("repair_log", []).append(diagnosis)
    state.setdefault("observations", {})["repair_log"] = state.get("repair_log", [])
    state.setdefault("warnings", []).append(message)
    if skip_status == "failed" and not failed_step.get("optional"):
        state["aborted"] = True
        message = f"{message} Workflow aborted after bounded repair attempts."
    state.setdefault("execution_trace", []).append(
        {
            "run_id": state.get("run_id"),
            "node": "repair_or_continue",
            "tool": tool_name,
            "params": {
                "step_id": step_id,
                "category": diagnosis.get("category"),
                "action": diagnosis.get("action"),
                "attempts": attempt_no,
                "max_attempts": max_attempts,
            },
            "status": skip_status,
            "summary": message,
            "warnings": [message],
            "errors": [] if skip_status == "skipped_optional" else result.get("errors", []),
            "duration_sec": 0,
            "repair": diagnosis,
        }
    )
    state["needs_repair"] = False
    state["current_step_index"] = len(plan) if state.get("aborted") else index + 1
    return state


def interpret_node(state: SpatialAgentState, *, llm_gateway: LLMGateway | None = None) -> SpatialAgentState:
    gateway = llm_gateway or LLMGateway.from_env()
    findings = gateway.synthesize_findings(
        query=state.get("user_query", ""),
        dataset_profile=state.get("dataset_profile") or state.get("dataset_summary", {}),
        evidence_packs=state.get("evidence_packs", []),
        warnings=state.get("warnings", []),
    )
    state["scientific_findings"] = [finding.model_dump() for finding in findings]
    claims = gateway.synthesize_evidence_claims(
        query=state.get("user_query", ""),
        dataset_profile=state.get("dataset_profile") or state.get("dataset_summary", {}),
        evidence_artifacts=state.get("evidence_artifacts", []),
        execution_trace=state.get("execution_trace", []),
    )
    state["evidence_claims"] = [claim.model_dump() for claim in claims]
    state["llm_enabled"] = state.get("llm_enabled", False) or gateway.enabled
    state["llm_mode"] = gateway.active_mode
    state["llm_status"] = gateway.safe_status()
    _extend_llm_telemetry(state, gateway)
    llm_interpretation = gateway.synthesize_interpretation(
        query=state.get("user_query", ""),
        dataset_profile=state.get("dataset_profile") or state.get("dataset_summary", {}),
        evidence_artifacts=state.get("evidence_artifacts", []),
        findings=state.get("scientific_findings", []),
        execution_trace=state.get("execution_trace", []),
        warnings=state.get("warnings", []),
    )
    _extend_llm_telemetry(state, gateway)
    if llm_interpretation:
        state["final_answer"] = llm_interpretation
        return state
    if findings:
        bullets = " ".join(
            f"{index}. {finding.statement} Evidence: {', '.join(finding.evidence_ids)}."
            for index, finding in enumerate(findings[:4], start=1)
        )
        caveats = " ".join(caveat for finding in findings[:4] for caveat in finding.caveats[:1])
        state["final_answer"] = f"Research brief: {bullets} Caveats: {caveats}".strip()
        return state
    success_count = sum(
        1
        for item in state.get("execution_trace", [])
        if item.get("node") == "execute_tool" and str(item.get("status", "")).startswith("success")
    )
    pack_count = len(state.get("evidence_packs", []))
    warnings_count = len(state.get("warnings", []))
    state["final_answer"] = (
        f"SpatialScope completed {success_count} successful analysis tool steps in {state.get('mode')} mode and produced "
        f"{pack_count} compact evidence packs. Gene-level figures and marker ranking use a safe expression source when available; "
        f"all biological interpretations are exploratory and bounded by the recorded figures, tables, and trace. "
        f"Warnings recorded: {warnings_count}."
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


def _route_after_repair(state: SpatialAgentState) -> str:
    if state.get("aborted"):
        return "interpret"
    if int(state.get("current_step_index", 0)) < len(state.get("approved_plan", [])):
        return "execute"
    return "interpret"


def build_langgraph(checkpointer: Any | None = None, *, llm_gateway: LLMGateway | None = None):
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(SpatialAgentState)
    graph.add_node("parse_request", lambda state: parse_request_node(state, llm_gateway=llm_gateway))
    graph.add_node("inspect_dataset", inspect_dataset_node)
    graph.add_node("plan_analysis", lambda state: plan_analysis_node(state, llm_gateway=llm_gateway))
    graph.add_node("review_plan", review_plan_node)
    graph.add_node("execute_tool", execute_tool_node)
    graph.add_node("validate_result", validate_result_node)
    graph.add_node("repair_or_continue", lambda state: repair_or_continue_node(state, llm_gateway=llm_gateway))
    graph.add_node("interpret", lambda state: interpret_node(state, llm_gateway=llm_gateway))
    graph.add_node("report", report_node)
    graph.add_edge(START, "inspect_dataset")
    graph.add_edge("inspect_dataset", "parse_request")
    graph.add_edge("parse_request", "plan_analysis")
    graph.add_edge("plan_analysis", "review_plan")
    graph.add_edge("review_plan", "execute_tool")
    graph.add_edge("execute_tool", "validate_result")
    graph.add_conditional_edges(
        "validate_result",
        _route_after_validate,
        {"repair": "repair_or_continue", "execute": "execute_tool", "interpret": "interpret"},
    )
    graph.add_conditional_edges(
        "repair_or_continue",
        _route_after_repair,
        {"execute": "execute_tool", "interpret": "interpret"},
    )
    graph.add_edge("interpret", "report")
    graph.add_edge("report", END)
    return graph.compile(checkpointer=checkpointer or InMemorySaver())


def run_fallback_graph(state: SpatialAgentState) -> SpatialAgentState:
    """Compatibility path for tests that need non-interactive execution."""

    state = inspect_dataset_node(state)
    state = parse_request_node(state)
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
    from spatialscope.agent.runtime import AgentRuntime

    runtime = AgentRuntime()
    return runtime.start_run(data_path=data_path, query=query, mode=mode, outdir=outdir, auto_approve=False)


def execute_agent_state(
    state: SpatialAgentState,
    *,
    approved_plan: list[dict[str, Any]] | None = None,
    plan_source: str | None = None,
) -> SpatialAgentState:
    from spatialscope.agent.runtime import AgentRuntime

    runtime = AgentRuntime()
    return runtime.resume_run(
        str(state.get("thread_id") or state.get("run_id")),
        approved_plan=approved_plan or list(state.get("task_plan", [])),
        plan_source=plan_source or "user_edited",
    )


def run_agent(
    *,
    data_path: str,
    query: str,
    mode: RunMode = "quick",
    outdir: str = "outputs/runs",
) -> SpatialAgentState:
    from spatialscope.agent.runtime import AgentRuntime

    runtime = AgentRuntime()
    return runtime.start_run(data_path=data_path, query=query, mode=mode, outdir=outdir, auto_approve=True)
