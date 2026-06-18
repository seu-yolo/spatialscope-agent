from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from spatialscope.tools.registry import available_tool_names
from spatialscope.utils.paths import public_state_copy, write_json


STATUS_SCORE = {"pass": 100, "warn": 65, "fail": 0}
SYSTEM_TRACE_TOOLS = {"load_h5ad", "generate_report"}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _check(
    name: str,
    status: str,
    summary: str,
    evidence: str,
    recommendation: str = "",
) -> dict[str, Any]:
    if status not in STATUS_SCORE:
        status = "warn"
    return {
        "name": name,
        "status": status,
        "score": STATUS_SCORE[status],
        "summary": summary,
        "evidence": evidence,
        "recommendation": recommendation,
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _tool_name(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    return str(item.get("tool") or "")


def _status_counts(checks: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"pass": 0, "warn": 0, "fail": 0}
    for check in checks:
        status = str(check.get("status") or "warn")
        if status in counts:
            counts[status] += 1
    return counts


def _counter_gap(expected: list[str], observed: list[str]) -> list[str]:
    expected_counts = Counter(expected)
    observed_counts = Counter(observed)
    missing: list[str] = []
    for tool, count in expected_counts.items():
        gap = count - observed_counts.get(tool, 0)
        missing.extend([tool] * max(gap, 0))
    return missing


def build_agent_audit(state: dict[str, Any]) -> dict[str, Any]:
    """Build a behavior-level self-audit for the agent workflow.

    Quality gates judge the run outputs. This audit judges whether the agent
    behaved in a traceable, contract-bound, repair-aware way.
    """

    registry_tools = available_tool_names()
    plan = [item for item in _as_list(state.get("approved_plan")) if isinstance(item, dict)]
    trace = [item for item in _as_list(state.get("execution_trace")) if isinstance(item, dict)]
    repairs = [item for item in _as_list(state.get("repair_log")) if isinstance(item, dict)]
    figures = _as_list(state.get("generated_figures"))
    tables = _as_list(state.get("generated_tables"))
    public_state = public_state_copy(state)

    planned_tools = [_tool_name(step) for step in plan if _tool_name(step)]
    executed_tools = [
        _tool_name(item)
        for item in trace
        if item.get("node") == "execute_tool" and _tool_name(item)
    ]
    traced_tools = [_tool_name(item) for item in trace if _tool_name(item)]
    unknown_plan_tools = sorted({tool for tool in planned_tools if tool not in registry_tools})
    unknown_trace_tools = sorted(
        {
            tool
            for tool in traced_tools
            if tool not in registry_tools and tool not in SYSTEM_TRACE_TOOLS
        }
    )

    checks: list[dict[str, Any]] = []

    if not plan:
        checks.append(
            _check(
                "Plan contract alignment",
                "fail",
                "No approved analysis plan was available for audit.",
                "approved_plan is empty",
                "Generate and approve a plan before running the workflow.",
            )
        )
    elif unknown_plan_tools:
        checks.append(
            _check(
                "Plan contract alignment",
                "fail",
                "The approved plan contains tools outside the registry.",
                ", ".join(unknown_plan_tools),
                "Route plans through registry validation before execution.",
            )
        )
    else:
        checks.append(
            _check(
                "Plan contract alignment",
                "pass",
                "All approved plan steps map to registered tool contracts.",
                f"{len(planned_tools)} planned steps, {len(registry_tools)} registered tools",
            )
        )

    contract_rows = [item for item in _as_list(state.get("tool_contracts")) if isinstance(item, dict)]
    contract_names = {str(item.get("name") or "") for item in contract_rows if item.get("name")}
    if contract_names and registry_tools.issubset(contract_names):
        checks.append(
            _check(
                "Tool contract visibility",
                "pass",
                "The planner state includes the full public tool contract registry.",
                f"{len(contract_names)} contracts exposed",
            )
        )
    elif contract_names:
        missing = sorted(registry_tools - contract_names)
        checks.append(
            _check(
                "Tool contract visibility",
                "warn",
                "Tool contracts are present but do not cover the full registry.",
                f"{len(contract_names)} contracts exposed; missing={missing[:5]}",
                "Refresh the planner state from `list_tool_contracts()`.",
            )
        )
    else:
        checks.append(
            _check(
                "Tool contract visibility",
                "fail",
                "No public tool contracts were recorded in state.",
                "tool_contracts is empty",
                "Run the planner node before execution.",
            )
        )

    missing_executions = _counter_gap(planned_tools, executed_tools)
    if plan and not executed_tools:
        checks.append(
            _check(
                "Plan execution coverage",
                "fail",
                "No executable tool trace was recorded for the approved plan.",
                f"{len(planned_tools)} planned steps, 0 executed steps",
                "Run the plan through the agent executor so each step is traceable.",
            )
        )
    elif missing_executions:
        checks.append(
            _check(
                "Plan execution coverage",
                "fail",
                "Some approved plan tools are missing from the execution trace.",
                "missing=" + ", ".join(missing_executions),
                "Re-run the workflow or inspect aborted trace records.",
            )
        )
    elif planned_tools == executed_tools:
        checks.append(
            _check(
                "Plan execution coverage",
                "pass",
                "The execution trace matches the approved plan order.",
                f"{len(executed_tools)} executed steps",
            )
        )
    else:
        checks.append(
            _check(
                "Plan execution coverage",
                "warn",
                "All planned tools were executed, but the order differs from the plan.",
                f"planned={planned_tools}; executed={executed_tools}",
                "Inspect whether user edits or repair routing changed execution order.",
            )
        )

    if unknown_trace_tools:
        checks.append(
            _check(
                "Trace registry discipline",
                "fail",
                "The trace contains non-system tools outside the registry.",
                ", ".join(unknown_trace_tools),
                "Keep tool execution behind the registry so contracts and repairs apply.",
            )
        )
    elif trace:
        checks.append(
            _check(
                "Trace registry discipline",
                "pass",
                "Trace tools are either registered tools or expected system nodes.",
                f"{len(trace)} trace records",
            )
        )
    else:
        checks.append(
            _check(
                "Trace registry discipline",
                "fail",
                "No execution trace was recorded.",
                "execution_trace is empty",
                "Run through LangGraph or the fallback executor.",
            )
        )

    failed_trace = [item for item in trace if item.get("status") == "failed"]
    repaired_trace = [item for item in trace if item.get("status") == "repaired"]
    if not failed_trace:
        checks.append(
            _check(
                "Repair accountability",
                "pass",
                "No failed tool calls require repair handling.",
                f"{len(repairs)} repair records, {len(repaired_trace)} repaired trace records",
            )
        )
    elif repairs or repaired_trace:
        checks.append(
            _check(
                "Repair accountability",
                "warn",
                "Failed tool calls have repair records, but downstream interpretation should remain cautious.",
                f"{len(failed_trace)} failed calls, {len(repairs)} repair records",
                "Review Repair Diagnostics before treating results as final.",
            )
        )
    else:
        checks.append(
            _check(
                "Repair accountability",
                "fail",
                "Failed tool calls were recorded without repair diagnostics.",
                f"{len(failed_trace)} failed calls, 0 repair records",
                "Route failures through `repair_or_continue` before reporting.",
            )
        )

    final_answer = str(state.get("final_answer") or "").strip()
    if final_answer and trace and (figures or tables):
        checks.append(
            _check(
                "Evidence-bounded interpretation",
                "pass",
                "The final answer is paired with trace records and generated evidence artifacts.",
                f"{len(figures)} figures, {len(tables)} tables, {len(trace)} trace records",
            )
        )
    elif final_answer and trace:
        checks.append(
            _check(
                "Evidence-bounded interpretation",
                "warn",
                "The final answer has trace context but limited figure/table evidence.",
                f"{len(figures)} figures, {len(tables)} tables",
                "Generate tangible evidence artifacts before presenting biological conclusions.",
            )
        )
    else:
        checks.append(
            _check(
                "Evidence-bounded interpretation",
                "fail",
                "No evidence-bounded final interpretation was recorded.",
                "requires final_answer and execution_trace",
                "Run interpretation after tool execution and include limitations.",
            )
        )

    raw_state_keys = [key for key in public_state if str(key).startswith("_") or key in {"adata", "raw_matrix", "expression_matrix"}]
    if raw_state_keys:
        checks.append(
            _check(
                "Public-state privacy boundary",
                "fail",
                "Public state contains raw or private analysis keys.",
                ", ".join(raw_state_keys),
                "Only export summaries, traces, figures, tables, and metadata.",
            )
        )
    else:
        checks.append(
            _check(
                "Public-state privacy boundary",
                "pass",
                "Public state excludes raw AnnData/private matrix fields.",
                f"{len(public_state)} public keys",
            )
        )

    counts = _status_counts(checks)
    if counts["fail"]:
        overall_status = "fail"
    elif counts["warn"]:
        overall_status = "warn"
    else:
        overall_status = "pass"
    score = round(sum(int(check["score"]) for check in checks) / max(len(checks), 1))

    return {
        "schema_version": "1.0",
        "run_id": state.get("run_id"),
        "overall_status": overall_status,
        "score": score,
        "status_counts": counts,
        "checks": checks,
        "planned_tools": planned_tools,
        "executed_tools": executed_tools,
        "unknown_plan_tools": unknown_plan_tools,
        "unknown_trace_tools": unknown_trace_tools,
        "repair_summary": {
            "failed_trace_records": len(failed_trace),
            "repaired_trace_records": len(repaired_trace),
            "repair_records": len(repairs),
        },
        "evidence_summary": {
            "figures": len(figures),
            "tables": len(tables),
            "trace_records": len(trace),
            "has_final_answer": bool(final_answer),
        },
    }


def write_agent_audit(state: dict[str, Any], run_dir: str | Path | None = None) -> dict[str, Any]:
    root = Path(str(run_dir or state.get("run_dir") or "."))
    audit = build_agent_audit(state)
    write_json(root / "agent_audit.json", audit)
    return audit


def load_agent_audit(run_dir: str | Path) -> dict[str, Any]:
    return _read_json(Path(run_dir) / "agent_audit.json")
