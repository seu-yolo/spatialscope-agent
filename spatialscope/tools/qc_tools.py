from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from spatialscope.tools.base import ToolResult, missing_dependency
from spatialscope.visualization.theme import apply_matplotlib_theme


def run_qc(
    adata: Any,
    *,
    figures_dir: str,
    tables_dir: str,
    min_genes: int = 20,
    min_cells: int = 3,
    max_mt_pct: float = 25,
) -> ToolResult:
    try:
        import scanpy as sc
    except Exception as exc:
        raise missing_dependency("scanpy", "QC analysis") from exc

    adata.var["mt"] = [str(name).lower().startswith("mt-") for name in adata.var_names]
    try:
        sc.pp.calculate_qc_metrics(adata, qc_vars=["mt"], inplace=True, percent_top=None)
    except Exception:
        sc.pp.calculate_qc_metrics(adata, inplace=True, percent_top=None)
        adata.obs["pct_counts_mt"] = 0.0

    before = {"n_obs": int(adata.n_obs), "n_vars": int(adata.n_vars)}
    if min_cells > 0:
        sc.pp.filter_genes(adata, min_cells=min_cells)
    if min_genes > 0:
        sc.pp.filter_cells(adata, min_genes=min_genes)
    if "pct_counts_mt" in adata.obs:
        adata._inplace_subset_obs(np.asarray(adata.obs["pct_counts_mt"]) <= max_mt_pct)
    after = {"n_obs": int(adata.n_obs), "n_vars": int(adata.n_vars)}

    summary_df = pd.DataFrame([{"stage": "before", **before}, {"stage": "after", **after}])
    table_path = Path(tables_dir) / "qc_summary.csv"
    summary_df.to_csv(table_path, index=False)

    apply_matplotlib_theme()
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(10, 3))
    metrics = [
        ("total_counts", "Total counts"),
        ("n_genes_by_counts", "Genes by counts"),
        ("pct_counts_mt", "MT percent"),
    ]
    for ax, (column, title) in zip(axes, metrics):
        if column in adata.obs:
            values = np.asarray(adata.obs[column])
            ax.hist(values[np.isfinite(values)], bins=40, color="#4c78a8", alpha=0.85)
        ax.set_title(title)
    fig.suptitle("QC metric distributions")
    fig.tight_layout()
    fig_path = Path(figures_dir) / "qc_metrics.png"
    fig.savefig(fig_path, bbox_inches="tight")
    plt.close(fig)

    return ToolResult(
        status="success",
        summary=f"QC retained {after['n_obs']} observations and {after['n_vars']} genes.",
        figures=[
            {
                "path": str(fig_path),
                "title": "QC metric distributions",
                "caption": "Distributions of total counts, detected genes, and mitochondrial percentage after QC metric calculation.",
            }
        ],
        tables=[{"path": str(table_path), "title": "QC summary"}],
        observations={"qc_before": before, "qc_after": after},
        warnings=[] if after["n_obs"] > 0 else ["QC removed all observations; relax thresholds."],
    )

