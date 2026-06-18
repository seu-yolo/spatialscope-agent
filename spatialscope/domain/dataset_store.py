from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


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
        self._cache[path] = adata
        return adata

    def save(self, adata: Any, ref: str) -> None:
        path = Path(ref)
        path.parent.mkdir(parents=True, exist_ok=True)
        adata.write_h5ad(path)
        self._cache[str(path)] = adata

    def clear(self) -> None:
        self._cache.clear()


DEFAULT_DATASET_STORE = DatasetStore()
