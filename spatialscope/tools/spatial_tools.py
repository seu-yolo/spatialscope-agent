from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from spatialscope.tools.base import ToolResult
from spatialscope.utils.gene_matching import match_gene_name
from spatialscope.visualization.theme import CLUSTER_PALETTE, EXPRESSION_CMAP, apply_matplotlib_theme


def _dense_vector(values: Any) -> np.ndarray:
    if hasattr(values, "toarray"):
        values = values.toarray()
    arr = np.asarray(values)
    return np.ravel(arr)


def _gene_vector(adata: Any, gene: str) -> np.ndarray:
    idx = list(adata.var_names).index(gene)
    return _dense_vector(adata.X[:, idx])


def plot_umap(adata: Any, *, figures_dir: str, color: str = "leiden") -> ToolResult:
    if "X_umap" not in adata.obsm:
        return ToolResult(status="failed", summary="UMAP coordinates not found.", errors=["missing obsm['X_umap']"])
    if color not in adata.obs:
        return ToolResult(status="failed", summary=f"Observation column not found: {color}", errors=[color])

    apply_matplotlib_theme()
    import matplotlib.pyplot as plt

    coords = np.asarray(adata.obsm["X_umap"])
    labels = adata.obs[color].astype(str)
    categories = sorted(labels.unique())
    color_map = {cat: CLUSTER_PALETTE[i % len(CLUSTER_PALETTE)] for i, cat in enumerate(categories)}

    fig, ax = plt.subplots(figsize=(5, 4))
    for cat in categories:
        mask = labels == cat
        ax.scatter(coords[mask, 0], coords[mask, 1], s=8, color=color_map[cat], label=cat, alpha=0.85)
    ax.set_title(f"UMAP colored by {color}")
    ax.set_xlabel("UMAP1")
    ax.set_ylabel("UMAP2")
    ax.legend(title=color, bbox_to_anchor=(1.02, 1), loc="upper left", markerscale=2)
    fig.tight_layout()
    path = Path(figures_dir) / f"umap_{color}.png"
    fig.savefig(path, bbox_inches="tight", dpi=300)
    plt.close(fig)
    return ToolResult(
        status="success",
        summary=f"Generated UMAP plot colored by {color}.",
        figures=[
            {
                "path": str(path),
                "title": f"UMAP colored by {color}",
                "caption": f"UMAP embedding colored by `{color}`. Cluster colors are reused in spatial views.",
            }
        ],
    )


def plot_spatial(adata: Any, *, figures_dir: str, color: str = "leiden") -> ToolResult:
    if "spatial" not in adata.obsm:
        return ToolResult(
            status="failed",
            summary="Spatial coordinates not found; skipping spatial plot.",
            warnings=["missing obsm['spatial']"],
        )
    if color not in adata.obs and color not in adata.var_names:
        return ToolResult(status="failed", summary=f"Color key not found: {color}", errors=[color])

    apply_matplotlib_theme()
    import matplotlib.pyplot as plt

    coords = np.asarray(adata.obsm["spatial"])
    fig, ax = plt.subplots(figsize=(5, 5))
    point_size = max(3, min(24, 12000 / max(adata.n_obs, 1)))
    if color in adata.obs:
        labels = adata.obs[color].astype(str)
        categories = sorted(labels.unique())
        color_map = {cat: CLUSTER_PALETTE[i % len(CLUSTER_PALETTE)] for i, cat in enumerate(categories)}
        for cat in categories:
            mask = labels == cat
            ax.scatter(coords[mask, 0], coords[mask, 1], s=point_size, color=color_map[cat], label=cat, alpha=0.9)
        ax.legend(title=color, bbox_to_anchor=(1.02, 1), loc="upper left", markerscale=1.8)
        caption = f"Spatial distribution colored by `{color}` using coordinates from `adata.obsm['spatial']`."
    else:
        values = _gene_vector(adata, color)
        lo, hi = np.nanpercentile(values, [1, 99])
        clipped = np.clip(values, lo, hi)
        sc = ax.scatter(coords[:, 0], coords[:, 1], s=point_size, c=clipped, cmap=EXPRESSION_CMAP, alpha=0.9)
        fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04, label=color)
        caption = f"Spatial expression of `{color}` with 1-99 percentile clipping."
    ax.set_aspect("equal")
    ax.set_title(f"Spatial view: {color}")
    ax.set_xticks([])
    ax.set_yticks([])
    fig.tight_layout()
    path = Path(figures_dir) / f"spatial_{color}.png"
    fig.savefig(path, bbox_inches="tight", dpi=300)
    plt.close(fig)
    return ToolResult(
        status="success",
        summary=f"Generated spatial plot for {color}.",
        figures=[{"path": str(path), "title": f"Spatial view: {color}", "caption": caption}],
    )


def plot_gene_panel(adata: Any, *, figures_dir: str, genes: list[str]) -> ToolResult:
    if "spatial" not in adata.obsm:
        return ToolResult(status="failed", summary="Spatial coordinates not found.", warnings=["missing obsm['spatial']"])
    if not genes:
        return ToolResult(status="skipped", summary="No genes requested for gene panel.")

    apply_matplotlib_theme()
    import matplotlib.pyplot as plt

    var_names = list(map(str, adata.var_names))
    resolved: list[str] = []
    warnings: list[str] = []
    for gene in genes:
        match = match_gene_name(gene, var_names)
        if match["match"] is None:
            warnings.append(f"No match found for gene `{gene}`.")
            continue
        if match["match"] != gene:
            warnings.append(f"Gene `{gene}` matched to `{match['match']}` (score={match['score']}).")
        resolved.append(str(match["match"]))

    if not resolved:
        return ToolResult(status="failed", summary="No requested genes could be matched.", warnings=warnings)

    coords = np.asarray(adata.obsm["spatial"])
    n = len(resolved)
    fig, axes = plt.subplots(1, n, figsize=(4 * n, 4), squeeze=False)
    point_size = max(3, min(22, 12000 / max(adata.n_obs, 1)))
    for ax, gene in zip(axes.ravel(), resolved):
        values = _gene_vector(adata, gene)
        lo, hi = np.nanpercentile(values, [1, 99])
        clipped = np.clip(values, lo, hi)
        sc = ax.scatter(coords[:, 0], coords[:, 1], c=clipped, cmap=EXPRESSION_CMAP, s=point_size, alpha=0.9)
        ax.set_title(gene)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        fig.colorbar(sc, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle("Gene Panel Spatial View")
    fig.tight_layout()
    path = Path(figures_dir) / "gene_panel_spatial.png"
    fig.savefig(path, bbox_inches="tight", dpi=300)
    plt.close(fig)
    return ToolResult(
        status="success",
        summary=f"Generated gene panel for {', '.join(resolved)}.",
        figures=[
            {
                "path": str(path),
                "title": "Gene Panel Spatial View",
                "caption": "Small-multiple spatial expression plots using shared spatial coordinates and percentile-clipped expression.",
            }
        ],
        observations={"requested_genes": genes, "resolved_genes": resolved},
        warnings=warnings,
    )

