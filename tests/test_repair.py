from spatialscope.agent.repair import diagnose_tool_failure
from spatialscope.tools.registry import get_tool


def test_repair_diagnoses_optional_missing_dependency():
    spec = get_tool("run_svg")
    diagnosis = diagnose_tool_failure(
        {"id": "svg", "tool": "run_svg", "params": {"mode": "moran"}, "optional": True},
        {
            "status": "failed",
            "summary": "run_svg failed: No module named 'squidpy'",
            "errors": ["ModuleNotFoundError: No module named 'squidpy'"],
        },
        spec.contract,
        optional_dependency=spec.optional_dependency,
    )
    assert diagnosis["category"] == "missing_dependency"
    assert diagnosis["action"] == "skip_optional_step"
    assert diagnosis["optional"] is True
    assert "squidpy" in " ".join(diagnosis["recommended_actions"]).lower()


def test_repair_diagnoses_missing_spatial_coordinates():
    spec = get_tool("plot_spatial")
    diagnosis = diagnose_tool_failure(
        {"id": "spatial", "tool": "plot_spatial", "params": {"color": "leiden"}},
        {
            "status": "failed",
            "summary": "plot_spatial failed: spatial coordinates are missing",
            "errors": ["KeyError: adata.obsm['spatial'] not found"],
        },
        spec.contract,
    )
    assert diagnosis["category"] == "missing_spatial_coordinates"
    assert diagnosis["action"] == "skip_failed_step"
    assert diagnosis["optional"] is False
