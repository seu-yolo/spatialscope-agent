from __future__ import annotations

import anndata as ad
import numpy as np
import pandas as pd

from spatialscope.domain.dataset_profile import ensure_spatial_obsm
from spatialscope.tools.io_tools import load_h5ad


def test_load_h5ad_aliases_x_spatial_to_canonical_spatial(tmp_path):
    adata = ad.AnnData(np.ones((4, 3)))
    adata.var_names = ["Sox17", "T", "Mesp1"]
    adata.obsm["X_spatial"] = np.column_stack([np.arange(4), np.arange(4) * 2])
    path = tmp_path / "x_spatial.h5ad"
    adata.write_h5ad(path)

    loaded, result = load_h5ad(str(path))

    assert result.status == "success"
    assert loaded is not None
    assert "spatial" in loaded.obsm
    assert result.observations["dataset_summary"]["has_spatial"] is True
    assert result.observations["dataset_summary"]["spatial_source"] == "X_spatial"


def test_ensure_spatial_obsm_uses_obs_xy_when_obsm_missing():
    obs = pd.DataFrame({"x": [10, 11, 12], "y": [2, 3, 5]}, index=["a", "b", "c"])
    adata = ad.AnnData(np.ones((3, 2)), obs=obs)

    source = ensure_spatial_obsm(adata)

    assert source == "obs[x,y]"
    assert "spatial" in adata.obsm
    np.testing.assert_allclose(adata.obsm["spatial"], np.asarray([[10, 2], [11, 3], [12, 5]], dtype=float))
