import pytest

from spatialscope.agent.schemas import AnalysisPlan, ParsedRequest, normalize_plan_steps


def test_parsed_request_coerces_gene_string():
    parsed = ParsedRequest.model_validate({"genes": "GeneA, GeneB", "preferred_mode": "standard"})
    assert parsed.genes == ["GeneA", "GeneB"]
    assert parsed.preferred_mode == "standard"


def test_analysis_plan_rejects_duplicate_step_ids():
    with pytest.raises(ValueError):
        AnalysisPlan(
            mode="quick",
            steps=[
                {"id": "qc", "tool": "run_qc", "params": {}},
                {"id": "qc", "tool": "run_preprocess", "params": {}},
            ],
        )


def test_normalize_plan_rejects_unknown_tool():
    with pytest.raises(ValueError):
        normalize_plan_steps([{"id": "bad", "tool": "missing_tool", "params": {}}], allowed_tools={"run_qc"})
