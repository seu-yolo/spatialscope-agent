from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from spatialscope.tools.base import ToolResult, missing_dependency


def run_clustering(
    adata: Any,
    *,
    figures_dir: str,
    tables_dir: str,
    resolution: float = 0.8,
    random_state: int = 0,
) -> ToolResult:
    try:
        import scanpy as sc
    except Exception as exc:
        raise missing_dependency("scanpy", "PCA/UMAP/Leiden clustering") from exc

    use_highly_variable = "highly_variable" in adata.var and int(adata.var["highly_variable"].sum()) >= 10
    try:
        sc.tl.pca(
            adata,
            svd_solver="arpack",
            mask_var="highly_variable" if use_highly_variable else None,
            random_state=random_state,
        )
    except TypeError:
        sc.tl.pca(adata, svd_solver="arpack", use_highly_variable=use_highly_variable, random_state=random_state)
    sc.pp.neighbors(adata, n_neighbors=min(15, max(2, adata.n_obs - 1)), n_pcs=min(30, adata.n_vars, adata.n_obs - 1))
    sc.tl.umap(adata, random_state=random_state)
    try:
        sc.tl.leiden(
            adata,
            resolution=resolution,
            key_added="leiden",
            random_state=random_state,
            flavor="igraph",
            n_iterations=2,
            directed=False,
        )
    except TypeError:
        sc.tl.leiden(adata, resolution=resolution, key_added="leiden", random_state=random_state)

    counts = adata.obs["leiden"].value_counts().sort_index()
    table_path = Path(tables_dir) / "cluster_summary.csv"
    pd.DataFrame({"cluster": counts.index.astype(str), "n_obs": counts.values}).to_csv(table_path, index=False)

    return ToolResult(
        status="success",
        summary=f"Computed PCA, UMAP, and Leiden clustering with {len(counts)} clusters at resolution {resolution}.",
        tables=[{"path": str(table_path), "title": "Cluster summary"}],
        observations={"n_clusters": int(len(counts)), "resolution": resolution},
        warnings=[] if 2 <= len(counts) <= 30 else [f"Leiden produced {len(counts)} clusters; resolution may need adjustment."],
    )
