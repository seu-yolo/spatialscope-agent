from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Callable

from spatialscope.tools.annotation_tools import suggest_cluster_annotations
from spatialscope.tools.base import ToolContract, ToolResult
from spatialscope.tools.clustering_tools import run_clustering
from spatialscope.tools.marker_tools import rank_markers
from spatialscope.tools.neighborhood_tools import run_neighborhood_enrichment
from spatialscope.tools.preprocess_tools import run_preprocess
from spatialscope.tools.qc_tools import run_qc
from spatialscope.tools.spatial_tools import plot_gene_panel, plot_spatial, plot_umap
from spatialscope.tools.svg_tools import run_svg


ToolCallable = Callable[..., ToolResult]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    function: ToolCallable
    category: str
    description: str
    contract: ToolContract
    optional_dependency: str | None = None

    def public_dict(self) -> dict[str, object]:
        payload = {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "optional_dependency": self.optional_dependency,
            "contract": asdict(self.contract),
        }
        payload["contract"].pop("output_schema", None)  # type: ignore[index]
        return payload


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "run_qc": ToolSpec(
        name="run_qc",
        function=run_qc,
        category="quality_control",
        description="Calculate QC metrics, apply conservative filters, and write QC figure/table outputs.",
        contract=ToolContract(
            name="run_qc",
            required_fields=["adata"],
            optional_fields=["min_genes", "min_cells", "max_mt_pct"],
            preconditions=["AnnData object is loaded.", "Gene names are available in adata.var_names."],
            postconditions=["QC metrics exist in adata.obs.", "QC summary table and metric figure are written."],
            common_failures=["QC thresholds remove all observations.", "Scanpy is not installed."],
            repair_strategy=["Relax thresholds.", "Install the core conda environment."],
        ),
    ),
    "run_preprocess": ToolSpec(
        name="run_preprocess",
        function=run_preprocess,
        category="preprocessing",
        description="Normalize, log-transform, select highly variable genes, and scale with sparse-safe settings.",
        contract=ToolContract(
            name="run_preprocess",
            required_fields=["adata"],
            optional_fields=["n_top_genes"],
            preconditions=["QC has retained observations and genes."],
            postconditions=["adata.X is normalized/log transformed.", "adata.var['highly_variable'] is available when possible."],
            common_failures=["Dataset has too few genes after QC.", "Scanpy is not installed."],
            repair_strategy=["Reduce QC stringency.", "Lower n_top_genes.", "Install the core conda environment."],
        ),
    ),
    "run_clustering": ToolSpec(
        name="run_clustering",
        function=run_clustering,
        category="embedding_clustering",
        description="Compute PCA, neighbors, UMAP, and Leiden clusters.",
        contract=ToolContract(
            name="run_clustering",
            required_fields=["adata"],
            optional_fields=["resolution", "random_state"],
            preconditions=["Preprocessing has completed.", "At least a few observations and genes remain."],
            postconditions=["adata.obsm['X_umap'] and adata.obs['leiden'] are available."],
            common_failures=["Too few observations for neighbors.", "Leiden backend is missing."],
            repair_strategy=["Lower filtering thresholds.", "Install leidenalg/python-igraph or igraph backend."],
        ),
    ),
    "plot_umap": ToolSpec(
        name="plot_umap",
        function=plot_umap,
        category="visualization",
        description="Render a UMAP scatter plot colored by a categorical observation column.",
        contract=ToolContract(
            name="plot_umap",
            required_fields=["adata.obsm['X_umap']"],
            optional_fields=["color"],
            preconditions=["Clustering has generated UMAP coordinates.", "The requested color key exists in adata.obs."],
            postconditions=["A UMAP PNG is written to the run figure directory."],
            common_failures=["UMAP is missing.", "Color key is absent."],
            repair_strategy=["Run clustering before plotting.", "Use a valid obs column such as leiden."],
        ),
    ),
    "plot_spatial": ToolSpec(
        name="plot_spatial",
        function=plot_spatial,
        category="spatial_visualization",
        description="Render spatial coordinates colored by a cluster, observation column, or gene expression vector.",
        contract=ToolContract(
            name="plot_spatial",
            required_fields=["adata.obsm['spatial']"],
            optional_fields=["color"],
            preconditions=["Spatial coordinates exist in adata.obsm['spatial']."],
            postconditions=["A spatial PNG is written to the run figure directory."],
            common_failures=["Spatial coordinates are missing.", "Requested color key or gene is absent."],
            repair_strategy=["Use a dataset with spatial coordinates.", "Apply gene matching or choose a valid obs column."],
        ),
    ),
    "plot_gene_panel": ToolSpec(
        name="plot_gene_panel",
        function=plot_gene_panel,
        category="spatial_visualization",
        description="Render small-multiple spatial expression plots for requested genes with fuzzy gene matching.",
        contract=ToolContract(
            name="plot_gene_panel",
            required_fields=["adata.obsm['spatial']", "genes"],
            optional_fields=[],
            preconditions=["Spatial coordinates exist.", "At least one requested gene can be matched."],
            postconditions=["A gene panel PNG is written.", "Resolved gene names are recorded in observations."],
            common_failures=["No requested genes match the dataset.", "Spatial coordinates are missing."],
            repair_strategy=["Suggest closest gene names.", "Fall back to default demo genes for smoke tests."],
        ),
    ),
    "rank_markers": ToolSpec(
        name="rank_markers",
        function=rank_markers,
        category="differential_expression",
        description="Rank marker genes by cluster and export full/top marker tables.",
        contract=ToolContract(
            name="rank_markers",
            required_fields=["adata.obs[groupby]"],
            optional_fields=["groupby", "top_n"],
            preconditions=["A clustering column such as leiden exists."],
            postconditions=["Marker tables and a top-marker heatmap are written."],
            common_failures=["Cluster key is missing.", "Groups are too small for stable ranking."],
            repair_strategy=["Run clustering first.", "Use a valid grouping column."],
        ),
    ),
    "suggest_cluster_annotations": ToolSpec(
        name="suggest_cluster_annotations",
        function=suggest_cluster_annotations,
        category="interpretation_support",
        description="Suggest cautious cluster labels from top marker genes using a compact canonical marker lexicon.",
        contract=ToolContract(
            name="suggest_cluster_annotations",
            required_fields=["adata.obs[groupby]", "adata.uns['rank_genes_groups']"],
            optional_fields=["groupby", "top_n"],
            preconditions=["Marker ranking has completed.", "A clustering column such as leiden exists."],
            postconditions=["Candidate annotation table and confidence figure are written."],
            common_failures=["Marker rankings are missing.", "Markers do not overlap the compact lexicon."],
            repair_strategy=[
                "Run rank_markers first.",
                "Treat unresolved clusters as requiring manual/domain-specific review.",
            ],
        ),
    ),
    "run_svg": ToolSpec(
        name="run_svg",
        function=run_svg,
        category="advanced_spatial_statistics",
        description="Compute spatially variable genes using Squidpy spatial autocorrelation when available.",
        optional_dependency="squidpy",
        contract=ToolContract(
            name="run_svg",
            required_fields=["adata.obsm['spatial']"],
            optional_fields=["mode"],
            preconditions=["Squidpy is installed.", "Spatial coordinates exist."],
            postconditions=["SVG table and top-gene figure are written when Squidpy is available."],
            common_failures=["Squidpy is not installed.", "Spatial neighbor graph cannot be built."],
            repair_strategy=["Install environment-squidpy.yml.", "Skip gracefully in core demos."],
        ),
    ),
    "run_neighborhood_enrichment": ToolSpec(
        name="run_neighborhood_enrichment",
        function=run_neighborhood_enrichment,
        category="advanced_spatial_statistics",
        description="Compute cluster neighborhood enrichment using Squidpy when available.",
        optional_dependency="squidpy",
        contract=ToolContract(
            name="run_neighborhood_enrichment",
            required_fields=["adata.obsm['spatial']", "adata.obs[cluster_key]"],
            optional_fields=["cluster_key"],
            preconditions=["Squidpy is installed.", "Spatial coordinates and cluster labels exist."],
            postconditions=["Neighborhood enrichment heatmap/table are written when Squidpy is available."],
            common_failures=["Squidpy is not installed.", "Cluster key is missing."],
            repair_strategy=["Install environment-squidpy.yml.", "Run clustering first.", "Skip gracefully in core demos."],
        ),
    ),
}


def get_tool(name: str) -> ToolSpec:
    try:
        return TOOL_REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"Unknown SpatialScope tool: {name}") from exc


def available_tool_names() -> set[str]:
    return set(TOOL_REGISTRY)


def list_tool_contracts() -> list[dict[str, object]]:
    return [spec.public_dict() for spec in TOOL_REGISTRY.values()]


def tool_contract_summary() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for spec in TOOL_REGISTRY.values():
        rows.append(
            {
                "tool": spec.name,
                "category": spec.category,
                "description": spec.description,
                "optional_dependency": spec.optional_dependency or "",
                "preconditions": "; ".join(spec.contract.preconditions),
            }
        )
    return rows
