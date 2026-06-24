import pandas as pd
import pytest

from scripts.create_demo_data import create_demo_data
from spatialscope.utils.demo import ensure_demo_data, get_demo_preset


def test_demo_preset_contains_standard_showcase_defaults():
    preset = get_demo_preset()
    assert preset["mode"] == "standard"
    assert preset["data_path"].endswith("demo_embryo.h5ad")
    assert "Pou5f1" in preset["gene_text"]
    assert "Mesp1" in preset["gene_text"]
    assert preset["annotation_top_n"] >= 3


def test_ensure_demo_data_creates_h5ad(tmp_path):
    target = tmp_path / "demo.h5ad"
    result = ensure_demo_data(target)
    assert result["created"] is True
    assert target.exists()
    second = ensure_demo_data(target)
    assert second["created"] is False


def test_create_demo_data_handles_future_string_inference(tmp_path):
    target = tmp_path / "demo_future_strings.h5ad"
    try:
        previous = pd.get_option("future.infer_string")
    except pd.errors.OptionError:
        pytest.skip("pandas does not expose future.infer_string")

    try:
        pd.set_option("future.infer_string", True)
        create_demo_data(str(target))
    finally:
        pd.set_option("future.infer_string", previous)

    assert target.exists()


def test_ensure_demo_data_rebuilds_corrupt_file(tmp_path):
    target = tmp_path / "demo_corrupt.h5ad"
    target.write_text("not an h5ad", encoding="utf-8")

    result = ensure_demo_data(target)

    assert result["created"] is True
    assert target.stat().st_size > len("not an h5ad")
