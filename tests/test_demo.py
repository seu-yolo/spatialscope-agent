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
