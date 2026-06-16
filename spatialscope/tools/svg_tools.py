from __future__ import annotations

from pathlib import Path
from typing import Any

from spatialscope.tools.base import ToolResult


def run_svg(adata: Any, *, figures_dir: str, tables_dir: str, mode: str = "moran") -> ToolResult:
    if "spatial" not in adata.obsm:
        return ToolResult(status="failed", summary="Spatial coordinates not found; SVG skipped.", warnings=["missing obsm['spatial']"])
    try:
        import squidpy as sq
    except Exception:
        return ToolResult(
            status="skipped",
            summary="Squidpy is not installed; spatially variable gene analysis was skipped.",
            warnings=["Install the optional Squidpy extension with `conda env update -n spatialscope-agent -f environment-squidpy.yml`."],
        )

    if "spatial_connectivities" not in adata.obsp:
        sq.gr.spatial_neighbors(adata)
    sq.gr.spatial_autocorr(adata, mode=mode)
    key = f"{mode}I" if mode == "moran" else f"{mode}C"
    result_key = key if key in adata.uns else "moranI"
    result = adata.uns.get(result_key)
    if result is None:
        return ToolResult(status="failed", summary="Squidpy did not return spatial autocorrelation results.")

    table_path = Path(tables_dir) / f"svg_{mode}.csv"
    result.to_csv(table_path)

    import matplotlib.pyplot as plt

    top = result.sort_values(result.columns[0], ascending=False).head(15)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.barh(top.index.astype(str)[::-1], top.iloc[:, 0].values[::-1], color="#4c78a8")
    ax.set_title(f"Top spatially variable genes ({mode})")
    ax.set_xlabel(top.columns[0])
    fig.tight_layout()
    fig_path = Path(figures_dir) / f"svg_{mode}_top.png"
    fig.savefig(fig_path, bbox_inches="tight", dpi=300)
    plt.close(fig)
    return ToolResult(
        status="success",
        summary=f"Computed spatial autocorrelation using {mode} and saved {len(result)} gene results.",
        figures=[
            {
                "path": str(fig_path),
                "title": f"Top SVGs by {mode}",
                "caption": f"Top genes ranked by Squidpy spatial autocorrelation ({mode}) on the spatial neighbor graph.",
            }
        ],
        tables=[{"path": str(table_path), "title": f"SVG results ({mode})"}],
        observations={"svg_rows": int(len(result)), "mode": mode},
    )
