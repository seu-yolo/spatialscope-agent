from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


ASSET_DIR = Path(__file__).parent / "assets"
PREVIEW_PNG = ASSET_DIR / "landing_demo_preview.png"
PREVIEW_WEBP = ASSET_DIR / "landing_demo_preview.webp"


def preview_paths() -> dict[str, Path]:
    return {"png": PREVIEW_PNG, "webp": PREVIEW_WEBP}


def _dense(values: Any) -> np.ndarray:
    if hasattr(values, "toarray"):
        values = values.toarray()
    return np.ravel(np.asarray(values))


def generate_landing_preview(
    data_path: str | Path = "data/demo_embryo.h5ad",
    *,
    png_path: str | Path = PREVIEW_PNG,
    webp_path: str | Path = PREVIEW_WEBP,
) -> dict[str, Path]:
    """Create the deterministic landing evidence preview from the bundled demo."""

    import anndata as ad
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap

    from spatialscope.visualization.theme import CLUSTER_PALETTE, numeric_sort_key

    source = Path(data_path)
    if not source.exists():
        from spatialscope.utils.demo import ensure_demo_data

        ensure_demo_data(source)
    adata = ad.read_h5ad(source)
    if "spatial" not in adata.obsm:
        raise ValueError("Demo preview requires adata.obsm['spatial'].")

    coords = np.asarray(adata.obsm["spatial"])
    if "demo_region" in adata.obs:
        labels = adata.obs["demo_region"].astype(str)
    elif "leiden" in adata.obs:
        labels = adata.obs["leiden"].astype(str)
    else:
        labels = adata.obs.iloc[:, 0].astype(str)
    categories = sorted(labels.unique(), key=numeric_sort_key)
    palette = {cat: CLUSTER_PALETTE[i % len(CLUSTER_PALETTE)] for i, cat in enumerate(categories)}

    gene = "Sox17" if "Sox17" in adata.var_names else str(adata.var_names[0])
    gene_index = list(map(str, adata.var_names)).index(gene)
    values = _dense(adata.X[:, gene_index])
    finite = values[np.isfinite(values)]
    if finite.size:
        lo, hi = np.percentile(finite, [2, 98])
        values = np.clip(values, lo, hi)

    cmap = LinearSegmentedColormap.from_list("spatialscope_expression", ["#F7FAF9", "#CDE7E2", "#40988E", "#075A54"])
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 4.1), dpi=180)
    fig.patch.set_facecolor("#F4F5F2")
    for ax in axes:
        ax.set_facecolor("#FFFFFF")
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

    for category in categories:
        mask = np.asarray(labels == category)
        axes[0].scatter(
            coords[mask, 0],
            coords[mask, 1],
            s=22,
            c=palette[category],
            edgecolors="white",
            linewidths=0.28,
            alpha=0.94,
            label=category,
        )
    axes[0].set_title("Spatial regions", loc="left", fontsize=11, fontweight=650, color="#18201C", pad=8)

    scatter = axes[1].scatter(
        coords[:, 0],
        coords[:, 1],
        s=22,
        c=values,
        cmap=cmap,
        edgecolors="white",
        linewidths=0.28,
        alpha=0.95,
    )
    axes[1].set_title(f"{gene} signal", loc="left", fontsize=11, fontweight=650, color="#18201C", pad=8)
    cbar = fig.colorbar(scatter, ax=axes[1], fraction=0.046, pad=0.025)
    cbar.outline.set_visible(False)
    cbar.ax.tick_params(labelsize=7, colors="#737C76", length=0)

    handles, labels_out = axes[0].get_legend_handles_labels()
    if handles:
        legend = axes[0].legend(
            handles[:5],
            labels_out[:5],
            loc="lower left",
            bbox_to_anchor=(0.01, 0.01),
            frameon=True,
            facecolor="#FFFFFF",
            edgecolor="#DFE4E0",
            fontsize=7,
            markerscale=0.75,
            labelcolor="#414B46",
            borderpad=0.45,
        )
        legend.get_frame().set_linewidth(0.6)

    fig.subplots_adjust(left=0.035, right=0.985, bottom=0.035, top=0.92, wspace=0.085)
    png = Path(png_path)
    webp = Path(webp_path)
    png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(png, facecolor=fig.get_facecolor(), bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)

    try:
        from PIL import Image

        Image.open(png).save(webp, "WEBP", quality=92, method=6)
    except Exception:
        pass
    return {"png": png, "webp": webp}


def ensure_landing_preview(data_path: str | Path = "data/demo_embryo.h5ad") -> dict[str, Path]:
    if PREVIEW_PNG.exists():
        return preview_paths()
    return generate_landing_preview(data_path)
