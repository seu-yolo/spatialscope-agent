from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from spatialscope.domain.expression_lineage import build_expression_lineage, infer_matrix_state
from spatialscope.tools.base import ToolResult, missing_dependency
from spatialscope.visualization.theme import NEUTRAL_LINE, SIGNAL_PLUM, SIGNAL_TEAL, apply_matplotlib_theme, polish_axis, save_figure_bundle


def run_preprocess(adata: Any, *, figures_dir: str, n_top_genes: int = 2000) -> ToolResult:
    try:
        import scanpy as sc
    except Exception as exc:
        raise missing_dependency("scanpy", "preprocessing") from exc

    warnings: list[str] = []
    assessment = infer_matrix_state(adata.X)
    source_layer = "X"
    if assessment.state == "count_like":
        if "counts" not in adata.layers:
            adata.layers["counts"] = adata.X.copy()
        work = adata.copy()
        sc.pp.normalize_total(work, target_sum=1e4)
        sc.pp.log1p(work)
        adata.layers["spatialscope_interpretation"] = work.X.copy()
        interpretation_note = "verified count-like X normalized to target_sum=1e4 and log1p transformed"
    elif assessment.state == "log_normalized":
        adata.layers["spatialscope_interpretation"] = adata.X.copy()
        interpretation_note = "input X heuristically treated as log-normalized"
    else:
        adata.layers["spatialscope_interpretation"] = adata.X.copy()
        interpretation_note = f"input X preserved as interpretation layer under {assessment.state} assumption"
        warnings.append(
            f"Input matrix state is {assessment.state}; expression interpretation uses a labeled assumption instead of naming X as counts."
        )

    adata.X = adata.layers["spatialscope_interpretation"].copy()
    try:
        sc.pp.highly_variable_genes(adata, n_top_genes=min(n_top_genes, adata.n_vars), flavor="seurat")
    except Exception:
        sc.pp.highly_variable_genes(adata, n_top_genes=min(n_top_genes, adata.n_vars))
    adata.layers["spatialscope_model_input"] = adata.X.copy()
    sc.pp.scale(adata, max_value=10, zero_center=False)
    adata.layers["spatialscope_model_scaled"] = adata.X.copy()
    adata.uns["spatialscope_expression_lineage"] = build_expression_lineage(
        adata,
        preferred_layer="spatialscope_interpretation",
    )
    adata.uns["spatialscope_expression_lineage"]["source_layer"] = source_layer
    adata.uns["spatialscope_expression_lineage"]["preprocess_note"] = interpretation_note

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
        summary=(
            f"Prepared expression lineage, selected up to {n_top_genes} HVGs, and created a scaled modeling representation. "
            f"Interpretation layer: spatialscope_interpretation ({interpretation_note})."
        ),
        figures=[
            {
                **saved,
                "title": "Highly variable genes",
                "caption": (
                    "Number of selected highly variable genes used for downstream embedding. "
                    "Interpretation layer: spatialscope_interpretation; modeling layer: spatialscope_model_scaled."
                ),
            }
        ],
        observations={
            "n_highly_variable": int(adata.var.get("highly_variable", []).sum()) if "highly_variable" in adata.var else None,
            "expression_lineage": adata.uns.get("spatialscope_expression_lineage", {}),
        },
        warnings=warnings,
    )
