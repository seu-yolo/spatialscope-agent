from __future__ import annotations

from pathlib import Path
from typing import Any


DEMO_PRESET: dict[str, Any] = {
    "data_path": "data/demo_embryo.h5ad",
    "query": "检查这个早期小鼠胚胎空间数据的质量，比较空间结构与 UMAP 聚类，并查看 Pou5f1、Sox17、T 和 Mesp1 的空间表达。总结主要观察和局限。",
    "mode": "standard",
    "outdir": "outputs/runs",
    "min_genes": 20,
    "min_cells": 3,
    "max_mt_pct": 25.0,
    "resolution": 0.8,
    "gene_text": "Pou5f1, Sox17, T, Mesp1",
    "annotation_top_n": 12,
}


def get_demo_preset() -> dict[str, Any]:
    return dict(DEMO_PRESET)


def _is_valid_demo(path: Path) -> bool:
    try:
        import anndata as ad

        adata = ad.read_h5ad(path, backed="r")
        try:
            has_spatial = "spatial" in adata.obsm
            return bool(adata.n_obs > 0 and adata.n_vars > 0 and has_spatial)
        finally:
            adata.file.close()
    except Exception:
        return False


def ensure_demo_data(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path or str(DEMO_PRESET["data_path"]))
    if target.exists():
        if _is_valid_demo(target):
            return {"path": str(target), "created": False}
        target.unlink(missing_ok=True)

    try:
        from scripts.create_demo_data import create_demo_data
    except Exception as exc:
        raise RuntimeError(
            "Could not import the demo data generator. Run from the project root or create "
            "`data/demo_tiny.h5ad` with `python scripts/create_demo_data.py`."
        ) from exc

    create_demo_data(str(target))
    return {"path": str(target), "created": True}
