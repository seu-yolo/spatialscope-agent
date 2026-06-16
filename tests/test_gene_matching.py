from spatialscope.utils.gene_matching import match_gene_name


def test_exact_gene_match():
    result = match_gene_name("Sox17", ["Sox17", "Mesp1"])
    assert result["match"] == "Sox17"
    assert result["score"] == 100.0


def test_case_insensitive_gene_match():
    result = match_gene_name("sox17", ["Sox17", "Mesp1"])
    assert result["match"] == "Sox17"
    assert result["score"] >= 98.0


def test_fuzzy_gene_match_returns_candidate():
    result = match_gene_name("Soxl7", ["Sox17", "Mesp1"])
    assert result["match"] in {"Sox17", "Mesp1"}
    assert result["candidates"]

