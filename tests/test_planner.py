from spatialscope.agent.planner import fallback_parse_query, make_plan


def test_fallback_parser_extracts_genes():
    parsed = fallback_parse_query("Plot Sox17 and Mesp1 in spatial view", "quick")
    assert "Sox17" in parsed["genes"]
    assert "Mesp1" in parsed["genes"]


def test_make_advanced_plan_contains_showcase_tools():
    parsed = {"genes": ["Sox17"]}
    tools = [step["tool"] for step in make_plan(parsed, "advanced")]
    assert "run_svg" in tools
    assert "run_neighborhood_enrichment" in tools
    assert "plot_gene_panel" in tools

