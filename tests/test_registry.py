from spatialscope.tools.registry import available_tool_names, get_tool, list_tool_contracts


def test_registry_exposes_core_tools():
    tools = available_tool_names()
    assert "run_qc" in tools
    assert "plot_gene_panel" in tools
    assert "run_svg" in tools


def test_tool_contracts_are_prompt_safe():
    contracts = list_tool_contracts()
    assert contracts
    first = contracts[0]
    assert "name" in first
    assert "contract" in first
    assert "output_schema" not in first["contract"]


def test_get_tool_returns_callable():
    spec = get_tool("run_qc")
    assert callable(spec.function)
    assert spec.contract.name == "run_qc"
