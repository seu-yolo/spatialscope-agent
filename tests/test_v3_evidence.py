from __future__ import annotations

from spatialscope.agent.planner import fallback_parse_query
from spatialscope.llm.context import safe_for_llm
from spatialscope.llm.gateway import LLMGateway


def test_safe_context_redacts_matrix_like_payloads():
    payload = {
        "summary": {"n_obs": 4},
        "raw_matrix": [[1, 2], [3, 4]],
        "nested": {"spatial_coordinates": [[0, 0], [1, 1]]},
    }
    safe = safe_for_llm(payload)
    assert safe["raw_matrix"] == "[redacted matrix-like payload]"
    assert safe["nested"]["spatial_coordinates"] == "[redacted matrix-like payload]"


def test_fallback_findings_are_evidence_linked(monkeypatch):
    monkeypatch.setenv("SPATIALSCOPE_LLM_API_KEY", "")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "")
    gateway = LLMGateway.from_env()
    findings = gateway.synthesize_findings(
        query="检查 QC 并比较空间结构",
        dataset_profile={"n_obs": 10, "n_vars": 5},
        evidence_packs=[
            {
                "evidence_id": "inspect_dataset:load_h5ad:metric:0",
                "kind": "metric",
                "title": "load_h5ad metrics",
                "tool": "load_h5ad",
                "summary_metrics": {"n_obs": 10, "n_vars": 5, "has_spatial": True},
            },
            {
                "evidence_id": "execute_tool:run_clustering:table:0",
                "kind": "table",
                "title": "Cluster summary",
                "tool": "run_clustering",
                "summary_metrics": {"n_clusters": 3, "cluster_sizes": {"0": 4, "1": 3, "2": 3}},
            },
        ],
        warnings=[],
    )
    assert findings
    assert all(finding.evidence_ids for finding in findings)
    assert findings[0].source == "fallback"


def test_chinese_demo_query_parses_full_analysis_and_single_letter_t_gene():
    parsed = fallback_parse_query(
        "检查这个早期小鼠胚胎空间数据的质量，比较空间结构与 UMAP 聚类，并查看 Pou5f1、Sox17、T 和 Mesp1 的空间表达。",
        "standard",
    )
    assert "full_analysis" in parsed["requested_steps"]
    assert "gene_panel" in parsed["requested_steps"]
    assert "T" in parsed["genes"]
