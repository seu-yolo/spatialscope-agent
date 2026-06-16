from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from spatialscope.tools.base import ToolResult, missing_dependency


def rank_markers(adata: Any, *, tables_dir: str, groupby: str = "leiden") -> ToolResult:
    if groupby not in adata.obs:
        return ToolResult(status="failed", summary=f"Group column not found: {groupby}", errors=[groupby])
    try:
        import scanpy as sc
    except Exception as exc:
        raise missing_dependency("scanpy", "marker gene ranking") from exc

    sc.tl.rank_genes_groups(adata, groupby=groupby, method="wilcoxon")
    marker_df = sc.get.rank_genes_groups_df(adata, group=None)
    table_path = Path(tables_dir) / "marker_genes.csv"
    marker_df.to_csv(table_path, index=False)

    top = marker_df.groupby("group").head(5)
    top_path = Path(tables_dir) / "marker_genes_top5.csv"
    top.to_csv(top_path, index=False)
    return ToolResult(
        status="success",
        summary=f"Ranked marker genes for `{groupby}` and saved {len(marker_df)} rows.",
        tables=[
            {"path": str(table_path), "title": "Marker genes"},
            {"path": str(top_path), "title": "Top 5 marker genes per cluster"},
        ],
        observations={"marker_rows": int(len(marker_df)), "groupby": groupby},
    )

