from __future__ import annotations

import pandas as pd

from spatialscope.tools.annotation_tools import suggest_cluster_annotations


class FakeAdata:
    def __init__(self) -> None:
        self.obs = pd.DataFrame({"leiden": ["0", "0", "1", "1"]})
        self.uns = {
            "rank_genes_groups": {
                "names": {
                    "0": ["CD3D", "TRAC", "IL7R", "GeneX"],
                    "1": ["PECAM1", "VWF", "CLDN5", "GeneY"],
                }
            }
        }


def test_suggest_cluster_annotations_from_ranked_markers(tmp_path):
    result = suggest_cluster_annotations(
        FakeAdata(),
        tables_dir=str(tmp_path),
        figures_dir=str(tmp_path),
        groupby="leiden",
        top_n=4,
        reference="generic_marker_lexicon",
    )

    assert result.status == "success"
    assert "T cell-like" in result.summary
    assert "Endothelial-like" in result.summary
    assert (tmp_path / "cluster_annotation_suggestions.csv").exists()
    assert (tmp_path / "cluster_annotation_suggestions.png").exists()
    assert "marker_evidence_score" in result.observations["cluster_annotation_suggestions"][0]
