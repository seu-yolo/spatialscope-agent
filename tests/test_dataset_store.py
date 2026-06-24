import anndata as ad
import numpy as np
import pandas as pd
import pytest

from spatialscope.domain.dataset_store import DatasetStore
from scripts.create_demo_data import create_demo_data


def test_dataset_store_save_handles_nullable_string_axes(tmp_path):
    try:
        previous = pd.get_option("future.infer_string")
    except pd.errors.OptionError:
        pytest.skip("pandas does not expose future.infer_string")

    try:
        pd.set_option("future.infer_string", True)
        adata = ad.AnnData(
            X=np.ones((3, 2)),
            obs=pd.DataFrame({"region": ["epiblast", "endoderm", "mesoderm"]}, index=["spot_1", "spot_2", "spot_3"]),
            var=pd.DataFrame({"family": ["marker", "marker"]}, index=["Sox17", "Mesp1"]),
        )
    finally:
        pd.set_option("future.infer_string", previous)

    path = tmp_path / "working.h5ad"

    DatasetStore().save(adata, str(path))

    loaded = ad.read_h5ad(path)
    assert list(loaded.obs["region"].astype(str)) == ["epiblast", "endoderm", "mesoderm"]
    assert list(loaded.var_names.astype(str)) == ["Sox17", "Mesp1"]


def test_dataset_store_save_handles_demo_after_h5ad_roundtrip(tmp_path):
    source = tmp_path / "demo.h5ad"
    create_demo_data(str(source))

    try:
        previous = pd.get_option("future.infer_string")
    except pd.errors.OptionError:
        pytest.skip("pandas does not expose future.infer_string")

    try:
        pd.set_option("future.infer_string", True)
        adata = ad.read_h5ad(source)
    finally:
        pd.set_option("future.infer_string", previous)

    target = tmp_path / "working_roundtrip.h5ad"
    DatasetStore().save(adata, str(target))

    loaded = ad.read_h5ad(target)
    assert loaded.n_obs == 240
    assert "spatial" in loaded.obsm
