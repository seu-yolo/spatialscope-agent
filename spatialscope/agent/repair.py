from __future__ import annotations

from typing import Any

from spatialscope.tools.base import ToolContract


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list | tuple | set):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _contract_list(contract: ToolContract | dict[str, Any] | None, field: str) -> list[str]:
    if contract is None:
        return []
    if isinstance(contract, dict):
        return _as_list(contract.get(field))
    return _as_list(getattr(contract, field, []))


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        normalized = item.strip()
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            out.append(normalized)
    return out


def _infer_category(summary: str, errors: list[str]) -> tuple[str, str, float, list[str]]:
    text = " ".join([summary, *errors]).lower()
    if any(term in text for term in ["no module named", "not installed", "missing dependency", "importerror", "modulenotfounderror"]):
        return (
            "missing_dependency",
            "A required Python package or optional analysis backend appears to be unavailable.",
            0.85,
            ["Install the missing dependency in the conda environment, then rerun the step."],
        )
    if "spatial" in text and any(term in text for term in ["missing", "absent", "not found", "keyerror"]):
        return (
            "missing_spatial_coordinates",
            "The selected data object does not expose usable spatial coordinates for this tool.",
            0.8,
            ["Use an AnnData file with `adata.obsm['spatial']`, or skip spatial-only tools for this dataset."],
        )
    if any(term in text for term in ["unmatched_genes", "need clarification", "no requested genes match", "no genes", "gene is absent", "gene not found"]):
        return (
            "unmatched_genes",
            "Requested genes could not be matched to the dataset gene index.",
            0.78,
            ["Check gene symbols, species naming conventions, or use the closest gene suggestions from the run trace."],
        )
    if any(term in text for term in ["too few", "remove all", "removed all", "empty", "zero observations", "zero genes"]):
        return (
            "insufficient_data_after_filtering",
            "The dataset may be too small or the current filtering/modeling settings are too strict.",
            0.75,
            ["Relax QC thresholds or reduce dimensionality/modeling requirements before rerunning."],
        )
    if any(term in text for term in ["missing", "absent", "not found", "keyerror"]):
        return (
            "missing_input_or_column",
            "The tool expected an input field, embedding, gene, or observation column that was not available.",
            0.68,
            ["Run prerequisite tools first, or change the parameter to a valid key recorded in the dataset summary."],
        )
    return (
        "tool_execution_error",
        "The tool raised an execution error that needs manual review of the recorded summary and parameters.",
        0.45,
        ["Review the failed step parameters, tool preconditions, and original traceback summary."],
    )


def diagnose_tool_failure(
    step: dict[str, Any],
    tool_result: dict[str, Any],
    contract: ToolContract | dict[str, Any] | None = None,
    *,
    optional_dependency: str | None = None,
    llm_suggestion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a compact, reproducible repair diagnosis from public tool evidence."""

    tool = str(step.get("tool") or "unknown")
    step_id = str(step.get("id") or tool)
    summary = str(tool_result.get("summary") or "")
    errors = _as_list(tool_result.get("errors"))
    category, likely_cause, confidence, inferred_actions = _infer_category(summary, errors)

    if optional_dependency and category == "missing_dependency":
        inferred_actions.append(f"Install optional dependency `{optional_dependency}` if this advanced step is required.")

    optional = bool(step.get("optional"))
    action = "skip_optional_step" if optional else "skip_failed_step"
    continue_policy = (
        "Continue the workflow after recording this optional advanced step as skipped."
        if optional
        else "Continue the workflow so available evidence is preserved, but review this failure before trusting downstream results."
    )

    llm_actions: list[str] = []
    llm_payload: dict[str, Any] | None = None
    if isinstance(llm_suggestion, dict):
        llm_actions = _as_list(llm_suggestion.get("recommended_actions"))
        llm_payload = {
            "likely_cause": str(llm_suggestion.get("likely_cause") or "").strip(),
            "recommended_actions": llm_actions,
            "user_message": str(llm_suggestion.get("user_message") or "").strip(),
            "should_retry": bool(llm_suggestion.get("should_retry", False)),
        }
        if llm_payload["likely_cause"]:
            likely_cause = llm_payload["likely_cause"]
        if llm_payload["should_retry"]:
            continue_policy = (
                "A future interactive run may retry with adjusted parameters; this run records the diagnosis and continues."
            )

    recommendations = _dedupe(
        _contract_list(contract, "repair_strategy")
        + inferred_actions
        + llm_actions
    )
    common_failures = _contract_list(contract, "common_failures")

    user_message = (
        f"`{tool}` failed with category `{category}`. {likely_cause} "
        f"Action taken: {action.replace('_', ' ')}."
    )
    if llm_payload and llm_payload.get("user_message"):
        user_message = str(llm_payload["user_message"])

    return {
        "step_id": step_id,
        "tool": tool,
        "params": dict(step.get("params", {})),
        "optional": optional,
        "category": category,
        "likely_cause": likely_cause,
        "confidence": confidence,
        "action": action,
        "continue_policy": continue_policy,
        "recommended_actions": recommendations,
        "contract_common_failures": common_failures,
        "source": "rule_based+llm" if llm_payload else "rule_based",
        "llm_suggestion": llm_payload,
        "original_summary": summary,
        "original_errors": errors,
        "user_message": user_message,
    }
