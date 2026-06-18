import json

from spatialscope.utils.storyboard import build_storyboard, write_storyboard


def test_storyboard_selects_curated_cards_and_writes_files(tmp_path):
    run_dir = tmp_path / "run"
    figures_dir = run_dir / "figures"
    figures_dir.mkdir(parents=True)
    spatial = figures_dir / "spatial_cluster.png"
    umap = figures_dir / "umap.png"
    spatial.write_text("png", encoding="utf-8")
    umap.write_text("png", encoding="utf-8")
    state = {
        "run_id": "run",
        "run_dir": str(run_dir),
        "user_query": "show spatial structure",
        "mode": "quick",
        "plan_source": "rule_based",
        "llm_enabled": False,
        "dataset_summary": {"n_obs": 12, "n_vars": 34},
        "quality": {"score": 100, "overall_status": "pass"},
        "agent_audit": {"score": 100, "overall_status": "pass"},
        "generated_figures": [
            {"title": "UMAP clusters", "path": str(umap), "caption": "Embedding view."},
            {"title": "Spatial cluster map", "path": str(spatial), "caption": "Tissue view."},
        ],
        "generated_tables": [{"path": str(run_dir / "tables" / "qc.csv")}],
        "execution_trace": [{"tool": "run_qc", "status": "success"}],
    }

    storyboard = write_storyboard(state, run_dir)

    assert storyboard["n_cards"] == 2
    assert storyboard["hero"]["role"] == "spatial"
    assert storyboard["metrics"]["spots"] == 12
    assert (run_dir / "storyboard.html").exists()
    assert (run_dir / "storyboard.json").exists()
    loaded = json.loads((run_dir / "storyboard.json").read_text(encoding="utf-8"))
    assert loaded["cards"][0]["relpath"] == "figures/spatial_cluster.png"


def test_storyboard_html_escapes_user_query(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {
        "run_id": "run",
        "run_dir": str(run_dir),
        "user_query": "<script>alert(1)</script>",
        "generated_figures": [],
        "generated_tables": [],
        "execution_trace": [],
    }

    storyboard = write_storyboard(state, run_dir)
    html = (run_dir / "storyboard.html").read_text(encoding="utf-8")

    assert storyboard["n_cards"] == 0
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_build_storyboard_ignores_missing_figures(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    state = {
        "run_id": "run",
        "run_dir": str(run_dir),
        "generated_figures": [{"title": "Spatial missing", "path": str(run_dir / "missing.png")}],
        "generated_tables": [],
        "execution_trace": [],
    }

    storyboard = build_storyboard(state, run_dir=run_dir)

    assert storyboard["n_cards"] == 0
    assert storyboard["hero"] == {}
