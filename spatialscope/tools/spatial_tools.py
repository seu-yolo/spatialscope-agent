from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from spatialscope.domain.expression_lineage import infer_matrix_state
from spatialscope.tools.base import ToolResult
from spatialscope.utils.gene_matching import match_gene_name
from spatialscope.visualization.theme import (
    CLUSTER_PALETTE,
    EXPRESSION_CMAP,
    NEUTRAL_MUTED,
    apply_matplotlib_theme,
    numeric_sort_key,
    polish_axis,
    save_figure_bundle,
)


def _dense_vector(values: Any) -> np.ndarray:
    if hasattr(values, "toarray"):
        values = values.toarray()
    arr = np.asarray(values)
    return np.ravel(arr)


def _gene_vector(adata: Any, gene: str, *, expression_layer: str | None = None) -> np.ndarray:
    idx = list(adata.var_names).index(gene)
    if expression_layer and expression_layer not in {"X", "raw"} and expression_layer in getattr(adata, "layers", {}):
        return _dense_vector(adata.layers[expression_layer][:, idx])
    if expression_layer == "raw" and getattr(adata, "raw", None) is not None:
        return _dense_vector(adata.raw[:, gene].X)
    return _dense_vector(adata.X[:, idx])


def _safe_expression_layer(adata: Any, requested: str) -> tuple[str | None, str | None]:
    layers = getattr(adata, "layers", {})
    if requested in layers:
        return requested, None
    if requested == "raw" and getattr(adata, "raw", None) is not None:
        return "raw", None
    if requested == "X":
        assessment = infer_matrix_state(adata.X)
        if assessment.state in {"count_like", "log_normalized"}:
            return "X", None
    assessment = infer_matrix_state(adata.X)
    if assessment.state in {"count_like", "log_normalized"}:
        return "X", None
    lineage = getattr(adata, "uns", {}).get("spatialscope_expression_lineage", {})
    recommended = lineage.get("recommended_interpretation_layer")
    return None, (
        f"No safe expression source is available for `{requested}`. "
        f"Recommended source recorded by expression lineage: `{recommended or 'unavailable'}`."
    )


def plot_umap(adata: Any, *, figures_dir: str, color: str = "leiden") -> ToolResult:
    if "X_umap" not in adata.obsm:
        return ToolResult(status="failed", summary="UMAP coordinates not found.", errors=["missing obsm['X_umap']"])
    if color not in adata.obs:
        return ToolResult(status="failed", summary=f"Observation column not found: {color}", errors=[color])

    apply_matplotlib_theme()
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    coords = np.asarray(adata.obsm["X_umap"])
    labels = adata.obs[color].astype(str)
    categories = sorted(labels.unique(), key=numeric_sort_key)
    color_map = {cat: CLUSTER_PALETTE[i % len(CLUSTER_PALETTE)] for i, cat in enumerate(categories)}
    adata.uns.setdefault("spatialscope_cluster_palette", {})[color] = color_map

    fig = plt.figure(figsize=(6.7, 4.1), constrained_layout=True)
    gs = fig.add_gridspec(1, 2, width_ratios=[4.7, 1.2])
    ax = fig.add_subplot(gs[0, 0])
    ax_leg = fig.add_subplot(gs[0, 1])
    for cat in categories:
        mask = labels == cat
        ax.scatter(coords[mask, 0], coords[mask, 1], s=9, color=color_map[cat], label=cat, alpha=0.88, linewidths=0)
    polish_axis(ax, title=f"UMAP by {color}", subtitle=f"{adata.n_obs:,} observations; {len(categories)} groups")
    ax.set_xlabel("UMAP1")
    ax.set_ylabel("UMAP2")
    ax_leg.set_axis_off()
    handles = [
        Line2D([0], [0], marker="o", linestyle="", color=color_map[cat], label=str(cat), markersize=5)
        for cat in categories
    ]
    ax_leg.legend(handles=handles, labels=[str(cat) for cat in categories], title=color, loc="center left")
    path = Path(figures_dir) / f"umap_{color}.png"
    saved = save_figure_bundle(fig, path)
    plt.close(fig)
    return ToolResult(
        status="success",
        summary=f"Generated UMAP plot colored by {color}.",
        figures=[
            {
                **saved,
                "title": f"UMAP colored by {color}",
                "caption": f"UMAP embedding colored by `{color}`. Cluster colors are reused in spatial views.",
            }
        ],
        observations={"groupby": color, "cluster_palette": color_map, "n_clusters": int(len(categories))},
    )


def plot_spatial(
    adata: Any,
    *,
    figures_dir: str,
    color: str = "leiden",
    expression_layer: str = "spatialscope_interpretation",
    clip_percentiles: tuple[float, float] = (1, 99),
) -> ToolResult:
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
    from matplotlib.lines import Line2D

    coords = np.asarray(adata.obsm["spatial"])
    x_range = float(np.nanmax(coords[:, 0]) - np.nanmin(coords[:, 0])) if len(coords) else 1.0
    y_range = float(np.nanmax(coords[:, 1]) - np.nanmin(coords[:, 1])) if len(coords) else 1.0
    spatial_ratio = x_range / max(y_range, 1e-6)
    fig_height = max(3.1, min(5.0, 4.8 / max(spatial_ratio, 0.9) + 0.85))
    fig = plt.figure(figsize=(6.2, fig_height), constrained_layout=True)
    gs = fig.add_gridspec(1, 2, width_ratios=[4.8, 1.2])
    ax = fig.add_subplot(gs[0, 0])
    ax_leg = fig.add_subplot(gs[0, 1])
    point_size = max(3, min(24, 12000 / max(adata.n_obs, 1)))
    if color in adata.obs:
        labels = adata.obs[color].astype(str)
        categories = sorted(labels.unique(), key=numeric_sort_key)
        color_map = {cat: CLUSTER_PALETTE[i % len(CLUSTER_PALETTE)] for i, cat in enumerate(categories)}
        adata.uns.setdefault("spatialscope_cluster_palette", {})[color] = color_map
        for cat in categories:
            mask = labels == cat
            ax.scatter(coords[mask, 0], coords[mask, 1], s=point_size, color=color_map[cat], label=cat, alpha=0.9, linewidths=0)
        ax_leg.set_axis_off()
        handles = [
            Line2D([0], [0], marker="o", linestyle="", color=color_map[cat], label=str(cat), markersize=5)
            for cat in categories
        ]
        ax_leg.legend(handles=handles, labels=[str(cat) for cat in categories], title=color, loc="center left")
        caption = f"Spatial distribution colored by `{color}` using coordinates from `adata.obsm['spatial']`."
    else:
        layer, layer_error = _safe_expression_layer(adata, expression_layer)
        if layer_error:
            return ToolResult(status="failed", summary=layer_error, errors=[layer_error])
        values = _gene_vector(adata, color, expression_layer=layer)
        lo, hi = np.nanpercentile(values, clip_percentiles)
        clipped = np.clip(values, lo, hi)
        sc = ax.scatter(coords[:, 0], coords[:, 1], s=point_size, c=clipped, cmap=EXPRESSION_CMAP, alpha=0.92, linewidths=0)
        ax_leg.set_axis_off()
        cbar = fig.colorbar(sc, ax=ax_leg, fraction=0.9, pad=0.08)
        cbar.set_label(color)
        caption = (
            f"Spatial expression of `{color}` using layer `{layer}`, coordinates `adata.obsm['spatial']`, "
            f"and {clip_percentiles[0]}-{clip_percentiles[1]} percentile clipping."
        )
    ax.set_aspect("equal")
    polish_axis(ax, title=f"Spatial view: {color}", subtitle=f"{adata.n_obs:,} spots/cells")
    ax.set_xticks([])
    ax.set_yticks([])
    path = Path(figures_dir) / f"spatial_{color}.png"
    saved = save_figure_bundle(fig, path)
    plt.close(fig)
    return ToolResult(
        status="success",
        summary=f"Generated spatial plot for {color}.",
        figures=[{**saved, "title": f"Spatial view: {color}", "caption": caption, "data_layer": expression_layer}],
        observations={
            "expression_layer": expression_layer,
            "clip_percentiles": list(clip_percentiles),
            "groupby": color if color in adata.obs else "",
            "cluster_palette": color_map if color in adata.obs else {},
        },
    )


def plot_gene_panel(
    adata: Any,
    *,
    figures_dir: str,
    genes: list[str],
    expression_layer: str = "spatialscope_interpretation",
    clip_percentiles: tuple[float, float] = (1, 99),
) -> ToolResult:
    if "spatial" not in adata.obsm:
        return ToolResult(status="failed", summary="Spatial coordinates not found.", warnings=["missing obsm['spatial']"])
    if not genes:
        return ToolResult(status="skipped", summary="No genes requested for gene panel.")

    apply_matplotlib_theme()
    import matplotlib.pyplot as plt

    var_names = list(map(str, adata.var_names))
    resolved: list[str] = []
    warnings: list[str] = []
    suggestions: dict[str, list[str]] = {}
    for gene in genes:
        match = match_gene_name(gene, var_names)
        if match["match"] is None:
            warnings.append(f"No match found for gene `{gene}`.")
            suggestions[gene] = list(map(str, match.get("candidates", []) or []))
            continue
        if match["match"] != gene:
            warnings.append(f"Gene `{gene}` needs confirmation; closest match is `{match['match']}` (score={match['score']}).")
            suggestions[gene] = list(map(str, match.get("candidates", []) or []))
            continue
        resolved.append(str(match["match"]))

    if suggestions:
        best_patch = [*resolved, *[items[0] for items in suggestions.values() if items]]
        return ToolResult(
            status="failed",
            summary="One or more requested genes need clarification before expression plotting.",
            errors=["unmatched_genes"],
            warnings=warnings,
            observations={"gene_suggestions": suggestions, "suggested_genes": best_patch},
        )

    coords = np.asarray(adata.obsm["spatial"])
    layer, layer_error = _safe_expression_layer(adata, expression_layer)
    if layer_error:
        return ToolResult(
            status="failed",
            summary=layer_error,
            errors=["unsafe_expression_source"],
            observations={"requested_genes": genes, "resolved_genes": resolved, "expression_layer": expression_layer},
        )
    n = len(resolved)
    ncols = min(3, n)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(3.4 * ncols, 3.35 * nrows), squeeze=False, constrained_layout=True)
    point_size = max(3, min(22, 12000 / max(adata.n_obs, 1)))
    labels = adata.obs["leiden"].astype(str) if "leiden" in adata.obs else None
    gene_summaries: list[dict[str, Any]] = []
    for ax, gene in zip(axes.ravel(), resolved):
        values = _gene_vector(adata, gene, expression_layer=layer)
        lo, hi = np.nanpercentile(values, clip_percentiles)
        clipped = np.clip(values, lo, hi)
        finite = values[np.isfinite(values)]
        summary: dict[str, Any] = {
            "gene": gene,
            "mean": round(float(np.mean(finite)), 4) if len(finite) else None,
            "median": round(float(np.median(finite)), 4) if len(finite) else None,
            "nonzero_fraction": round(float(np.mean(values > 0)), 4) if len(values) else None,
            "p95": round(float(np.percentile(finite, 95)), 4) if len(finite) else None,
        }
        if labels is not None:
            cluster_means = {
                str(cluster): round(float(np.mean(values[np.asarray(labels == cluster)])), 4)
                for cluster in sorted(labels.unique(), key=numeric_sort_key)
                if np.asarray(labels == cluster).sum() > 0
            }
            if cluster_means:
                summary["top_cluster_by_mean"] = max(cluster_means, key=cluster_means.get)
                summary["cluster_means"] = cluster_means
        gene_summaries.append(summary)
        sc = ax.scatter(coords[:, 0], coords[:, 1], c=clipped, cmap=EXPRESSION_CMAP, s=point_size, alpha=0.92, linewidths=0)
        polish_axis(ax, title=gene, subtitle=f"{layer}; {lo:.2g}-{hi:.2g} clipped")
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        cbar = fig.colorbar(sc, ax=ax, fraction=0.045, pad=0.02)
        cbar.ax.tick_params(labelsize=6.5, colors=NEUTRAL_MUTED)
    for ax in axes.ravel()[n:]:
        ax.set_axis_off()
    fig.suptitle("Gene Panel Spatial View", x=0.01, ha="left", fontsize=11, fontweight="bold")
    path = Path(figures_dir) / "gene_panel_spatial.png"
    saved = save_figure_bundle(fig, path)
    plt.close(fig)
    return ToolResult(
        status="success",
        summary=f"Generated gene panel for {', '.join(resolved)}.",
        figures=[
            {
                **saved,
                "title": "Gene Panel Spatial View",
                "caption": (
                    "Small-multiple spatial expression plots using shared spatial coordinates, "
                    f"layer `{layer}`, and {clip_percentiles[0]}-{clip_percentiles[1]} percentile clipping."
                ),
                "data_layer": layer,
            }
        ],
        observations={
            "requested_genes": genes,
            "resolved_genes": resolved,
            "expression_layer": layer,
            "clip_percentiles": list(clip_percentiles),
            "gene_expression_summary": gene_summaries,
        },
        warnings=warnings,
    )
