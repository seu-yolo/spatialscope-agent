from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from spatialscope.domain.expression_lineage import build_expression_lineage, infer_matrix_state
from spatialscope.utils.paths import file_sha256

SPATIAL_OBS_PAIRS = (
    ("x", "y"),
    ("image_x", "image_y"),
    ("spatial_x", "spatial_y"),
    ("x_flatten", "y_flatten"),
    ("array_col", "array_row"),
    ("pxl_col_in_fullres", "pxl_row_in_fullres"),
)


class DatasetProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dataset_name: str = ""
    dataset_hash: str = ""
    data_path: str = ""
    n_obs: int = 0
    n_vars: int = 0
    sparsity: float | None = None
    spatial_keys: list[str] = Field(default_factory=list)
    spatial_valid: bool = False
    layers: list[str] = Field(default_factory=list)
    has_raw: bool = False
    embeddings: list[str] = Field(default_factory=list)
    cluster_fields: list[str] = Field(default_factory=list)
    cell_type_fields: list[str] = Field(default_factory=list)
    gene_examples: list[str] = Field(default_factory=list)
    duplicate_gene_names: bool = False
    organism: str = "unknown"
    technology: str = "unknown"
    matrix_state: str = "unknown"
    matrix_state_evidence: list[str] = Field(default_factory=list)
    heuristic: bool = True
    recommended_expression_source: str = "X_assumed"
    expression_lineage: dict[str, Any] = Field(default_factory=dict)
    scientific_warnings: list[str] = Field(default_factory=list)
    recommended_run_depth: str = "quick"

    def legacy_summary(self) -> dict[str, Any]:
        return {
            "n_obs": self.n_obs,
            "n_vars": self.n_vars,
            "obs_columns": [],
            "var_columns": [],
            "obsm_keys": self.embeddings + self.spatial_keys,
            "layer_keys": self.layers,
            "has_spatial": self.spatial_valid,
            "var_names_preview": self.gene_examples,
            "dataset_hash": self.dataset_hash,
            "matrix_state": self.matrix_state,
            "recommended_expression_source": self.recommended_expression_source,
            "recommended_run_depth": self.recommended_run_depth,
        }


def _sparsity(matrix: Any) -> float | None:
    try:
        total = int(matrix.shape[0] * matrix.shape[1])
        if total == 0:
            return None
        if hasattr(matrix, "nnz"):
            nonzero = int(matrix.nnz)
        else:
            arr = np.asarray(matrix)
            nonzero = int(np.count_nonzero(arr))
        return round(1.0 - nonzero / total, 6)
    except Exception:
        return None


def _metadata_value(adata: Any, keys: list[str]) -> str:
    uns = getattr(adata, "uns", {})
    for key in keys:
        if key in uns and uns[key]:
            return str(uns[key])
    return "unknown"


def _is_valid_spatial_coords(coords: Any, *, n_obs: int) -> bool:
    try:
        arr = np.asarray(coords)
        return bool(arr.ndim == 2 and arr.shape[0] == n_obs and arr.shape[1] >= 2 and np.isfinite(arr[:, :2]).any())
    except Exception:
        return False


def _spatial_priority(key: str) -> tuple[int, str]:
    lowered = key.lower()
    if lowered == "spatial":
        return (0, lowered)
    if lowered == "x_spatial":
        return (1, lowered)
    if lowered.endswith("spatial"):
        return (2, lowered)
    if "spatial" in lowered:
        return (3, lowered)
    return (9, lowered)


def find_spatial_obsm_key(adata: Any) -> str | None:
    """Return the best valid obsm key that can act as spatial coordinates."""

    obsm = getattr(adata, "obsm", {})
    keys = [str(key) for key in obsm.keys() if str(key).lower() == "spatial" or "spatial" in str(key).lower()]
    for key in sorted(keys, key=_spatial_priority):
        if _is_valid_spatial_coords(obsm[key], n_obs=int(adata.n_obs)):
            return key
    return None


def ensure_spatial_obsm(adata: Any) -> str | None:
    """Normalize common spatial-coordinate conventions to `adata.obsm['spatial']`.

    Public AnnData files often use names such as `X_spatial` or store coordinates
    as observation columns. The analysis tools use one canonical key, so this
    helper creates a lightweight alias without changing expression values.
    """

    key = find_spatial_obsm_key(adata)
    if key:
        if key != "spatial":
            adata.obsm["spatial"] = np.asarray(adata.obsm[key])[:, :2].copy()
        adata.uns["spatialscope_spatial_source_key"] = key
        return key

    obs = getattr(adata, "obs", None)
    if obs is None:
        return None
    obs_columns = {str(col): col for col in obs.columns}
    lower_lookup = {str(col).lower(): col for col in obs.columns}
    for x_name, y_name in SPATIAL_OBS_PAIRS:
        x_col = obs_columns.get(x_name) or lower_lookup.get(x_name.lower())
        y_col = obs_columns.get(y_name) or lower_lookup.get(y_name.lower())
        if x_col is None or y_col is None:
            continue
        try:
            coords = obs[[x_col, y_col]].to_numpy(dtype=float)
        except Exception:
            continue
        if _is_valid_spatial_coords(coords, n_obs=int(adata.n_obs)):
            adata.obsm["spatial"] = coords[:, :2].copy()
            source = f"obs[{x_col},{y_col}]"
            adata.uns["spatialscope_spatial_source_key"] = source
            return source
    return None


def profile_adata(adata: Any, *, data_path: str = "", dataset_hash: str = "") -> DatasetProfile:
    obsm_keys = list(map(str, getattr(adata, "obsm", {}).keys()))
    spatial_keys = [key for key in obsm_keys if key.lower() == "spatial" or "spatial" in key.lower()]
    spatial_valid = False
    warnings: list[str] = []
    for key in spatial_keys:
        try:
            coords = np.asarray(adata.obsm[key])
            if coords.ndim == 2 and coords.shape[0] == adata.n_obs and coords.shape[1] >= 2 and np.isfinite(coords[:, :2]).any():
                spatial_valid = True
                break
        except Exception:
            warnings.append(f"Spatial key `{key}` could not be validated.")

    assessment = infer_matrix_state(adata.X)
    lineage = build_expression_lineage(adata)
    if assessment.state == "unknown":
        warnings.append("Matrix state is unknown; SpatialScope will keep expression interpretation explicitly labeled as an assumption.")
    if assessment.state == "scaled":
        warnings.append("Matrix appears scaled; marker ranking should use a preserved interpretation layer or raw representation.")
    if not spatial_valid:
        warnings.append("No valid spatial coordinate matrix was detected.")

    var_names = list(map(str, adata.var_names[:10]))
    duplicate_gene_names = bool(getattr(adata.var_names, "has_duplicates", False))
    layers = list(map(str, getattr(adata, "layers", {}).keys()))
    cluster_fields = [str(col) for col in adata.obs.columns if str(col).lower() in {"leiden", "cluster", "clusters"} or "cluster" in str(col).lower()]
    cell_type_fields = [str(col) for col in adata.obs.columns if "cell" in str(col).lower() and "type" in str(col).lower()]
    recommended_depth = "standard" if spatial_valid and adata.n_obs >= 50 and adata.n_vars >= 50 else "quick"
    if any(key.lower().startswith("x_umap") for key in obsm_keys) and cluster_fields:
        recommended_depth = "quick"

    path = Path(data_path) if data_path else Path("")
    if data_path and not dataset_hash:
        dataset_hash = file_sha256(path, max_bytes=64 * 1024 * 1024)
    return DatasetProfile(
        dataset_name=path.name if data_path else "AnnData",
        dataset_hash=dataset_hash,
        data_path=data_path,
        n_obs=int(adata.n_obs),
        n_vars=int(adata.n_vars),
        sparsity=_sparsity(adata.X),
        spatial_keys=spatial_keys,
        spatial_valid=spatial_valid,
        layers=layers,
        has_raw=getattr(adata, "raw", None) is not None,
        embeddings=[key for key in obsm_keys if key not in spatial_keys],
        cluster_fields=cluster_fields,
        cell_type_fields=cell_type_fields,
        gene_examples=var_names,
        duplicate_gene_names=duplicate_gene_names,
        organism=_metadata_value(adata, ["organism", "species"]),
        technology=_metadata_value(adata, ["technology", "assay", "platform"]),
        matrix_state=assessment.state,
        matrix_state_evidence=assessment.evidence,
        heuristic=assessment.heuristic,
        recommended_expression_source=str(lineage.get("recommended_interpretation_layer", "X_assumed")),
        expression_lineage=lineage,
        scientific_warnings=warnings + list(lineage.get("warnings", [])),
        recommended_run_depth=recommended_depth,
    )
