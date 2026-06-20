from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from spatialscope.domain.expression_lineage import infer_matrix_state
from spatialscope.tools.base import ToolResult, missing_dependency
from spatialscope.visualization.theme import EXPRESSION_CMAP, NEUTRAL_MUTED, apply_matplotlib_theme, numeric_sort_key, polish_axis, save_figure_bundle


def _dense_matrix(values: Any) -> np.ndarray:
    if hasattr(values, "toarray"):
        values = values.toarray()
    return np.asarray(values)


def _safe_expression_layer(adata: Any, requested: str) -> tuple[str | None, str | None]:
    if requested in getattr(adata, "layers", {}):
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
        f"No safe expression source is available for marker ranking with `{requested}`. "
        f"Recommended source recorded by expression lineage: `{recommended or 'unavailable'}`."
    )


def _marker_heatmap(
    adata: Any,
    marker_df: pd.DataFrame,
    *,
    groupby: str,
    figures_dir: str,
    top_n: int,
    expression_layer: str,
) -> dict[str, Any] | None:
    top = marker_df.groupby("group", observed=False).head(top_n)
    genes = [str(gene) for gene in top["names"] if str(gene) in set(map(str, adata.var_names))]
    genes = list(dict.fromkeys(genes))[:32]
    if not genes:
        return None

    labels = pd.Series(adata.obs[groupby]).astype(str)
    clusters = sorted(labels.unique(), key=numeric_sort_key)
    var_names = list(map(str, adata.var_names))
    gene_indices = [var_names.index(gene) for gene in genes]
    matrix_source = adata.layers[expression_layer] if expression_layer in getattr(adata, "layers", {}) else adata.X
    x = _dense_matrix(matrix_source[:, gene_indices])

    mean_by_cluster = []
    for cluster in clusters:
        mask = np.asarray(labels == cluster)
        if mask.sum() == 0:
            mean_by_cluster.append(np.zeros(len(genes)))
        else:
            mean_by_cluster.append(np.asarray(x[mask]).mean(axis=0))
    matrix = np.vstack(mean_by_cluster)
    gene_mean = matrix.mean(axis=0, keepdims=True)
    gene_std = matrix.std(axis=0, keepdims=True)
    z = (matrix - gene_mean) / np.where(gene_std == 0, 1, gene_std)
    z = np.clip(z, -2.5, 2.5)

    apply_matplotlib_theme()
    import matplotlib.pyplot as plt

    width = max(6.2, min(11.5, 0.32 * len(genes) + 2.4))
    height = max(3.2, 0.34 * len(clusters) + 1.8)
    fig, ax = plt.subplots(figsize=(width, height), constrained_layout=True)
    im = ax.imshow(z, aspect="auto", cmap=EXPRESSION_CMAP, vmin=-2.5, vmax=2.5)
    ax.set_xticks(range(len(genes)))
    ax.set_xticklabels(genes, rotation=60, ha="right")
    ax.set_yticks(range(len(clusters)))
    ax.set_yticklabels([f"Cluster {cluster}" for cluster in clusters])
    polish_axis(ax, title="Top Marker Expression Heatmap", subtitle=f"z-scored mean expression by cluster; layer={expression_layer}")
    cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("relative expression")
    cbar.ax.tick_params(labelsize=6.5, colors=NEUTRAL_MUTED)
    fig_path = Path(figures_dir) / "marker_expression_heatmap.png"
    saved = save_figure_bundle(fig, fig_path)
    plt.close(fig)
    return {
        **saved,
        "title": "Top Marker Expression Heatmap",
        "caption": f"Cluster-level mean expression of top ranked marker genes from layer `{expression_layer}`, z-scored per gene for visual comparison.",
        "data_layer": expression_layer,
    }


def rank_markers(
    adata: Any,
    *,
    tables_dir: str,
    figures_dir: str,
    groupby: str = "leiden",
    top_n: int = 5,
    expression_layer: str = "spatialscope_interpretation",
) -> ToolResult:
    if groupby not in adata.obs:
        return ToolResult(status="failed", summary=f"Group column not found: {groupby}", errors=[groupby])
    try:
        import scanpy as sc
    except Exception as exc:
        raise missing_dependency("scanpy", "marker gene ranking") from exc

    layer, layer_error = _safe_expression_layer(adata, expression_layer)
    if layer_error:
        return ToolResult(status="failed", summary=layer_error, errors=["unsafe_expression_source"])
    warnings = []
    sc.tl.rank_genes_groups(adata, groupby=groupby, method="wilcoxon", layer=layer)
    marker_df = sc.get.rank_genes_groups_df(adata, group=None)
    table_path = Path(tables_dir) / "marker_genes.csv"
    marker_df.to_csv(table_path, index=False)

    top = marker_df.groupby("group", observed=False).head(top_n)
    top_marker_summary = [
        {
            "group": str(row.get("group")),
            "gene": str(row.get("names")),
            "score": round(float(row.get("scores")), 4) if pd.notna(row.get("scores")) else None,
            "logfoldchanges": round(float(row.get("logfoldchanges")), 4) if pd.notna(row.get("logfoldchanges")) else None,
            "pvals_adj": float(row.get("pvals_adj")) if pd.notna(row.get("pvals_adj")) else None,
        }
        for row in top.head(18).to_dict(orient="records")
    ]
    top_path = Path(tables_dir) / "marker_genes_top5.csv"
    top.to_csv(top_path, index=False)
    figures = []
    heatmap = _marker_heatmap(
        adata,
        marker_df,
        groupby=groupby,
        figures_dir=figures_dir,
        top_n=min(top_n, 4),
        expression_layer=layer or "X",
    )
    if heatmap:
        figures.append(heatmap)
    return ToolResult(
        status="success",
        summary=f"Ranked marker genes for `{groupby}` using layer `{layer or 'X'}` and saved {len(marker_df)} rows.",
        figures=figures,
        tables=[
            {"path": str(table_path), "title": "Marker genes"},
            {"path": str(top_path), "title": "Top 5 marker genes per cluster"},
        ],
        observations={
            "marker_rows": int(len(marker_df)),
            "groupby": groupby,
            "marker_heatmap_genes": heatmap is not None,
            "expression_layer": layer or "X",
            "top_marker_summary": top_marker_summary,
        },
        warnings=warnings,
    )
