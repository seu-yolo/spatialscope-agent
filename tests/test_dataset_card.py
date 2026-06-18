import json

from spatialscope.utils.dataset_card import build_dataset_card, write_dataset_card


def test_dataset_card_builds_checks_and_recommended_mode():
    state = {
        "run_id": "run",
        "data_path": "data/demo_tiny.h5ad",
        "dataset_hash": "abcdef1234567890",
        "dataset_summary": {
            "n_obs": 120,
            "n_vars": 240,
            "has_spatial": True,
            "spatial_shape": [120, 2],
            "obs_columns": ["cluster"],
            "var_columns": ["highly_variable"],
            "obsm_keys": ["spatial", "X_umap"],
            "layer_keys": ["counts"],
            "obs_names_preview": ["spot-1"],
            "var_names_preview": ["GeneA"],
            "spatial_bounds": {"x": [0, 10], "y": [0, 12]},
        },
    }

    card = build_dataset_card(state)

    assert card["recommended_mode"] == "standard"
    assert card["short_hash"] == "abcdef123456"
    assert card["metrics"]["spatial"] == "yes"
    checks = {item["name"]: item for item in card["checks"]}
    assert checks["Shape"]["status"] == "pass"
    assert checks["Spatial coordinates"]["status"] == "pass"
    assert "raw expression matrices" in card["privacy_note"]


def test_write_dataset_card_writes_json_markdown_html(tmp_path):
    state = {
        "run_id": "run",
        "run_dir": str(tmp_path),
        "data_path": "data/demo_tiny.h5ad",
        "dataset_hash": "hash",
        "dataset_summary": {"n_obs": 50, "n_vars": 80, "has_spatial": True, "obsm_keys": ["spatial"]},
    }

    card = write_dataset_card(state)

    assert card["recommended_mode"] == "standard"
    assert (tmp_path / "dataset_card.json").exists()
    assert (tmp_path / "DATASET_CARD.md").exists()
    assert (tmp_path / "dataset_card.html").exists()
    loaded = json.loads((tmp_path / "dataset_card.json").read_text(encoding="utf-8"))
    assert loaded["dataset_hash"] == "hash"
    markdown = (tmp_path / "DATASET_CARD.md").read_text(encoding="utf-8")
    html = (tmp_path / "dataset_card.html").read_text(encoding="utf-8")
    assert "Schema Preview" in markdown
    assert "Data Before Interpretation" in html
    assert "full spatial coordinate arrays" in html


def test_dataset_card_warns_missing_spatial_or_tiny_demo():
    state = {
        "run_id": "tiny",
        "dataset_summary": {"n_obs": 5, "n_vars": 8, "has_spatial": False},
    }

    card = build_dataset_card(state)

    assert card["recommended_mode"] == "quick"
    checks = {item["name"]: item for item in card["checks"]}
    assert checks["Spatial coordinates"]["status"] == "warn"
    assert checks["Dataset fingerprint"]["status"] == "warn"
    assert checks["Scale"]["status"] == "warn"
