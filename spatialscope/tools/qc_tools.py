from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from spatialscope.tools.base import ToolResult, missing_dependency
from spatialscope.visualization.theme import (
    NEUTRAL_MUTED,
    SIGNAL_CORAL,
    SIGNAL_PLUM,
    SIGNAL_TEAL,
    apply_matplotlib_theme,
    polish_axis,
    save_figure_bundle,
)


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
    quantiles: dict[str, dict[str, float]] = {}
    for column in ["total_counts", "n_genes_by_counts", "pct_counts_mt"]:
        if column not in adata.obs:
            continue
        values = np.asarray(adata.obs[column])
        finite = values[np.isfinite(values)]
        if len(finite):
            quantiles[column] = {
                "p05": round(float(np.percentile(finite, 5)), 3),
                "median": round(float(np.median(finite)), 3),
                "p95": round(float(np.percentile(finite, 95)), 3),
            }

    summary_df = pd.DataFrame([{"stage": "before", **before}, {"stage": "after", **after}])
    table_path = Path(tables_dir) / "qc_summary.csv"
    summary_df.to_csv(table_path, index=False)

    apply_matplotlib_theme()
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(9.2, 3.0), constrained_layout=True)
    metrics = [
        ("total_counts", "Total counts", SIGNAL_TEAL),
        ("n_genes_by_counts", "Genes by counts", SIGNAL_PLUM),
        ("pct_counts_mt", "MT percent", SIGNAL_CORAL),
    ]
    for ax, (column, title, color) in zip(axes, metrics):
        if column in adata.obs:
            values = np.asarray(adata.obs[column])
            finite = values[np.isfinite(values)]
            ax.hist(finite, bins=34, color=color, alpha=0.82, edgecolor="white", linewidth=0.35)
            if len(finite):
                median = float(np.median(finite))
                ax.axvline(median, color="#172026", linewidth=1.0, linestyle="--")
                ax.text(
                    0.98,
                    0.92,
                    f"median {median:.2g}",
                    transform=ax.transAxes,
                    ha="right",
                    va="top",
                    fontsize=7,
                    color=NEUTRAL_MUTED,
                )
        polish_axis(ax, title=title)
        ax.set_ylabel("Spots/cells")
    retained = after["n_obs"] / max(before["n_obs"], 1)
    fig.suptitle(f"QC metric distributions - retained {retained:.0%} observations", x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig_path = Path(figures_dir) / "qc_metrics.png"
    saved = save_figure_bundle(fig, fig_path)
    plt.close(fig)

    return ToolResult(
        status="success",
        summary=f"QC retained {after['n_obs']} observations and {after['n_vars']} genes.",
        figures=[
            {
                **saved,
                "title": "QC metric distributions",
                "caption": "Distributions of total counts, detected genes, and mitochondrial percentage after QC metric calculation.",
            }
        ],
        tables=[{"path": str(table_path), "title": "QC summary"}],
        observations={
            "qc_before": before,
            "qc_after": after,
            "qc_quantiles": quantiles,
            "retention_fraction": round(float(retained), 4),
            "qc_thresholds": {"min_genes": min_genes, "min_cells": min_cells, "max_mt_pct": max_mt_pct},
        },
        warnings=[] if after["n_obs"] > 0 else ["QC removed all observations; relax thresholds."],
    )
