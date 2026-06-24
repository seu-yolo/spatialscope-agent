from spatialscope.utils.visual_priority import prioritize_visual_records


def test_visual_evidence_prioritizes_spatial_umap_gene_panel_before_qc():
    records = [
        {"title": "QC metric distributions", "path": "figures/qc_metrics.png"},
        {"title": "Highly variable genes", "path": "figures/highly_variable_genes.png"},
        {"title": "Gene Panel Spatial View", "path": "figures/gene_panel_spatial.png"},
        {"title": "UMAP by leiden", "path": "figures/umap_leiden.png"},
        {"title": "Spatial view: leiden", "path": "figures/spatial_leiden.png"},
        {"title": "Marker expression heatmap", "path": "figures/marker_expression_heatmap.png"},
    ]

    ordered = prioritize_visual_records(records)

    assert [item["title"] for item in ordered[:3]] == [
        "Spatial view: leiden",
        "UMAP by leiden",
        "Gene Panel Spatial View",
    ]
    assert ordered[-1]["title"] == "QC metric distributions"
