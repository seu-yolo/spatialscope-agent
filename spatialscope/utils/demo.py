from __future__ import annotations

from pathlib import Path
from typing import Any


DEMO_PRESET: dict[str, Any] = {
    "data_path": "data/demo_embryo.h5ad",
    "query": "探索早期小鼠胚胎空间转录组结构，生成 cluster marker genes，并绘制 Pou5f1 Sox2 Nanog Sox17 Gata6 T Mesp1 的空间表达图。",
    "mode": "standard",
    "outdir": "outputs/runs",
    "min_genes": 20,
    "min_cells": 3,
    "max_mt_pct": 25.0,
    "resolution": 0.8,
    "gene_text": "Pou5f1, Sox2, Nanog, Sox17, Gata6, T, Mesp1",
    "annotation_top_n": 12,
}


def get_demo_preset() -> dict[str, Any]:
    return dict(DEMO_PRESET)


def ensure_demo_data(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path or str(DEMO_PRESET["data_path"]))
    if target.exists():
        return {"path": str(target), "created": False}

    try:
        from scripts.create_demo_data import create_demo_data
    except Exception as exc:
        raise RuntimeError(
            "Could not import the demo data generator. Run from the project root or create "
            "`data/demo_tiny.h5ad` with `python scripts/create_demo_data.py`."
        ) from exc

    create_demo_data(str(target))
    return {"path": str(target), "created": True}
