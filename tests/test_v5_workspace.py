from __future__ import annotations

import numpy as np
import pytest

from spatialscope.domain.evidence import UIAction
from spatialscope.domain.exploration_evidence import (
    safe_expression_sources,
    summarize_gene,
    summarize_selection,
)
from spatialscope.llm.gateway import LLMGateway
from spatialscope.llm.mode import resolve_llm_mode
from spatialscope.utils.demo import ensure_demo_data


def _demo_adata(tmp_path):
    import anndata as ad

    path = tmp_path / "demo_embryo.h5ad"
    ensure_demo_data(path)
    return ad.read_h5ad(path)


def test_llm_mode_resolution_labels_fallback_and_full():
    fallback = resolve_llm_mode(requested="auto", has_api_key=False, has_base_url=True, has_model=True)
    assert fallback.active_mode == "fallback"
    assert "规则模式" in fallback.label

    full = resolve_llm_mode(requested="full", has_api_key=True, has_base_url=True, has_model=True)
    assert full.active_mode == "full"
    assert full.enabled is True


def test_exploration_gene_and_selection_evidence_have_quantitative_support(tmp_path):
    adata = _demo_adata(tmp_path)
    source = safe_expression_sources(adata)[0]
    selected = list(map(str, adata.obs_names[:12]))

    gene_pack = summarize_gene(adata, "Sox17", source, "leiden", selected_obs_ids=selected)
    selection_pack = summarize_selection(adata, selected, "Sox17", source, "leiden")

    assert gene_pack.kind == "gene"
    assert gene_pack.evidence_id == "gene:Sox17:summary"
    assert gene_pack.summary_metrics["global"]["mean"] is not None
    assert gene_pack.summary_metrics["top_clusters_by_mean"]
    assert "selected_minus_global_mean" in gene_pack.summary_metrics
    assert selection_pack.kind == "selection"
    assert selection_pack.summary_metrics["selected_count"] == 12
    assert selection_pack.summary_metrics["cluster_composition"]


def test_unsafe_expression_source_blocks_gene_interpretation():
    import anndata as ad
    import pandas as pd

    adata = ad.AnnData(
        X=np.array([[-1.2, 0.1], [0.3, -0.7], [1.4, 0.5]], dtype=float),
        obs=pd.DataFrame({"leiden": ["0", "1", "1"]}, index=["a", "b", "c"]),
        var=pd.DataFrame(index=["Sox17", "Pou5f1"]),
    )
    assert safe_expression_sources(adata) == []
    pack = summarize_gene(adata, "Sox17", "X", "leiden")
    assert pack.evidence_id == "gene:Sox17:unsafe_source"
    assert "not safe" in pack.caveats[0]


def test_fallback_copilot_answers_are_question_specific_and_evidence_grounded(monkeypatch, tmp_path):
    monkeypatch.setenv("SPATIALSCOPE_LLM_MODE", "fallback")
    monkeypatch.delenv("SPATIALSCOPE_LLM_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    adata = _demo_adata(tmp_path)
    source = safe_expression_sources(adata)[0]
    selected = list(map(str, adata.obs_names[:10]))
    gene_pack = summarize_gene(adata, "Sox17", source, "leiden", selected_obs_ids=selected)
    selection_pack = summarize_selection(adata, selected, "Sox17", source, "leiden")
    context = {
        "selected_gene": "Sox17",
        "selected_obs_ids": selected,
        "expression_source": source,
        "evidence_ids": [gene_pack.evidence_id, selection_pack.evidence_id],
        "evidence_packs": [gene_pack.model_dump(), selection_pack.model_dump()],
        "warnings": [],
    }
    gateway = LLMGateway.from_env()

    top_answer = gateway.answer_contextual_question(context=context, question="哪个 cluster 的 Sox17 平均表达最高？")
    diff_answer = gateway.answer_contextual_question(context=context, question="我当前选择的空间区域和全局相比有什么差异？")

    assert top_answer["source"] == "fallback"
    assert diff_answer["source"] == "fallback"
    assert top_answer["direct_answer"] != diff_answer["direct_answer"]
    assert gene_pack.evidence_id in top_answer["evidence_ids"]
    assert selection_pack.evidence_id in diff_answer["evidence_ids"]
    assert any(action["type"] == "highlight_cluster" for action in top_answer["suggested_actions"])


def test_copilot_ui_action_schema_accepts_workspace_actions():
    action = UIAction(
        action_id="focus_cluster_2",
        type="highlight_cluster",
        label="高亮 cluster 2",
        payload={"cluster": "2"},
    )
    assert action.type == "highlight_cluster"
    with pytest.raises(Exception):
        UIAction(action_id="bad", type="invented_action", label="bad", payload={})
