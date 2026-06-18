from __future__ import annotations

from pathlib import Path

import anndata as ad
import numpy as np

from spatialscope.agent.runtime import AgentRuntime
from spatialscope.tools.spatial_tools import plot_gene_panel


def _write_tiny_h5ad(path: Path, *, with_leiden: bool = False) -> Path:
    x = np.asarray(
        [
            [4, 0, 1, 0, 2],
            [3, 0, 2, 1, 0],
            [0, 4, 0, 1, 2],
            [1, 5, 0, 0, 1],
            [0, 1, 5, 2, 0],
            [1, 0, 4, 2, 1],
            [2, 1, 0, 5, 0],
            [1, 2, 1, 4, 1],
        ],
        dtype=float,
    )
    adata = ad.AnnData(x)
    adata.var_names = ["GeneA", "GeneB", "GeneC", "GeneD", "GeneE"]
    adata.obs_names = [f"spot_{i}" for i in range(adata.n_obs)]
    adata.obsm["spatial"] = np.column_stack([np.arange(adata.n_obs), np.arange(adata.n_obs) % 3])
    if with_leiden:
        adata.obs["leiden"] = ["0", "0", "1", "1", "2", "2", "3", "3"]
    adata.write_h5ad(path)
    return path


def test_runtime_interrupt_resume_keeps_state_serializable(tmp_path, monkeypatch):
    monkeypatch.setenv("SPATIALSCOPE_LLM_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    data_path = _write_tiny_h5ad(tmp_path / "tiny.h5ad")
    runtime = AgentRuntime(checkpoint_path=tmp_path / "checkpoint.sqlite")

    paused = runtime.start_run(
        data_path=str(data_path),
        query="Plot GeneA in spatial view",
        mode="quick",
        outdir=str(tmp_path / "runs"),
        auto_approve=False,
    )

    assert paused["awaiting_plan_review"] is True
    assert "__interrupt__" in paused
    assert paused["thread_id"] == paused["run_id"]
    assert "_adata" not in paused
    assert paused["working_dataset_ref"].endswith("_working.h5ad")
    assert [step["tool"] for step in paused["task_plan"]] == ["plot_gene_panel"]

    final = runtime.resume_run(
        paused["thread_id"],
        approved_plan=paused["task_plan"],
        plan_source="test_approved",
    )

    assert "_adata" not in final
    assert Path(str(final["report_path"])).exists()
    assert [item["node"] for item in final["execution_trace"] if item["node"] == "review_plan"]
    assert any(item["tool"] == "plot_gene_panel" and item["status"] == "success" for item in final["execution_trace"])
    runtime.close()


def test_runtime_retries_with_parameter_patch(tmp_path, monkeypatch):
    monkeypatch.setenv("SPATIALSCOPE_LLM_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    data_path = _write_tiny_h5ad(tmp_path / "clustered.h5ad", with_leiden=True)
    runtime = AgentRuntime(checkpoint_path=tmp_path / "checkpoint_retry.sqlite")
    paused = runtime.start_run(
        data_path=str(data_path),
        query="Create a spatial plot.",
        mode="quick",
        outdir=str(tmp_path / "runs"),
        auto_approve=False,
    )
    final = runtime.resume_run(
        paused["thread_id"],
        approved_plan=[
            {
                "id": "bad_spatial",
                "tool": "plot_spatial",
                "params": {"color": "missing_column"},
                "rationale": "Exercise bounded repair retry.",
                "max_attempts": 2,
            }
        ],
        plan_source="test_approved",
    )
    statuses = [(item.get("node"), item.get("tool"), item.get("status")) for item in final["execution_trace"]]
    assert ("repair_or_continue", "plot_spatial", "retrying") in statuses
    assert ("execute_tool", "plot_spatial", "success_after_retry") in statuses
    assert final["approved_plan"][0]["params"]["color"] == "leiden"
    assert Path(str(final["report_path"])).exists()
    runtime.close()


def test_runtime_retries_misspelled_gene_with_suggestion(tmp_path, monkeypatch):
    monkeypatch.setenv("SPATIALSCOPE_LLM_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    data_path = _write_tiny_h5ad(tmp_path / "tiny_gene_retry.h5ad")
    runtime = AgentRuntime(checkpoint_path=tmp_path / "checkpoint_gene_retry.sqlite")
    paused = runtime.start_run(
        data_path=str(data_path),
        query="Plot GneeA in spatial view",
        mode="quick",
        outdir=str(tmp_path / "runs"),
        auto_approve=False,
    )
    final = runtime.resume_run(
        paused["thread_id"],
        approved_plan=paused["task_plan"],
        plan_source="test_approved",
    )
    statuses = [(item.get("node"), item.get("tool"), item.get("status")) for item in final["execution_trace"]]
    assert ("repair_or_continue", "plot_gene_panel", "retrying") in statuses
    assert ("execute_tool", "plot_gene_panel", "success_after_retry") in statuses
    assert final["approved_plan"][0]["params"]["genes"] == ["GeneA"]
    runtime.close()


def test_gene_panel_blocks_unsafe_unknown_expression_source(tmp_path):
    adata = ad.AnnData(np.asarray([[0.2, -1.1], [0.7, 1.4], [-0.3, 0.8]], dtype=float))
    adata.var_names = ["GeneA", "GeneB"]
    adata.obsm["spatial"] = np.column_stack([np.arange(adata.n_obs), np.arange(adata.n_obs)])
    result = plot_gene_panel(
        adata,
        figures_dir=str(tmp_path),
        genes=["GeneA"],
        expression_layer="spatialscope_interpretation",
    )
    assert result.status == "failed"
    assert "unsafe_expression_source" in result.errors
