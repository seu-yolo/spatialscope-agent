from __future__ import annotations

from typing import Any, Literal, TypedDict


RunMode = Literal["quick", "standard", "advanced"]


class SpatialAgentState(TypedDict, total=False):
    run_id: str
    user_query: str
    llm_enabled: bool
    data_path: str | None
    dataset_ref: str | None
    working_dataset_ref: str | None
    thread_id: str
    dataset_hash: str | None
    adata_path: str | None
    dataset_profile: dict[str, Any]
    research_brief: dict[str, Any]
    dataset_summary: dict[str, Any]
    task_plan: list[dict[str, Any]]
    approved_plan: list[dict[str, Any]]
    plan_review_payload: dict[str, Any]
    plan_source: str
    plan_rationale: str
    tool_contracts: list[dict[str, Any]]
    current_step: str
    current_step_index: int
    parameters: dict[str, Any]
    generated_figures: list[dict[str, Any]]
    generated_tables: list[dict[str, Any]]
    observations: dict[str, Any]
    warnings: list[str]
    errors: list[str]
    llm_calls: list[dict[str, Any]]
    evidence_artifacts: list[dict[str, Any]]
    evidence_packs: list[dict[str, Any]]
    evidence_claims: list[dict[str, Any]]
    scientific_findings: list[dict[str, Any]]
    clarification_items: list[dict[str, Any]]
    step_attempts: dict[str, int]
    aborted: bool
    repair_attempts: int
    repair_log: list[dict[str, Any]]
    execution_trace: list[dict[str, Any]]
    environment: dict[str, Any]
    final_answer: str | None
    report_path: str | None
    outdir: str
    run_dir: str
    figures_dir: str
    tables_dir: str
    intermediate_dir: str
    mode: RunMode
    parsed_request: dict[str, Any]
    last_result: dict[str, Any]
    needs_repair: bool


def initial_state(
    *,
    run_id: str,
    data_path: str,
    query: str,
    mode: RunMode,
    outdir: str,
    run_dir: str,
    figures_dir: str,
    tables_dir: str,
    intermediate_dir: str,
) -> SpatialAgentState:
    return {
        "run_id": run_id,
        "user_query": query,
        "llm_enabled": False,
        "data_path": data_path,
        "dataset_ref": data_path,
        "working_dataset_ref": None,
        "thread_id": run_id,
        "adata_path": None,
        "dataset_hash": None,
        "dataset_profile": {},
        "research_brief": {},
        "dataset_summary": {},
        "task_plan": [],
        "approved_plan": [],
        "plan_review_payload": {},
        "plan_source": "rule_based",
        "plan_rationale": "",
        "tool_contracts": [],
        "current_step": "",
        "current_step_index": 0,
        "parameters": {"mode": mode},
        "generated_figures": [],
        "generated_tables": [],
        "observations": {},
        "warnings": [],
        "errors": [],
        "llm_calls": [],
        "evidence_artifacts": [],
        "evidence_packs": [],
        "evidence_claims": [],
        "scientific_findings": [],
        "clarification_items": [],
        "step_attempts": {},
        "aborted": False,
        "repair_attempts": 0,
        "repair_log": [],
        "execution_trace": [],
        "environment": {},
        "final_answer": None,
        "report_path": None,
        "outdir": outdir,
        "run_dir": run_dir,
        "figures_dir": figures_dir,
        "tables_dir": tables_dir,
        "intermediate_dir": intermediate_dir,
        "mode": mode,
        "parsed_request": {},
        "last_result": {},
        "needs_repair": False,
    }
