from __future__ import annotations

import re
from typing import Any

from spatialscope.agent.schemas import AnalysisPlan, ParsedRequest, normalize_plan_steps
from spatialscope.agent.state import RunMode
from spatialscope.tools.registry import available_tool_names


GENE_PATTERN = re.compile(r"\b[A-Za-z][A-Za-z0-9_.-]{1,20}\b")
STOPWORDS = {
    "run",
    "plot",
    "do",
    "find",
    "quick",
    "standard",
    "advanced",
    "spatial",
    "spatially",
    "analysis",
    "variable",
    "variables",
    "view",
    "views",
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
    "qc",
    "umap",
    "leiden",
    "svg",
    "gene",
    "genes",
}


def fallback_parse_query(query: str, mode: RunMode) -> dict[str, Any]:
    genes = []
    for token in GENE_PATTERN.findall(query):
        if token.lower() not in STOPWORDS:
            genes.append(token)
    seen: set[str] = set()
    genes = [gene for gene in genes if not (gene in seen or seen.add(gene))]
    parsed = ParsedRequest(
        intent="spatial transcriptomics exploration",
        requested_steps=[],
        genes=genes[:8],
        preferred_mode=mode,
        notes="Rule-based parser used because DeepSeek API is not configured or failed.",
        confidence=0.35,
    )
    return parsed.model_dump()


def make_analysis_plan(parsed_request: dict[str, Any], mode: RunMode, *, source: str = "rule_based") -> AnalysisPlan:
    genes = parsed_request.get("genes") or []
    if not genes:
        genes = ["GeneA", "GeneB", "GeneC"]

    plan: list[dict[str, Any]] = [
        {
            "id": "qc",
            "tool": "run_qc",
            "params": {"min_genes": 20, "min_cells": 3, "max_mt_pct": 25},
            "rationale": "Establish basic data quality before downstream modeling.",
        },
        {
            "id": "preprocess",
            "tool": "run_preprocess",
            "params": {"n_top_genes": 2000},
            "rationale": "Normalize and prepare the expression matrix for embedding and clustering.",
        },
        {
            "id": "cluster",
            "tool": "run_clustering",
            "params": {"resolution": 0.8},
            "rationale": "Create a low-dimensional embedding and cluster structure for exploration.",
        },
        {
            "id": "umap_plot",
            "tool": "plot_umap",
            "params": {"color": "leiden"},
            "rationale": "Check whether clusters separate in expression space.",
        },
        {
            "id": "spatial_cluster",
            "tool": "plot_spatial",
            "params": {"color": "leiden"},
            "rationale": "Map cluster labels back to tissue coordinates.",
        },
        {
            "id": "gene_panel",
            "tool": "plot_gene_panel",
            "params": {"genes": genes[:6]},
            "rationale": "Inspect requested or default genes in spatial context.",
        },
    ]

    if mode in {"standard", "advanced"}:
        plan.extend(
            [
                {
                    "id": "markers",
                    "tool": "rank_markers",
                    "params": {"groupby": "leiden"},
                    "rationale": "Rank candidate marker genes for each Leiden cluster.",
                },
            ]
        )

    if mode == "advanced":
        plan.extend(
            [
                {
                    "id": "svg",
                    "tool": "run_svg",
                    "params": {"mode": "moran"},
                    "rationale": "Identify genes with spatial autocorrelation when Squidpy is available.",
                    "optional": True,
                },
                {
                    "id": "neighborhood",
                    "tool": "run_neighborhood_enrichment",
                    "params": {"cluster_key": "leiden"},
                    "rationale": "Test spatial adjacency patterns between clusters when Squidpy is available.",
                    "optional": True,
                },
            ]
        )

    normalized = normalize_plan_steps(plan, allowed_tools=available_tool_names())
    return AnalysisPlan(
        mode=mode,
        source=source,  # type: ignore[arg-type]
        rationale=f"{mode.title()} mode balances runtime, visual evidence, and reproducible outputs.",
        steps=normalized,
    )


def make_plan(parsed_request: dict[str, Any], mode: RunMode) -> list[dict[str, Any]]:
    return [step.model_dump() for step in make_analysis_plan(parsed_request, mode).steps]


def validate_plan_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return normalize_plan_steps(steps, allowed_tools=available_tool_names())
