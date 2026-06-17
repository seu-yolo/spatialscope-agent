from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from spatialscope.tools.base import ToolResult
from spatialscope.visualization.theme import (
    CLUSTER_PALETTE,
    NEUTRAL_MUTED,
    SIGNAL_TEAL,
    apply_matplotlib_theme,
    polish_axis,
    save_figure_bundle,
)


MARKER_LEXICON: dict[str, set[str]] = {
    "T cell-like": {"CD3D", "CD3E", "CD2", "TRAC", "IL7R", "CD4", "CD8A", "LTB"},
    "B cell-like": {"MS4A1", "CD79A", "CD79B", "BANK1", "CD74", "IGHM"},
    "Plasma cell-like": {"MZB1", "JCHAIN", "XBP1", "IGKC", "IGHG1", "SDC1"},
    "Myeloid-like": {"LYZ", "LST1", "S100A8", "S100A9", "FCGR3A", "C1QA", "C1QB"},
    "Endothelial-like": {"PECAM1", "VWF", "KDR", "CLDN5", "ENG", "ESAM"},
    "Fibroblast/stromal-like": {"COL1A1", "COL1A2", "COL3A1", "DCN", "LUM", "PDGFRA"},
    "Epithelial-like": {"EPCAM", "KRT8", "KRT18", "KRT19", "KRT7", "MUC1"},
    "Smooth muscle/pericyte-like": {"ACTA2", "TAGLN", "MYH11", "RGS5", "MCAM", "PDGFRB"},
    "Proliferating-like": {"MKI67", "TOP2A", "PCNA", "STMN1", "UBE2C", "HMGB2"},
    "Neuronal-like": {"SNAP25", "RBFOX3", "SYT1", "MAP2", "TUBB3", "SLC17A7"},
    "Astrocyte-like": {"GFAP", "AQP4", "ALDH1L1", "SLC1A3", "S100B"},
    "Oligodendrocyte-like": {"MBP", "MOG", "PLP1", "MAG", "OLIG1", "OLIG2"},
}


def _normalize_gene(gene: Any) -> str:
    return str(gene).strip().upper()


def _marker_frame_from_uns(adata: Any, *, groupby: str, top_n: int) -> pd.DataFrame:
    rankings = getattr(adata, "uns", {}).get("rank_genes_groups")
    if not rankings or "names" not in rankings:
        return pd.DataFrame(columns=["group", "names", "rank"])

    names = rankings["names"]
    rows: list[dict[str, Any]] = []
    if hasattr(names, "dtype") and getattr(names.dtype, "names", None):
        for group in names.dtype.names or []:
            for rank, gene in enumerate(list(names[group])[:top_n], start=1):
                rows.append({"group": str(group), "names": str(gene), "rank": rank})
    elif isinstance(names, dict):
        for group, genes in names.items():
            for rank, gene in enumerate(list(genes)[:top_n], start=1):
                rows.append({"group": str(group), "names": str(gene), "rank": rank})
    elif groupby in getattr(adata, "obs", {}):
        groups = sorted(pd.Series(adata.obs[groupby]).astype(str).unique())
        for group, genes in zip(groups, np.asarray(names).T, strict=False):
            for rank, gene in enumerate(list(genes)[:top_n], start=1):
                rows.append({"group": str(group), "names": str(gene), "rank": rank})
    return pd.DataFrame(rows)


def _extract_marker_frame(adata: Any, *, groupby: str, top_n: int) -> pd.DataFrame:
    try:
        import scanpy as sc

        marker_df = sc.get.rank_genes_groups_df(adata, group=None)
    except Exception:
        marker_df = _marker_frame_from_uns(adata, groupby=groupby, top_n=top_n)

    if marker_df.empty or "names" not in marker_df:
        return pd.DataFrame(columns=["group", "names", "rank"])
    if "group" not in marker_df:
        marker_df["group"] = "0"
    marker_df = marker_df.copy()
    marker_df["group"] = marker_df["group"].astype(str)
    marker_df["names"] = marker_df["names"].astype(str)
    if "rank" not in marker_df:
        marker_df["rank"] = marker_df.groupby("group", observed=False).cumcount() + 1
    return marker_df.groupby("group", observed=False).head(top_n).reset_index(drop=True)


def _suggest_label(genes: list[str]) -> tuple[str, float, list[str]]:
    normalized = {_normalize_gene(gene): gene for gene in genes}
    query = set(normalized)
    candidates: list[tuple[str, float, list[str]]] = []
    for label, marker_set in MARKER_LEXICON.items():
        overlap = sorted(query & marker_set)
        if not overlap:
            continue
        denominator = max(3, min(len(marker_set), max(len(query), 1)))
        confidence = min(0.92, 0.28 + 0.62 * (len(overlap) / denominator))
        evidence = [normalized[gene] for gene in overlap]
        candidates.append((label, round(confidence, 3), evidence))
    if not candidates:
        return "Unresolved", 0.0, []
    candidates.sort(key=lambda item: (item[1], len(item[2]), item[0]), reverse=True)
    return candidates[0]


def suggest_cluster_annotations(
    adata: Any,
    *,
    tables_dir: str,
    figures_dir: str,
    groupby: str = "leiden",
    top_n: int = 12,
) -> ToolResult:
    if groupby not in adata.obs:
        return ToolResult(status="failed", summary=f"Group column not found: {groupby}", errors=[groupby])

    marker_df = _extract_marker_frame(adata, groupby=groupby, top_n=top_n)
    if marker_df.empty:
        return ToolResult(
            status="skipped",
            summary="No ranked marker genes were available for cluster annotation suggestions.",
            warnings=["Run marker ranking before cluster annotation suggestion."],
        )

    rows: list[dict[str, Any]] = []
    for group, group_df in marker_df.groupby("group", observed=False, sort=True):
        genes = [str(gene) for gene in group_df["names"].head(top_n)]
        label, confidence, evidence = _suggest_label(genes)
        rows.append(
            {
                "cluster": str(group),
                "candidate_label": label,
                "confidence": confidence,
                "evidence_markers": ", ".join(evidence) if evidence else "",
                "top_markers": ", ".join(genes[: min(8, len(genes))]),
                "note": "Candidate label from a compact canonical marker lexicon; validate with domain context.",
            }
        )

    suggestions = pd.DataFrame(rows)
    table_path = Path(tables_dir) / "cluster_annotation_suggestions.csv"
    suggestions.to_csv(table_path, index=False)

    apply_matplotlib_theme()
    import matplotlib.pyplot as plt

    fig_height = max(2.6, 0.42 * len(suggestions) + 1.2)
    fig, ax = plt.subplots(figsize=(7.2, fig_height), constrained_layout=True)
    labels = [f"{row.cluster}: {row.candidate_label}" for row in suggestions.itertuples()]
    colors = [CLUSTER_PALETTE[i % len(CLUSTER_PALETTE)] for i in range(len(suggestions))]
    bars = ax.barh(labels, suggestions["confidence"], color=colors, alpha=0.9, edgecolor="white", linewidth=0.6)
    for bar, row in zip(bars, suggestions.itertuples()):
        value = float(row.confidence)
        ax.text(
            min(value + 0.02, 0.98),
            bar.get_y() + bar.get_height() / 2,
            f"{value:.2f}",
            ha="left" if value < 0.9 else "right",
            va="center",
            fontsize=7,
            color=SIGNAL_TEAL if value > 0 else NEUTRAL_MUTED,
        )
    ax.set_xlim(0, 1)
    ax.set_xlabel("Marker-overlap confidence")
    polish_axis(ax, title="Candidate Cluster Annotation Suggestions", subtitle="exploratory, marker-overlap based")
    ax.invert_yaxis()
    fig_path = Path(figures_dir) / "cluster_annotation_suggestions.png"
    saved = save_figure_bundle(fig, fig_path)
    plt.close(fig)

    compact = "; ".join(f"{row.cluster}:{row.candidate_label}" for row in suggestions.itertuples())
    warnings = []
    if (suggestions["candidate_label"] == "Unresolved").any():
        warnings.append("Some clusters had no overlap with the compact canonical marker lexicon.")
    return ToolResult(
        status="success",
        summary=f"Generated candidate cluster annotation suggestions for {len(suggestions)} clusters ({compact}).",
        figures=[
            {
                **saved,
                "title": "Candidate Cluster Annotation Suggestions",
                "caption": "Exploratory labels scored by overlap between top ranked marker genes and a compact canonical marker lexicon.",
            }
        ],
        tables=[{"path": str(table_path), "title": "Cluster annotation suggestions"}],
        observations={"cluster_annotation_suggestions": suggestions.to_dict(orient="records")},
        warnings=warnings,
    )
