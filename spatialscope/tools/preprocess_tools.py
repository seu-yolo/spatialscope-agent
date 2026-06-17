from __future__ import annotations

from pathlib import Path
from typing import Any

from spatialscope.tools.base import ToolResult, missing_dependency
from spatialscope.visualization.theme import NEUTRAL_LINE, SIGNAL_PLUM, SIGNAL_TEAL, apply_matplotlib_theme, polish_axis, save_figure_bundle


def run_preprocess(adata: Any, *, figures_dir: str, n_top_genes: int = 2000) -> ToolResult:
    try:
        import scanpy as sc
    except Exception as exc:
        raise missing_dependency("scanpy", "preprocessing") from exc

    if "counts" not in adata.layers:
        adata.layers["counts"] = adata.X.copy()
    sc.pp.normalize_total(adata, target_sum=1e4)
    sc.pp.log1p(adata)
    try:
        sc.pp.highly_variable_genes(adata, n_top_genes=min(n_top_genes, adata.n_vars), flavor="seurat")
    except Exception:
        sc.pp.highly_variable_genes(adata, n_top_genes=min(n_top_genes, adata.n_vars))
    sc.pp.scale(adata, max_value=10, zero_center=False)

    apply_matplotlib_theme()
    import matplotlib.pyplot as plt

    hvg = adata.var.get("highly_variable")
    fig, ax = plt.subplots(figsize=(4.4, 3.0), constrained_layout=True)
    if hvg is not None:
        counts = [int(hvg.sum()), int((~hvg).sum())]
        bars = ax.bar(["HVG", "Other"], counts, color=[SIGNAL_TEAL, NEUTRAL_LINE], edgecolor="white", linewidth=0.6)
        total = max(sum(counts), 1)
        for bar, value in zip(bars, counts):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value,
                f"{value:,}\n{value / total:.0%}",
                ha="center",
                va="bottom",
                fontsize=7.2,
                color=SIGNAL_PLUM if value else "#66737f",
            )
    polish_axis(ax, title="Highly variable genes", subtitle=f"top_n target {min(n_top_genes, adata.n_vars):,}")
    ax.set_ylabel("Genes")
    fig_path = Path(figures_dir) / "highly_variable_genes.png"
    saved = save_figure_bundle(fig, fig_path)
    plt.close(fig)

    return ToolResult(
        status="success",
        summary=f"Normalized, log-transformed, selected up to {n_top_genes} HVGs, and scaled the matrix with sparse-safe scaling.",
        figures=[
            {
                **saved,
                "title": "Highly variable genes",
                "caption": "Number of selected highly variable genes used for downstream embedding.",
            }
        ],
        observations={"n_highly_variable": int(adata.var.get("highly_variable", []).sum()) if "highly_variable" in adata.var else None},
    )
