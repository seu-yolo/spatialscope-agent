import os

from spatialscope.utils.replay import build_rerun_recipe, render_rerun_script, write_rerun_recipe


def test_build_rerun_recipe_captures_command_without_secrets():
    state = {
        "run_id": "run",
        "data_path": "data/demo tiny.h5ad",
        "user_query": "run quick analysis for GeneA",
        "mode": "quick",
        "outdir": "outputs/runs",
        "dataset_hash": "abc123",
        "parameters": {"mode": "quick"},
        "plan_source": "rule_based",
        "approved_plan": [{"tool": "run_qc", "params": {}, "rationale": "QC"}],
    }

    recipe = build_rerun_recipe(state)

    assert recipe["run_id"] == "run"
    assert recipe["data_path"] == "data/demo tiny.h5ad"
    assert recipe["dataset_hash"] == "abc123"
    assert "--data 'data/demo tiny.h5ad'" in recipe["conda_command_string"]
    assert "API" not in recipe["conda_command_string"]
    assert "key" not in recipe["conda_command_string"].lower()


def test_write_rerun_recipe_writes_json_markdown_and_executable_script(tmp_path):
    run_dir = tmp_path / "outputs" / "runs" / "run"
    state = {
        "run_id": "run",
        "run_dir": str(run_dir),
        "data_path": "data/demo_tiny.h5ad",
        "user_query": "run quick analysis",
        "mode": "quick",
        "outdir": "outputs/runs",
        "approved_plan": [],
    }

    recipe = write_rerun_recipe(state, run_dir)

    assert recipe["mode"] == "quick"
    assert (run_dir / "rerun_recipe.json").exists()
    assert (run_dir / "RERUN.md").exists()
    assert (run_dir / "rerun.sh").exists()
    assert os.access(run_dir / "rerun.sh", os.X_OK)
    assert "SpatialScope Rerun Recipe" in (run_dir / "RERUN.md").read_text(encoding="utf-8")


def test_rerun_script_uses_overridable_project_and_data_path():
    script = render_rerun_script(
        {
            "data_path": "data/demo tiny.h5ad",
            "outdir": "outputs/runs",
            "query": "run quick analysis",
            "mode": "quick",
        }
    )

    assert "SPATIALSCOPE_PROJECT_DIR" in script
    assert 'DATA_PATH="${1:-}"' in script
    assert "DATA_PATH='data/demo tiny.h5ad'" in script
    assert "--data \"$DATA_PATH\"" in script
