from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from spatialscope.tools.base import ToolResult, missing_dependency


def run_neighborhood_enrichment(
    adata: Any,
    *,
    figures_dir: str,
    tables_dir: str,
    cluster_key: str = "leiden",
) -> ToolResult:
    if "spatial" not in adata.obsm:
        return ToolResult(status="failed", summary="Spatial coordinates not found; neighborhood enrichment skipped.")
    if cluster_key not in adata.obs:
        return ToolResult(status="failed", summary=f"Cluster key not found: {cluster_key}", errors=[cluster_key])
    try:
        import squidpy as sq
    except Exception as exc:
        raise missing_dependency("squidpy", "neighborhood enrichment") from exc

    if "spatial_connectivities" not in adata.obsp:
        sq.gr.spatial_neighbors(adata)
    sq.gr.nhood_enrichment(adata, cluster_key=cluster_key)
    result = adata.uns.get(f"{cluster_key}_nhood_enrichment")
    if result is None or "zscore" not in result:
        return ToolResult(status="failed", summary="Squidpy did not return neighborhood enrichment z-scores.")

    z = result["zscore"]
    categories = list(adata.obs[cluster_key].astype("category").cat.categories)
    table_path = Path(tables_dir) / "neighborhood_enrichment_zscore.csv"
    pd.DataFrame(z, index=categories, columns=categories).to_csv(table_path)

    import matplotlib.pyplot as plt
    import seaborn as sns

    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(z, xticklabels=categories, yticklabels=categories, cmap="vlag", center=0, ax=ax)
    ax.set_title("Neighborhood enrichment z-score")
    fig.tight_layout()
    fig_path = Path(figures_dir) / "neighborhood_enrichment.png"
    fig.savefig(fig_path, bbox_inches="tight", dpi=300)
    plt.close(fig)
    return ToolResult(
        status="success",
        summary=f"Computed neighborhood enrichment for `{cluster_key}`.",
        figures=[
            {
                "path": str(fig_path),
                "title": "Neighborhood enrichment",
                "caption": f"Squidpy neighborhood enrichment z-scores for spatial adjacency between `{cluster_key}` groups.",
            }
        ],
        tables=[{"path": str(table_path), "title": "Neighborhood enrichment z-score"}],
    )

