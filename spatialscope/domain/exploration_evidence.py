from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from spatialscope.domain.evidence import EvidencePack
from spatialscope.domain.expression_lineage import infer_matrix_state
from spatialscope.utils.gene_matching import match_gene_name
from spatialscope.visualization.theme import numeric_sort_key


def dense_vector(values: Any) -> np.ndarray:
    if hasattr(values, "toarray"):
        values = values.toarray()
    return np.ravel(np.asarray(values, dtype=float))


def safe_expression_sources(adata: Any) -> list[str]:
    layers = getattr(adata, "layers", {})
    sources: list[str] = []
    if "spatialscope_interpretation" in layers:
        sources.append("spatialscope_interpretation")
    if "counts" in layers:
        sources.append("counts")
    if getattr(adata, "raw", None) is not None:
        sources.append("raw")
    try:
        state = infer_matrix_state(adata.X).state
        if state in {"count_like", "log_normalized"}:
            sources.append("X")
    except Exception:
        pass
    return list(dict.fromkeys(sources))


def expression_vector(adata: Any, gene: str, expression_source: str) -> np.ndarray:
    if expression_source == "raw" and getattr(adata, "raw", None) is not None:
        return dense_vector(adata.raw[:, gene].X)
    var_names = list(map(str, adata.var_names))
    idx = var_names.index(gene)
    if expression_source != "X" and expression_source in getattr(adata, "layers", {}):
        return dense_vector(adata.layers[expression_source][:, idx])
    return dense_vector(adata.X[:, idx])


def resolve_gene(adata: Any, requested_gene: str) -> dict[str, Any]:
    match = match_gene_name(requested_gene, list(map(str, adata.var_names)))
    return {
        "requested_gene": requested_gene,
        "resolved_gene": match.get("match"),
        "match_method": "exact" if match.get("match") == requested_gene else "fuzzy" if match.get("match") else "unresolved",
        "match_score": match.get("score"),
        "candidates": match.get("candidates", []),
    }


def _series_stats(values: np.ndarray) -> dict[str, Any]:
    finite = values[np.isfinite(values)]
    if not len(finite):
        return {"mean": None, "median": None, "nonzero_fraction": None}
    return {
        "mean": round(float(np.mean(finite)), 5),
        "median": round(float(np.median(finite)), 5),
        "nonzero_fraction": round(float(np.mean(finite > 0)), 5),
    }


def _labels(adata: Any, cluster_key: str) -> pd.Series:
    if cluster_key in adata.obs:
        return adata.obs[cluster_key].astype(str)
    return pd.Series(["all"] * adata.n_obs, index=adata.obs_names, dtype=str)


def summarize_gene(
    adata: Any,
    gene: str,
    expression_source: str,
    cluster_key: str,
    selected_obs_ids: list[str] | None = None,
    clip_percentiles: tuple[float, float] = (1.0, 99.0),
) -> EvidencePack:
    resolved = resolve_gene(adata, gene)
    resolved_gene = resolved.get("resolved_gene")
    if not resolved_gene:
        return EvidencePack(
            evidence_id=f"gene:{gene}:unresolved",
            kind="gene",
            title=f"Gene evidence: {gene}",
            tool="explore_gene_summary",
            data_layer=expression_source,
            summary_metrics=resolved,
            parameters={"gene": gene, "cluster_key": cluster_key},
            caveats=["Requested gene could not be resolved safely."],
        )
    safe_sources = safe_expression_sources(adata)
    if expression_source not in safe_sources:
        return EvidencePack(
            evidence_id=f"gene:{resolved_gene}:unsafe_source",
            kind="gene",
            title=f"Gene evidence: {resolved_gene}",
            tool="explore_gene_summary",
            data_layer=expression_source,
            summary_metrics={**resolved, "safe_sources": safe_sources},
            parameters={"gene": gene, "cluster_key": cluster_key, "expression_source": expression_source},
            caveats=["Expression source is not safe for interpretation."],
        )
    values = expression_vector(adata, str(resolved_gene), expression_source)
    labels = _labels(adata, cluster_key)
    by_cluster: dict[str, dict[str, Any]] = {}
    for cluster in sorted(labels.unique(), key=numeric_sort_key):
        mask = np.asarray(labels == cluster)
        by_cluster[str(cluster)] = _series_stats(values[mask])
    top_clusters = sorted(
        by_cluster,
        key=lambda item: (-1 if by_cluster[item]["mean"] is None else -float(by_cluster[item]["mean"])),
    )[:3]
    selected_ids = [obs for obs in (selected_obs_ids or []) if obs in set(map(str, adata.obs_names))]
    selected_metrics: dict[str, Any] = {}
    if selected_ids:
        positions = pd.Index(list(map(str, adata.obs_names))).get_indexer(selected_ids)
        positions = positions[positions >= 0]
        selected_stats = _series_stats(values[positions])
        global_stats = _series_stats(values)
        selected_metrics = {
            "selected_count": int(len(positions)),
            "selected_mean": selected_stats["mean"],
            "selected_median": selected_stats["median"],
            "selected_nonzero_fraction": selected_stats["nonzero_fraction"],
            "global_mean": global_stats["mean"],
            "global_nonzero_fraction": global_stats["nonzero_fraction"],
            "selected_minus_global_mean": (
                round(float(selected_stats["mean"]) - float(global_stats["mean"]), 5)
                if selected_stats["mean"] is not None and global_stats["mean"] is not None
                else None
            ),
        }
    summary = {
        **resolved,
        "expression_source": expression_source,
        "global": _series_stats(values),
        "by_cluster": by_cluster,
        "top_clusters_by_mean": top_clusters,
        "clip_percentiles": list(clip_percentiles),
        **selected_metrics,
    }
    support = [
        {"cluster": cluster, **by_cluster[cluster]}
        for cluster in top_clusters
    ]
    return EvidencePack(
        evidence_id=f"gene:{resolved_gene}:summary",
        kind="gene",
        title=f"Gene evidence: {resolved_gene}",
        tool="explore_gene_summary",
        data_layer=expression_source,
        summary_metrics=summary,
        table_excerpt=support,
        parameters={"gene": gene, "cluster_key": cluster_key, "expression_source": expression_source},
        caveats=["Gene evidence is exploratory and depends on the selected expression source and clipping."],
    )


def summarize_cluster(
    adata: Any,
    cluster: str,
    cluster_key: str,
    selected_obs_ids: list[str] | None = None,
) -> EvidencePack:
    labels = _labels(adata, cluster_key)
    counts = labels.value_counts().sort_index()
    total = max(int(counts.sum()), 1)
    cluster = str(cluster)
    cluster_size = int(counts.get(cluster, 0))
    selected_ids = set(map(str, selected_obs_ids or []))
    cluster_mask = np.asarray(labels == cluster)
    selected_count = int(sum(obs in selected_ids for obs in map(str, adata.obs_names[cluster_mask])))
    summary = {
        "cluster_key": cluster_key,
        "cluster": cluster,
        "cluster_size": cluster_size,
        "cluster_fraction": round(cluster_size / total, 5),
        "selected_count": selected_count,
        "selected_fraction_in_cluster": round(selected_count / max(cluster_size, 1), 5),
        "cluster_sizes": {str(k): int(v) for k, v in counts.items()},
    }
    return EvidencePack(
        evidence_id=f"cluster:{cluster_key}:{cluster}:summary",
        kind="cluster",
        title=f"Cluster evidence: {cluster_key}={cluster}",
        tool="explore_cluster_summary",
        summary_metrics=summary,
        table_excerpt=[{"cluster": str(k), "n_obs": int(v), "fraction": round(int(v) / total, 5)} for k, v in counts.items()],
        parameters={"cluster_key": cluster_key, "cluster": cluster},
        caveats=["Cluster evidence is exploratory and does not assign cell identity by itself."],
    )


def summarize_selection(
    adata: Any,
    selected_obs_ids: list[str],
    selected_gene: str | None,
    expression_source: str | None,
    cluster_key: str,
) -> EvidencePack:
    selected = [obs for obs in selected_obs_ids if obs in set(map(str, adata.obs_names))]
    labels = _labels(adata, cluster_key)
    selected_set = set(selected)
    composition = labels[[obs in selected_set for obs in map(str, adata.obs_names)]].value_counts().to_dict()
    summary: dict[str, Any] = {
        "selected_count": len(selected),
        "cluster_composition": {str(k): int(v) for k, v in composition.items()},
        "cluster_key": cluster_key,
    }
    caveats = ["Selection statistics are based only on the observations selected in the browser session."]
    if selected and selected_gene and expression_source:
        gene_pack = summarize_gene(
            adata,
            selected_gene,
            expression_source,
            cluster_key,
            selected_obs_ids=selected,
        )
        summary.update({
            "selected_gene": gene_pack.summary_metrics.get("resolved_gene"),
            "expression_source": expression_source,
            "selected_mean": gene_pack.summary_metrics.get("selected_mean"),
            "global_mean": gene_pack.summary_metrics.get("global_mean"),
            "selected_minus_global_mean": gene_pack.summary_metrics.get("selected_minus_global_mean"),
            "selected_nonzero_fraction": gene_pack.summary_metrics.get("selected_nonzero_fraction"),
            "global_nonzero_fraction": gene_pack.summary_metrics.get("global_nonzero_fraction"),
        })
        caveats.extend(gene_pack.caveats)
    return EvidencePack(
        evidence_id="selection:browser:summary",
        kind="selection",
        title="Selection evidence",
        tool="explore_selection_summary",
        data_layer=expression_source,
        summary_metrics=summary,
        table_excerpt=[{"cluster": str(k), "selected_obs": int(v)} for k, v in composition.items()],
        parameters={"cluster_key": cluster_key, "selected_gene": selected_gene or ""},
        caveats=caveats,
    )
