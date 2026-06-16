from __future__ import annotations

import re
from typing import Any

from spatialscope.agent.state import RunMode


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
    return {
        "intent": "spatial transcriptomics exploration",
        "requested_steps": [],
        "genes": genes[:8],
        "preferred_mode": mode,
        "notes": "Rule-based parser used because DeepSeek API is not configured or failed.",
    }


def make_plan(parsed_request: dict[str, Any], mode: RunMode) -> list[dict[str, Any]]:
    genes = parsed_request.get("genes") or []
    if not genes:
        genes = ["GeneA", "GeneB", "GeneC"]

    plan: list[dict[str, Any]] = [
        {"id": "qc", "tool": "run_qc", "params": {"min_genes": 20, "min_cells": 3, "max_mt_pct": 25}},
        {"id": "preprocess", "tool": "run_preprocess", "params": {"n_top_genes": 2000}},
        {"id": "cluster", "tool": "run_clustering", "params": {"resolution": 0.8}},
        {"id": "umap_plot", "tool": "plot_umap", "params": {"color": "leiden"}},
        {"id": "spatial_cluster", "tool": "plot_spatial", "params": {"color": "leiden"}},
        {"id": "gene_panel", "tool": "plot_gene_panel", "params": {"genes": genes[:6]}},
    ]

    if mode in {"standard", "advanced"}:
        plan.extend(
            [
                {"id": "markers", "tool": "rank_markers", "params": {"groupby": "leiden"}},
            ]
        )

    if mode == "advanced":
        plan.extend(
            [
                {"id": "svg", "tool": "run_svg", "params": {"mode": "moran"}},
                {"id": "neighborhood", "tool": "run_neighborhood_enrichment", "params": {"cluster_key": "leiden"}},
            ]
        )

    return plan
