from __future__ import annotations

import re
from typing import Any

from spatialscope.agent.schemas import AnalysisPlan, ParsedRequest, normalize_plan_steps
from spatialscope.agent.state import RunMode
from spatialscope.tools.registry import available_tool_names


GENE_PATTERN = re.compile(r"\b[A-Za-z][A-Za-z0-9_.-]{0,20}\b")
STOPWORDS = {
    "run",
    "plot",
    "do",
    "find",
    "make",
    "create",
    "generate",
    "evidence",
    "evidence-linked",
    "linked",
    "report",
    "brief",
    "finding",
    "findings",
    "show",
    "inspect",
    "assess",
    "compare",
    "summarize",
    "summarise",
    "summary",
    "structure",
    "structures",
    "caveat",
    "caveats",
    "quick",
    "standard",
    "advanced",
    "spatial",
    "spatially",
    "analysis",
    "variable",
    "variables",
    "view",
    "visual",
    "visuals",
    "views",
    "story",
    "storyboard",
    "storyboards",
    "replay",
    "replayable",
    "reproducible",
    "rerun",
    "recipe",
    "cluster",
    "clusters",
    "marker",
    "markers",
    "panel",
    "panels",
    "and",
    "the",
    "with",
    "for",
    "in",
    "of",
    "data",
    "dataset",
    "datasets",
    "transcriptomics",
    "stereo-seq",
    "stereo",
    "seq",
    "mouse",
    "embryo",
    "embryonic",
    "real",
    "this",
    "sample",
    "samples",
    "card",
    "cards",
    "qc",
    "umap",
    "leiden",
    "svg",
    "gene",
    "genes",
    "cautious",
    "candidate",
    "annotation",
    "annotations",
    "suggest",
    "suggestion",
    "suggestions",
    "label",
    "labels",
}


GENE_CONTEXT_PATTERN = re.compile(
    r"(?:for|genes?|gene panel|panel|markers?|查看|比较|表达)\s+(.+?)(?:\bthen\b|[。；;]|$)",
    flags=re.IGNORECASE,
)


def _looks_like_gene_token(token: str) -> bool:
    cleaned = token.strip(" ,.;:()[]{}，、。；：")
    if not cleaned:
        return False
    lowered = cleaned.lower()
    if len(cleaned) == 1:
        return cleaned == "T"
    if lowered in STOPWORDS:
        return False
    if re.fullmatch(r"e\d+(?:\.\d+)?", cleaned, flags=re.IGNORECASE):
        return False
    if cleaned[0].islower():
        return False
    if "-" in cleaned and lowered == cleaned:
        return False
    return True


def _candidate_gene_tokens(text: str) -> list[str]:
    return [token for token in GENE_PATTERN.findall(text) if _looks_like_gene_token(token)]


def fallback_parse_query(query: str, mode: RunMode) -> dict[str, Any]:
    lowered = query.lower()
    genes = []
    for match in GENE_CONTEXT_PATTERN.finditer(query):
        genes.extend(_candidate_gene_tokens(match.group(1)))
    genes.extend(_candidate_gene_tokens(query))
    seen: set[str] = set()
    genes = [gene for gene in genes if not (gene in seen or seen.add(gene))]
    requested_steps: list[str] = []
    if any(term in lowered for term in ["analysis", "analyze", "analyse", "overview", "explore", "探索", "检查", "比较"]):
        requested_steps.append("overview")
    if any(term in lowered for term in ["complete", "de novo", "full", "standard", "quality", "qc", "cluster", "clustering", "质量", "聚类"]):
        requested_steps.append("full_analysis")
    if any(term in lowered for term in ["plot", "show", "view", "expression", "gene panel", "表达", "查看"]) and genes:
        requested_steps.append("gene_panel")
    if any(term in lowered for term in ["svg", "spatially variable", "variable gene"]):
        requested_steps.append("svg")
    if any(term in lowered for term in ["neighborhood", "neighbourhood", "enrichment"]):
        requested_steps.append("neighborhood")
    if any(term in lowered for term in ["annotation", "annotate", "cell type", "cell-type"]):
        requested_steps.append("annotation")
    requested_steps = list(dict.fromkeys(requested_steps))
    parsed = ParsedRequest(
        intent="spatial transcriptomics exploration",
        requested_steps=requested_steps,
        genes=genes[:8],
        preferred_mode=mode,
        notes="Rule-based parser used because DeepSeek API is not configured or failed.",
        confidence=0.35,
    )
    return parsed.model_dump()


def _step(
    step_id: str,
    tool: str,
    params: dict[str, Any] | None,
    rationale: str,
    *,
    origins: dict[str, str] | None = None,
    dependencies: list[str] | None = None,
    expected: list[str] | None = None,
    preconditions: list[str] | None = None,
    optional: bool = False,
    max_attempts: int = 2,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "tool": tool,
        "params": params or {},
        "parameter_origins": origins or {key: "dataset-aware default" for key in (params or {})},
        "dependencies": dependencies or [],
        "expected_evidence": expected or [],
        "preconditions": preconditions or [],
        "scientific_purpose": rationale,
        "rationale": rationale,
        "optional": optional,
        "max_attempts": max_attempts,
    }


def make_analysis_plan(
    parsed_request: dict[str, Any],
    mode: RunMode,
    *,
    source: str = "rule_based",
    dataset_summary: dict[str, Any] | None = None,
) -> AnalysisPlan:
    genes = parsed_request.get("genes") or []
    if not genes:
        genes = ["Pou5f1", "Sox2", "Sox17", "Mesp1"]
    requested = set(map(str, parsed_request.get("requested_steps") or []))
    dataset_summary = dataset_summary or {}
    existing_obsm = set(map(str, dataset_summary.get("obsm_keys", [])))
    existing_obs = set(map(str, dataset_summary.get("obs_columns", [])))
    has_existing_embedding = "X_umap" in existing_obsm
    has_existing_clusters = bool({"leiden", "cluster", "clusters"} & existing_obs)
    wants_full = bool({"full_analysis", "qc", "cluster"} & requested) or mode in {"standard", "advanced"}
    wants_overview = "overview" in requested
    if requested and requested <= {"gene_panel"} and dataset_summary:
        wants_full = False
        wants_overview = False

    plan: list[dict[str, Any]] = [
    ]
    if wants_full or wants_overview:
        plan.extend(
            [
                _step(
                    "qc",
                    "run_qc",
                    {"min_genes": 20, "min_cells": 3, "max_mt_pct": 25},
                    "Establish basic data quality before downstream modeling.",
                    expected=["QC metrics figure", "retention summary"],
                ),
                _step(
                    "preprocess",
                    "run_preprocess",
                    {"n_top_genes": 2000},
                    "Create explicit expression lineage and modeling representation.",
                    dependencies=["qc"],
                    expected=["highly variable gene summary", "expression lineage"],
                ),
                _step(
                    "cluster",
                    "run_clustering",
                    {"resolution": 0.8},
                    "Create PCA, neighbor graph, UMAP, and Leiden clusters for exploration.",
                    dependencies=["preprocess"],
                    expected=["cluster summary table", "embedding coordinates"],
                ),
            ]
        )
    elif not has_existing_embedding and not has_existing_clusters and "gene_panel" not in requested:
        plan.append(
            _step(
                "preprocess",
                "run_preprocess",
                {"n_top_genes": 2000},
                "Prepare a safe expression representation for requested lightweight views.",
                expected=["expression lineage"],
            )
        )

    if wants_full or wants_overview or has_existing_embedding:
        plan.append(
            _step(
                "umap_plot",
                "plot_umap",
                {"color": "leiden"},
                "Check whether clusters separate in expression space.",
                dependencies=["cluster"] if wants_full or wants_overview else [],
                expected=["UMAP figure"],
            )
        )
    if wants_full or wants_overview or has_existing_clusters:
        plan.append(
            _step(
                "spatial_cluster",
                "plot_spatial",
                {"color": "leiden"},
                "Map cluster labels back to tissue coordinates.",
                dependencies=["cluster"] if wants_full or wants_overview else [],
                expected=["spatial cluster figure"],
            )
        )
    if genes or "gene_panel" in requested:
        plan.append(
            _step(
                "gene_panel",
                "plot_gene_panel",
                {"genes": genes[:6], "expression_layer": "spatialscope_interpretation"},
                "Inspect requested genes in spatial context using the interpretation layer.",
                origins={"genes": "user_query" if parsed_request.get("genes") else "dataset-aware default", "expression_layer": "agent_suggestion"},
                expected=["spatial gene panel"],
                preconditions=["valid spatial coordinates", "gene identifiers present"],
            )
        )

    if mode in {"standard", "advanced"}:
        plan.extend(
            [
                _step(
                    "markers",
                    "rank_markers",
                    {"groupby": "leiden", "top_n": 5, "expression_layer": "spatialscope_interpretation"},
                    "Rank marker genes for each Leiden cluster using the interpretation layer.",
                    dependencies=["cluster"],
                    origins={"groupby": "dataset-aware default", "top_n": "dataset-aware default", "expression_layer": "agent_suggestion"},
                    expected=["marker table", "marker heatmap"],
                ),
            ]
        )
    if "annotation" in requested:
        plan.append(
            _step(
                "cluster_annotation_suggestions",
                "suggest_cluster_annotations",
                {"groupby": "leiden", "top_n": 12, "reference": "generic_marker_lexicon"},
                "Provide cautious marker-overlap label suggestions only because annotation was explicitly requested.",
                dependencies=["markers"],
                expected=["candidate annotation table"],
                optional=True,
            )
        )

    if mode == "advanced":
        plan.extend(
            [
                _step(
                    "svg",
                    "run_svg",
                    {"mode": "moran"},
                    "Identify genes with spatial autocorrelation when Squidpy is available.",
                    dependencies=["preprocess"],
                    expected=["SVG table", "SVG figure"],
                    optional=True,
                ),
                _step(
                    "neighborhood",
                    "run_neighborhood_enrichment",
                    {"cluster_key": "leiden"},
                    "Test spatial adjacency patterns between clusters when Squidpy is available.",
                    dependencies=["cluster"],
                    expected=["neighborhood enrichment table"],
                    optional=True,
                ),
            ]
        )

    normalized = normalize_plan_steps(plan, allowed_tools=available_tool_names())
    return AnalysisPlan(
        mode=mode,
        source=source,  # type: ignore[arg-type]
        rationale=f"{mode.title()} budget with dataset-aware minimal dependencies and explicit expression lineage.",
        steps=normalized,
    )


def make_plan(parsed_request: dict[str, Any], mode: RunMode) -> list[dict[str, Any]]:
    return [step.model_dump() for step in make_analysis_plan(parsed_request, mode).steps]


def validate_plan_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return normalize_plan_steps(steps, allowed_tools=available_tool_names())


def _unique_step_id(step_id: str, seen: set[str]) -> str:
    if step_id not in seen:
        return step_id
    index = 2
    while f"{step_id}_{index}" in seen:
        index += 1
    return f"{step_id}_{index}"


def merge_with_mode_baseline(
    steps: list[dict[str, Any]],
    parsed_request: dict[str, Any],
    mode: RunMode,
) -> list[dict[str, Any]]:
    """Keep LLM choices but enforce the baseline workflow required for the selected mode."""

    proposed = validate_plan_steps(steps)
    baseline = [step.model_dump() for step in make_analysis_plan(parsed_request, mode).steps]
    used_indexes: set[int] = set()
    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for baseline_step in baseline:
        match_index = next(
            (
                index
                for index, step in enumerate(proposed)
                if index not in used_indexes and step["tool"] == baseline_step["tool"]
            ),
            None,
        )
        if match_index is None:
            step = dict(baseline_step)
            step["rationale"] = f"Baseline requirement for {mode} mode. {step.get('rationale', '')}".strip()
        else:
            step = dict(proposed[match_index])
            used_indexes.add(match_index)
        step["id"] = _unique_step_id(str(step["id"]), seen_ids)
        seen_ids.add(str(step["id"]))
        merged.append(step)

    for index, proposed_step in enumerate(proposed):
        if index in used_indexes:
            continue
        step = dict(proposed_step)
        step["id"] = _unique_step_id(str(step["id"]), seen_ids)
        seen_ids.add(str(step["id"]))
        merged.append(step)

    return validate_plan_steps(merged)
