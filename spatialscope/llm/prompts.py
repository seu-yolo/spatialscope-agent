from __future__ import annotations

import json
from typing import Any


SYSTEM_PROMPT = """You are SpatialScope Agent, a careful spatial transcriptomics analysis assistant.
You are useful only when you stay grounded in the provided evidence packs.
Rules:
1. Never ask for or use full expression matrices or raw spatial coordinate arrays.
2. Never invent genes, cell types, p-values, mechanisms, or biological certainty.
3. Cite exact evidence IDs for every substantive claim.
4. If the evidence is insufficient, say what is missing and keep the answer bounded.
5. Return valid JSON whenever a schema is provided.
"""


def _schema_text(schema: dict[str, Any]) -> str:
    return json.dumps(schema, ensure_ascii=False)


def research_brief_prompt(*, schema: dict[str, Any], query: str, mode: str, dataset_profile: dict[str, Any]) -> str:
    return (
        "Parse the user request after inspecting the dataset profile. Return one ResearchBrief JSON object. "
        "Only include genes explicitly requested by the user. Identify ambiguities that need user clarification, "
        "especially misspelled genes, missing spatial coordinates, and unsafe expression layers.\n"
        f"Schema: {_schema_text(schema)}\n"
        f"Mode: {mode}\n"
        f"Dataset profile: {json.dumps(dataset_profile, ensure_ascii=False)[:3600]}\n"
        f"User request: {query}"
    )


def plan_prompt(
    *,
    schema: dict[str, Any],
    research_brief: str,
    mode: str,
    dataset_profile: dict[str, Any],
    tool_contracts: list[dict[str, Any]],
) -> str:
    return (
        "Generate a dependency-valid SpatialScope analysis plan as V2AnalysisPlan JSON. "
        "A gene-only request should produce a lightweight gene-focused plan when the dataset already supports it; "
        "a full-analysis request should include QC, preprocessing, clustering, linked spatial/UMAP review, markers, "
        "and report synthesis. Respect explicit genes and do not add annotation unless requested.\n"
        f"Schema: {_schema_text(schema)}\n"
        f"Requested mode: {mode}\n"
        f"Research brief: {research_brief}\n"
        f"Dataset profile: {json.dumps(dataset_profile, ensure_ascii=False)[:3600]}\n"
        f"Tool contracts: {json.dumps(tool_contracts, ensure_ascii=False)[:6000]}"
    )


def repair_prompt(
    *,
    schema: dict[str, Any],
    failed_step: dict[str, Any],
    tool_result: dict[str, Any],
    tool_contract: dict[str, Any],
    dataset_profile: dict[str, Any],
) -> str:
    return (
        "Suggest one bounded repair decision as RepairDecision JSON. Prefer retry_with_patch only when the repair is "
        "a safe parameter change derived from tool output, such as a fuzzy gene match or existing cluster column. "
        "Use ask_user when a choice cannot be resolved safely. Do not request raw matrices.\n"
        f"Schema: {_schema_text(schema)}\n"
        f"Failed step: {json.dumps(failed_step, ensure_ascii=False)}\n"
        f"Tool result: {json.dumps(tool_result, ensure_ascii=False)[:2800]}\n"
        f"Tool contract: {json.dumps(tool_contract, ensure_ascii=False)[:2600]}\n"
        f"Dataset profile: {json.dumps(dataset_profile, ensure_ascii=False)[:2600]}"
    )


def findings_prompt(
    *,
    schema: dict[str, Any],
    query: str,
    dataset_profile: dict[str, Any],
    evidence_packs: list[dict[str, Any]],
    warnings: list[str],
) -> str:
    return (
        "Synthesize 3 to 5 ScientificFinding objects from evidence packs. Each finding must answer the research "
        "question, cite exact evidence_ids, include quantitative support when available, and include caveats. "
        "Do not create findings from absent evidence. Do not claim cell identity or mechanisms unless directly supported.\n"
        f"Schema: {_schema_text(schema)}\n"
        f"Question: {query}\n"
        f"Dataset profile: {json.dumps(dataset_profile, ensure_ascii=False)[:2600]}\n"
        f"Evidence packs: {json.dumps(evidence_packs, ensure_ascii=False)[:8500]}\n"
        f"Warnings: {json.dumps(warnings, ensure_ascii=False)[:1800]}"
    )


def interpretation_prompt(
    *,
    schema: dict[str, Any],
    query: str,
    dataset_profile: dict[str, Any],
    findings: list[dict[str, Any]],
    warnings: list[str],
) -> str:
    return (
        "Write a concise final research brief as JSON. Start from the user's question, summarize only the provided "
        "scientific findings, and keep caveats visible. Do not invent new facts beyond the findings.\n"
        f"Schema: {_schema_text(schema)}\n"
        f"Question: {query}\n"
        f"Dataset profile: {json.dumps(dataset_profile, ensure_ascii=False)[:2200]}\n"
        f"Findings: {json.dumps(findings, ensure_ascii=False)[:7000]}\n"
        f"Warnings: {json.dumps(warnings, ensure_ascii=False)[:1600]}"
    )


def contextual_copilot_prompt(
    *,
    schema: dict[str, Any],
    question: str,
    conversation_memory: list[dict[str, Any]],
    selected_context: dict[str, Any],
    focus: str,
) -> str:
    return (
        "Answer the user's current question about selected SpatialScope evidence as JSON. The answer must be "
        "question-specific, concise, and grounded in the selected evidence packs. Do not start with a generic preamble. "
        "Always return the exact evidence_ids used. If selected evidence cannot answer the question, explain that boundary.\n"
        "Do not invent tool names or recommend tools that are not present in the selected context; write next_step as a plain user action.\n"
        f"Schema: {_schema_text(schema)}\n"
        f"Question focus: {focus}\n"
        f"Current question: {question}\n"
        f"Recent conversation memory: {json.dumps(conversation_memory[-6:], ensure_ascii=False)[:2200]}\n"
        f"Selected evidence context: {json.dumps(selected_context, ensure_ascii=False)[:8500]}"
    )
