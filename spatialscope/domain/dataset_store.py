from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from spatialscope.domain.dataset_profile import ensure_spatial_obsm


def _coerce_h5ad_string_axes(adata: Any) -> None:
    """Avoid AnnData nullable-string write failures across pandas defaults."""
    import numpy as np
    import pandas as pd
    from pandas.api.types import is_string_dtype

    string_array_types = tuple(
        cls
        for cls in (
            getattr(pd.arrays, "StringArray", None),
            getattr(pd.arrays, "ArrowStringArray", None),
        )
        if cls is not None
    )
    if not string_array_types:
        return

    def is_nullable_string(values: Any) -> bool:
        array = getattr(values, "array", values)
        dtype = getattr(values, "dtype", None)
        return isinstance(array, string_array_types) or bool(dtype is not None and is_string_dtype(dtype))

    def coerce_frame(frame: Any) -> None:
        if is_nullable_string(frame.index):
            frame.index = pd.Index(
                np.asarray(frame.index.to_numpy(dtype=object), dtype=object),
                dtype=object,
                name=frame.index.name,
            )
        for column in list(frame.columns):
            values = frame[column]
            if is_nullable_string(values):
                frame[column] = pd.Series(
                    np.asarray(values.to_numpy(dtype=object), dtype=object),
                    index=frame.index,
                    dtype=object,
                )

    coerce_frame(adata.obs)
    coerce_frame(adata.var)


class DatasetStore:
    """Runtime boundary for AnnData objects.

    Graph state stores only paths. The store may cache objects in process but the
    durable working `.h5ad` path remains the source of truth for resume/replay.
    """

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}

    def prepare_working_copy(self, data_path: str, *, intermediate_dir: str, run_id: str) -> str:
        source = Path(data_path)
        root = Path(intermediate_dir)
        root.mkdir(parents=True, exist_ok=True)
        target = root / f"{run_id}_working.h5ad"
        if not target.exists():
            shutil.copy2(source, target)
        return str(target)

    def load(self, ref: str) -> Any:
        path = str(Path(ref))
        if path in self._cache:
            return self._cache[path]
        import anndata as ad

        adata = ad.read_h5ad(path)
        ensure_spatial_obsm(adata)
        self._cache[path] = adata
        return adata

    def save(self, adata: Any, ref: str) -> None:
        path = Path(ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        _coerce_h5ad_string_axes(adata)
        adata.write_h5ad(path)
        self._cache[str(path)] = adata

    def clear(self) -> None:
        self._cache.clear()


DEFAULT_DATASET_STORE = DatasetStore()
