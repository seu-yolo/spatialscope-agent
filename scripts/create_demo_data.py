from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def create_demo_data(output: str, *, n_obs: int = 240, n_genes: int = 80, seed: int = 0) -> None:
    try:
        import anndata as ad
        import pandas as pd
        from scipy import sparse
    except Exception as exc:
        raise RuntimeError(
            "Demo data generation requires anndata, pandas, and scipy. "
            "Create the conda environment first: conda env create -f environment.yml"
        ) from exc

    rng = np.random.default_rng(seed)
    coords = rng.normal(size=(n_obs, 2))
    coords[:, 0] += np.repeat(np.linspace(-4, 4, 6), n_obs // 6 + 1)[:n_obs]
    clusters = np.digitize(coords[:, 0], bins=np.quantile(coords[:, 0], [0.2, 0.4, 0.6, 0.8])).astype(str)

    genes = ["Pou5f1", "Sox2", "Nanog", "Sox17", "Gata6", "T", "Mesp1", "Eomes", "Foxa2", "Lefty2"]
    genes.extend([f"Gene{i:03d}" for i in range(n_genes - len(genes))])
    base = rng.poisson(1.2, size=(n_obs, n_genes)).astype(float)
    cluster_int = clusters.astype(int)
    base[:, 0] += (cluster_int <= 1) * rng.poisson(5, size=n_obs)  # Pou5f1 pluripotent epiblast-like core
    base[:, 1] += (coords[:, 1] > np.quantile(coords[:, 1], 0.55)) * rng.poisson(4, size=n_obs)  # Sox2
    base[:, 2] += (cluster_int == 1) * rng.poisson(5, size=n_obs)  # Nanog
    base[:, 3] += (coords[:, 0] < np.quantile(coords[:, 0], 0.25)) * rng.poisson(6, size=n_obs)  # Sox17 endoderm-like edge
    base[:, 4] += (coords[:, 0] < np.quantile(coords[:, 0], 0.35)) * rng.poisson(5, size=n_obs)  # Gata6 primitive endoderm-like
    base[:, 5] += (coords[:, 0] > np.quantile(coords[:, 0], 0.70)) * rng.poisson(6, size=n_obs)  # T / primitive streak-like
    base[:, 6] += (cluster_int >= 3) * rng.poisson(5, size=n_obs)  # Mesp1 mesoderm-like
    base[:, 7] += (cluster_int == 4) * rng.poisson(4, size=n_obs)  # Eomes
    base[:, 8] += (coords[:, 0] < np.quantile(coords[:, 0], 0.20)) * rng.poisson(3, size=n_obs)  # Foxa2
    base[:, 9] += (coords[:, 1] < np.quantile(coords[:, 1], 0.30)) * rng.poisson(3, size=n_obs)  # Lefty2

    adata = ad.AnnData(
        X=sparse.csr_matrix(base),
        obs=pd.DataFrame(
            {
                "demo_region": clusters,
                "embryo_zone": np.where(cluster_int <= 1, "epiblast_like", np.where(cluster_int >= 3, "mesoderm_like", "transition")),
            },
            index=[f"cell_{i:03d}" for i in range(n_obs)],
        ),
        var=pd.DataFrame(index=genes),
    )
    adata.obsm["spatial"] = coords
    adata.uns["organism"] = "Mus musculus"
    adata.uns["technology"] = "synthetic spatial transcriptomics"
    adata.uns["development_stage"] = "early embryo demo"
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/demo_embryo.h5ad")
    parser.add_argument("--n-obs", type=int, default=240)
    parser.add_argument("--n-genes", type=int, default=80)
    args = parser.parse_args()
    create_demo_data(args.output, n_obs=args.n_obs, n_genes=args.n_genes)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
