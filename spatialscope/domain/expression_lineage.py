from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np


MatrixState = Literal["count_like", "log_normalized", "scaled", "unknown"]


@dataclass(frozen=True)
class MatrixStateAssessment:
    state: MatrixState
    evidence: list[str]
    heuristic: bool = True


def _sample_values(matrix: Any, *, max_values: int = 4096) -> np.ndarray:
    """Sample matrix values without densifying the full matrix."""

    if hasattr(matrix, "data"):
        values = np.asarray(matrix.data)
    else:
        arr = np.asarray(matrix)
        if arr.ndim == 0:
            values = arr.reshape(1)
        else:
            flat = arr.reshape(-1)
            if flat.size > max_values:
                indexes = np.linspace(0, flat.size - 1, num=max_values, dtype=int)
                values = flat[indexes]
            else:
                values = flat
    values = values[np.isfinite(values)]
    if values.size > max_values:
        indexes = np.linspace(0, values.size - 1, num=max_values, dtype=int)
        values = values[indexes]
    return values.astype(float, copy=False)


def infer_matrix_state(matrix: Any) -> MatrixStateAssessment:
    values = _sample_values(matrix)
    if values.size == 0:
        return MatrixStateAssessment("unknown", ["matrix has no finite sampled values"])

    min_value = float(np.nanmin(values))
    max_value = float(np.nanmax(values))
    non_negative = bool(min_value >= 0)
    integer_like = bool(np.allclose(values, np.round(values), atol=1e-6))
    frac_negative = float(np.mean(values < 0))
    frac_large = float(np.mean(values > 50))
    evidence = [
        f"sampled_values={values.size}",
        f"min={min_value:.4g}",
        f"max={max_value:.4g}",
        f"integer_like={integer_like}",
        f"negative_fraction={frac_negative:.3f}",
    ]

    if non_negative and integer_like and max_value > 20:
        return MatrixStateAssessment("count_like", evidence)
    if frac_negative > 0.01:
        return MatrixStateAssessment("scaled", evidence)
    if non_negative and max_value <= 30 and frac_large < 0.01 and not integer_like:
        return MatrixStateAssessment("log_normalized", evidence)
    return MatrixStateAssessment("unknown", evidence)


def select_interpretation_layer(adata: Any) -> str | None:
    for layer in ("spatialscope_interpretation", "log_normalized", "lognorm", "normalized"):
        if layer in getattr(adata, "layers", {}):
            return layer
    if getattr(adata, "raw", None) is not None:
        return None
    return None


def build_expression_lineage(adata: Any, *, preferred_layer: str | None = None) -> dict[str, Any]:
    assessment = infer_matrix_state(adata.X)
    layer_keys = list(map(str, getattr(adata, "layers", {}).keys()))
    selected = preferred_layer if preferred_layer in layer_keys else select_interpretation_layer(adata)
    if selected is None and "spatialscope_interpretation" in layer_keys:
        selected = "spatialscope_interpretation"
    warnings: list[str] = []
    if assessment.state == "unknown":
        warnings.append("Input matrix state is unknown; interpretation layer must be treated as an assumption.")
    if assessment.state == "scaled":
        warnings.append("Input matrix appears scaled; avoid marker ranking or expression interpretation directly on X.")
    return {
        "matrix_state": assessment.state,
        "assessment_evidence": assessment.evidence,
        "heuristic": assessment.heuristic,
        "available_layers": layer_keys,
        "recommended_interpretation_layer": selected or "X_assumed",
        "modeling_layer": "spatialscope_model_scaled" if "spatialscope_model_scaled" in layer_keys else "X",
        "warnings": warnings,
    }
