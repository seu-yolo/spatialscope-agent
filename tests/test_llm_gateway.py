from __future__ import annotations

from typing import Any

from spatialscope.llm.gateway import LLMGateway


class FakeStructuredClient:
    enabled = True

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete_json(self, messages: list[dict[str, str]], *, temperature: float = 0.1) -> dict[str, Any]:
        content = "\n".join(message["content"] for message in messages)
        self.prompts.append(content)
        if "ResearchBrief" in content:
            return {
                "normalized_question": "Plot Sox17 in spatial view",
                "requested_analyses": ["gene_panel"],
                "requested_genes": ["Sox17"],
                "confidence": 0.82,
            }
        if "V2AnalysisPlan" in content:
            return {
                "research_question": "Plot Sox17 in spatial view",
                "rationale": "Use an existing embedding and plot the requested gene only.",
                "steps": [
                    {
                        "id": "gene_panel",
                        "tool": "plot_gene_panel",
                        "scientific_purpose": "Inspect Sox17 spatial expression.",
                        "params": {"genes": ["Sox17"], "expression_layer": "spatialscope_interpretation"},
                        "parameter_origins": {"genes": "user_query", "expression_layer": "agent_suggestion"},
                        "expected_evidence": ["spatial gene panel"],
                    }
                ],
            }
        if "Answer the user's current question" in content:
            if "main caveat" in content:
                return {
                    "direct_answer": "The main caveat is that this is exploratory figure evidence, not a cell-type call.",
                    "observations": ["Evidence is limited to the selected figure."],
                    "evidence_ids": ["execute_tool:plot_gene_panel:figure:0"],
                    "caveats": ["No mechanism is inferred."],
                    "next_step": "Compare with marker tables.",
                    "suggested_actions": [
                        {"action_id": "open_markers", "type": "open_marker_table", "label": "Open marker table", "payload": {}}
                    ],
                }
            return {
                "direct_answer": "The selected gene view supports cautious spatial-expression review.",
                "observations": ["The answer is grounded in the selected gene panel."],
                "evidence_ids": ["execute_tool:plot_gene_panel:figure:0"],
                "caveats": ["Bounded to the selected evidence."],
                "next_step": "Check cluster views.",
                "suggested_actions": [
                    {"action_id": "focus_cluster_2", "type": "highlight_cluster", "label": "Focus cluster 2", "payload": {"cluster": "2"}}
                ],
            }
        return {
            "summary": "The selected evidence supports cautious spatial exploration.",
            "caveats": ["No biological mechanism is inferred."],
            "suggested_next_steps": ["Check marker tables and QC warnings."],
        }


def _enable_mock_llm(monkeypatch) -> None:
    monkeypatch.setenv("SPATIALSCOPE_LLM_API_KEY", "sk-test")
    monkeypatch.setenv("SPATIALSCOPE_LLM_BASE_URL", "https://llm.example.test/v1")
    monkeypatch.setenv("SPATIALSCOPE_LLM_MODEL", "mock-structured")
    monkeypatch.setenv("SPATIALSCOPE_LLM_MODE", "full")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)


def test_gateway_structured_llm_path_records_telemetry_and_redacts_payloads(monkeypatch):
    _enable_mock_llm(monkeypatch)
    client = FakeStructuredClient()
    gateway = LLMGateway(client=client)
    dataset_profile = {
        "n_obs": 20,
        "n_vars": 5,
        "matrix_state": "log_normalized",
        "raw_matrix": [[1, 2], [3, 4]],
        "spatial_coordinates": [[index, index + 1] for index in range(20)],
    }

    brief = gateway.parse_research_brief(
        "Plot Sox17 in spatial view",
        mode="quick",
        dataset_profile=dataset_profile,
    )
    plan = gateway.propose_plan(
        brief,
        mode="quick",
        dataset_profile=dataset_profile,
        tool_contracts=[{"name": "plot_gene_panel"}],
    )

    assert brief.source == "llm"
    assert brief.requested_genes == ["Sox17"]
    assert plan.source == "llm"
    assert plan.steps[0].tool == "plot_gene_panel"
    assert [record["purpose"] for record in gateway.telemetry] == ["parse_research_brief", "propose_plan"]
    assert all(record["validation_outcome"] == "passed" for record in gateway.telemetry)
    combined_prompts = "\n".join(client.prompts)
    assert "[redacted matrix-like payload]" in combined_prompts
    assert "[[1, 2], [3, 4]]" not in combined_prompts
    assert "[[0, 1], [1, 2]" not in combined_prompts


def test_gateway_interpretation_uses_evidence_only_and_records_schema(monkeypatch):
    _enable_mock_llm(monkeypatch)
    client = FakeStructuredClient()
    gateway = LLMGateway(client=client)

    answer = gateway.synthesize_interpretation(
        query="Explain the figure",
        dataset_profile={"matrix_state": "log_normalized", "raw_matrix": [[9, 9]]},
        evidence_artifacts=[
            {
                "kind": "figure",
                "title": "Sox17 spatial expression",
                "caption": "Expression layer: spatialscope_interpretation.",
                "data_layer": "spatialscope_interpretation",
                "tool": "plot_gene_panel",
            }
        ],
        execution_trace=[{"node": "execute_tool", "tool": "plot_gene_panel", "status": "success"}],
        warnings=[],
    )

    assert answer is not None
    assert "Caveats:" in answer
    assert gateway.telemetry[-1]["purpose"] == "synthesize_interpretation"
    assert gateway.telemetry[-1]["validation_outcome"] == "passed"
    assert "[[9, 9]]" not in client.prompts[-1]


def test_contextual_copilot_questions_are_question_aware_and_cite_evidence(monkeypatch):
    _enable_mock_llm(monkeypatch)
    gateway = LLMGateway(client=FakeStructuredClient())
    context = {
        "title": "Sox17 spatial expression",
        "evidence_ids": ["execute_tool:plot_gene_panel:figure:0"],
        "selected_evidence": [{"caption": "Layer: spatialscope_interpretation"}],
    }

    caveat_answer = gateway.answer_contextual_question(context=context, question="What is the main caveat?")
    gene_answer = gateway.answer_contextual_question(context=context, question="What gene expression pattern is supported?")

    assert caveat_answer["answer"] != gene_answer["answer"]
    assert caveat_answer["evidence_ids"] == ["execute_tool:plot_gene_panel:figure:0"]
    assert gene_answer["evidence_ids"] == ["execute_tool:plot_gene_panel:figure:0"]
