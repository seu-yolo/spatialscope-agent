from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from spatialscope.domain.dataset_profile import profile_adata
from spatialscope.tools.base import ToolResult, missing_dependency
from spatialscope.utils.paths import file_sha256


def _summary_from_adata(adata: Any, *, path: str, dataset_hash: str) -> dict[str, Any]:
    has_spatial = "spatial" in getattr(adata, "obsm", {})
    profile = profile_adata(adata, data_path=path, dataset_hash=dataset_hash)
    summary: dict[str, Any] = {
        "n_obs": int(adata.n_obs),
        "n_vars": int(adata.n_vars),
        "obs_columns": list(map(str, adata.obs.columns[:50])),
        "var_columns": list(map(str, adata.var.columns[:50])),
        "obsm_keys": list(map(str, adata.obsm.keys())),
        "layer_keys": list(map(str, adata.layers.keys())),
        "has_spatial": has_spatial,
        "matrix_state": profile.matrix_state,
        "recommended_run_depth": profile.recommended_run_depth,
        "cluster_columns": profile.cluster_fields,
        "cell_type_columns": profile.cell_type_fields,
        "scientific_warnings": profile.scientific_warnings,
        "dataset_profile": profile.model_dump(),
        "expression_lineage": profile.expression_lineage,
        "var_names_preview": list(map(str, adata.var_names[:10])),
        "obs_names_preview": list(map(str, adata.obs_names[:10])),
    }
    if has_spatial:
        coords = np.asarray(adata.obsm["spatial"])
        summary["spatial_shape"] = list(coords.shape)
        if coords.size:
            summary["spatial_bounds"] = {
                "x_min": float(np.nanmin(coords[:, 0])),
                "x_max": float(np.nanmax(coords[:, 0])),
                "y_min": float(np.nanmin(coords[:, 1])),
                "y_max": float(np.nanmax(coords[:, 1])),
            }
    return summary


def load_h5ad(path: str) -> tuple[Any, ToolResult]:
    data_path = Path(path)
    if not data_path.exists():
        return None, ToolResult(status="failed", summary=f"Data file not found: {path}", errors=[path])
    if data_path.suffix != ".h5ad":
        return None, ToolResult(status="failed", summary="SpatialScope v1 expects an .h5ad file.", errors=[path])

    try:
        import anndata as ad
    except Exception as exc:
        err = missing_dependency("anndata", "reading .h5ad files")
        return None, ToolResult(status="failed", summary=str(err), errors=[f"{type(exc).__name__}: {exc}"])

    adata = ad.read_h5ad(data_path)
    dataset_hash = file_sha256(data_path, max_bytes=64 * 1024 * 1024)
    summary = _summary_from_adata(adata, path=str(data_path), dataset_hash=dataset_hash)
    summary["dataset_hash"] = dataset_hash
    return adata, ToolResult(
        status="success",
        summary=f"Loaded {data_path.name}: {adata.n_obs} observations x {adata.n_vars} genes.",
        observations={"dataset_summary": summary},
        warnings=list(summary.get("scientific_warnings", [])),
    )
