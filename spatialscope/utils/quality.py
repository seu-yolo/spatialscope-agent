from __future__ import annotations

from typing import Any


STATUS_SCORE = {"pass": 100, "warn": 65, "fail": 0}


def _gate(name: str, status: str, summary: str, evidence: str, recommendation: str = "") -> dict[str, Any]:
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


def _status_counts(trace: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"success": 0, "skipped": 0, "failed": 0, "repaired": 0}
    for item in trace:
        status = str(item.get("status", ""))
        if status in counts:
            counts[status] += 1
    return counts


def build_quality_report(state: dict[str, Any]) -> dict[str, Any]:
    """Build a compact run-quality self-audit from public state evidence."""

    dataset = state.get("dataset_summary", {}) if isinstance(state.get("dataset_summary"), dict) else {}
    trace = [item for item in state.get("execution_trace", []) if isinstance(item, dict)]
    counts = _status_counts(trace)
    figures = state.get("generated_figures", [])
    tables = state.get("generated_tables", [])
    repairs = state.get("repair_log", [])
    warnings = state.get("warnings", [])
    errors = state.get("errors", [])
    plan = state.get("approved_plan", [])

    gates: list[dict[str, Any]] = []

    n_obs = dataset.get("n_obs")
    n_vars = dataset.get("n_vars")
    if state.get("dataset_hash") and n_obs and n_vars:
        gates.append(
            _gate(
                "Dataset readiness",
                "pass",
                "Dataset was loaded and hashed.",
                f"{n_obs} observations, {n_vars} genes, hash={str(state.get('dataset_hash'))[:12]}...",
            )
        )
    elif dataset:
        gates.append(
            _gate(
                "Dataset readiness",
                "warn",
                "Dataset summary exists, but hash or dimensions are incomplete.",
                str({key: dataset.get(key) for key in ["n_obs", "n_vars", "has_spatial"]}),
                "Inspect the AnnData input and rerun dataset inspection.",
            )
        )
    else:
        gates.append(
            _gate(
                "Dataset readiness",
                "fail",
                "No dataset summary was recorded.",
                "dataset_summary is empty",
                "Load a valid `.h5ad` file before running analysis steps.",
            )
        )

    if plan:
        gates.append(
            _gate(
                "Plan provenance",
                "pass",
                "Approved analysis plan is recorded.",
                f"{len(plan)} steps from {state.get('plan_source', 'unknown')}",
            )
        )
    else:
        gates.append(
            _gate(
                "Plan provenance",
                "fail",
                "No approved analysis plan was recorded.",
                "approved_plan is empty",
                "Generate and approve a plan before execution.",
            )
        )

    if not trace:
        gates.append(
            _gate(
                "Execution trace",
                "fail",
                "No execution trace was recorded.",
                "execution_trace is empty",
                "Run the workflow through the agent executor so tool calls are traceable.",
            )
        )
    elif counts["failed"] == 0 and counts["repaired"] == 0:
        gates.append(
            _gate(
                "Execution trace",
                "pass",
                "All recorded tool steps completed without repair.",
                f"{counts['success']} success, {counts['failed']} failed, {counts['repaired']} repaired",
            )
        )
    elif counts["repaired"] >= counts["failed"]:
        gates.append(
            _gate(
                "Execution trace",
                "warn",
                "Workflow continued after repaired or skipped failures.",
                f"{counts['success']} success, {counts['failed']} failed, {counts['repaired']} repaired",
                "Review Repair Diagnostics before interpreting downstream results.",
            )
        )
    else:
        gates.append(
            _gate(
                "Execution trace",
                "fail",
                "At least one failed step lacks a matching repair record.",
                f"{counts['success']} success, {counts['failed']} failed, {counts['repaired']} repaired",
                "Inspect failed trace rows and rerun with corrected parameters.",
            )
        )

    if figures and tables:
        gates.append(
            _gate("Evidence outputs", "pass", "Figures and tables were generated.", f"{len(figures)} figures, {len(tables)} tables")
        )
    elif figures or tables:
        gates.append(
            _gate(
                "Evidence outputs",
                "warn",
                "Only partial evidence outputs were generated.",
                f"{len(figures)} figures, {len(tables)} tables",
                "Check whether the selected mode should produce both figures and tables.",
            )
        )
    else:
        gates.append(
            _gate(
                "Evidence outputs",
                "fail",
                "No figure or table artifacts were recorded.",
                "generated_figures and generated_tables are empty",
                "Run analysis tools that generate tangible evidence before reporting.",
            )
        )

    if errors:
        status = "warn" if repairs else "fail"
        gates.append(
            _gate(
                "Error review",
                status,
                "Errors were recorded during the run.",
                f"{len(errors)} errors, {len(repairs)} repair records",
                "Resolve or explain errors before treating the run as final.",
            )
        )
    elif warnings:
        gates.append(
            _gate(
                "Error review",
                "warn",
                "Warnings were recorded but no hard errors remain.",
                f"{len(warnings)} warnings",
                "Read warnings and decide whether they affect the biological question.",
            )
        )
    else:
        gates.append(_gate("Error review", "pass", "No warnings or errors were recorded.", "0 warnings, 0 errors"))

    if state.get("final_answer"):
        gates.append(
            _gate(
                "Interpretation",
                "pass",
                "A final interpretation summary was recorded.",
                "final_answer is present",
            )
        )
    else:
        gates.append(
            _gate(
                "Interpretation",
                "warn",
                "No final interpretation summary was recorded.",
                "final_answer is empty",
                "Generate the report through the agent so interpretation and limitations are bundled.",
            )
        )

    if state.get("environment") and state.get("parameters") and state.get("run_id"):
        gates.append(
            _gate(
                "Reproducibility metadata",
                "pass",
                "Run id, parameters, and environment summary are available.",
                f"run_id={state.get('run_id')}",
            )
        )
    else:
        gates.append(
            _gate(
                "Reproducibility metadata",
                "warn",
                "Some reproducibility metadata are missing.",
                "requires run_id, parameters, and environment",
                "Ensure the run was created through `create_agent_state` or the CLI/Streamlit workflow.",
            )
        )

    score = round(sum(int(gate["score"]) for gate in gates) / max(len(gates), 1))
    status_counts = {"pass": 0, "warn": 0, "fail": 0}
    for gate in gates:
        status_counts[str(gate["status"])] += 1
    if status_counts["fail"]:
        overall_status = "fail"
    elif status_counts["warn"]:
        overall_status = "warn"
    else:
        overall_status = "pass"
    return {
        "schema_version": "1.0",
        "overall_status": overall_status,
        "score": score,
        "status_counts": status_counts,
        "gates": gates,
    }
