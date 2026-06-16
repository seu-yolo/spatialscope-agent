from __future__ import annotations

from pathlib import Path
from typing import Any

from spatialscope.tools.base import ToolResult, missing_dependency


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
    sc.pp.scale(adata, max_value=10)

    import matplotlib.pyplot as plt

    hvg = adata.var.get("highly_variable")
    fig, ax = plt.subplots(figsize=(4, 3))
    if hvg is not None:
        counts = [int(hvg.sum()), int((~hvg).sum())]
        ax.bar(["HVG", "Other"], counts, color=["#1f77b4", "#d0d7de"])
    ax.set_title("Highly variable genes")
    fig.tight_layout()
    fig_path = Path(figures_dir) / "highly_variable_genes.png"
    fig.savefig(fig_path, bbox_inches="tight", dpi=300)
    plt.close(fig)

    return ToolResult(
        status="success",
        summary=f"Normalized, log-transformed, selected up to {n_top_genes} HVGs, and scaled the matrix.",
        figures=[
            {
                "path": str(fig_path),
                "title": "Highly variable genes",
                "caption": "Number of selected highly variable genes used for downstream embedding.",
            }
        ],
        observations={"n_highly_variable": int(adata.var.get("highly_variable", []).sum()) if "highly_variable" in adata.var else None},
    )

