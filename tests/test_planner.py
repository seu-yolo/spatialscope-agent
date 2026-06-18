from spatialscope.agent.planner import fallback_parse_query, make_plan, merge_with_mode_baseline


def test_fallback_parser_extracts_genes():
    parsed = fallback_parse_query("Plot Sox17 and Mesp1 in spatial view", "quick")
    assert "Sox17" in parsed["genes"]
    assert "Mesp1" in parsed["genes"]


def test_fallback_parser_ignores_analysis_terms():
    parsed = fallback_parse_query("run standard spatial analysis with marker genes and GeneA GeneB panel", "standard")
    assert parsed["genes"] == ["GeneA", "GeneB"]


def test_fallback_parser_ignores_annotation_terms():
    parsed = fallback_parse_query(
        "Run standard spatial analysis with cautious cluster annotation suggestions and GeneA GeneB panel.",
        "standard",
    )
    assert parsed["genes"] == ["GeneA", "GeneB"]


def test_fallback_parser_ignores_storyboard_terms():
    parsed = fallback_parse_query(
        "Run quick spatial analysis and make a visual storyboard for GeneA GeneB",
        "quick",
    )
    assert parsed["genes"] == ["GeneA", "GeneB"]


def test_fallback_parser_ignores_replay_terms():
    parsed = fallback_parse_query(
        "Run quick spatial analysis and make a replayable rerun recipe for GeneA GeneB",
        "quick",
    )
    assert parsed["genes"] == ["GeneA", "GeneB"]


def test_fallback_parser_ignores_dataset_card_terms():
    parsed = fallback_parse_query(
        "Run quick spatial analysis and generate a dataset card for GeneA GeneB",
        "quick",
    )
    assert parsed["genes"] == ["GeneA", "GeneB"]


def test_make_advanced_plan_contains_showcase_tools():
    parsed = {"genes": ["Sox17"]}
    tools = [step["tool"] for step in make_plan(parsed, "advanced")]
    assert "run_svg" in tools
    assert "run_neighborhood_enrichment" in tools
    assert "plot_gene_panel" in tools
    assert "suggest_cluster_annotations" in tools


def test_merge_with_mode_baseline_adds_missing_standard_steps():
    proposed = [
        {
            "id": "only_qc",
            "tool": "run_qc",
            "params": {"min_genes": 10},
            "rationale": "LLM proposed a minimal plan.",
        }
    ]
    merged = merge_with_mode_baseline(proposed, {"genes": ["GeneA"]}, "standard")
    tools = [step["tool"] for step in merged]
    assert tools[:3] == ["run_qc", "run_preprocess", "run_clustering"]
    assert "rank_markers" in tools
    assert "suggest_cluster_annotations" in tools
    assert merged[0]["params"]["min_genes"] == 10
