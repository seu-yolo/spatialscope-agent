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

    genes = ["GeneA", "GeneB", "GeneC", "Sox17", "Mesp1", "Brachyury"]
    genes.extend([f"Gene{i:03d}" for i in range(n_genes - len(genes))])
    base = rng.poisson(1.2, size=(n_obs, n_genes)).astype(float)
    base[:, 0] += (coords[:, 0] < np.quantile(coords[:, 0], 0.35)) * rng.poisson(4, size=n_obs)
    base[:, 1] += (coords[:, 1] > np.quantile(coords[:, 1], 0.65)) * rng.poisson(4, size=n_obs)
    base[:, 2] += (clusters.astype(int) == 2) * rng.poisson(5, size=n_obs)
    base[:, 3] += (coords[:, 0] < np.quantile(coords[:, 0], 0.25)) * rng.poisson(5, size=n_obs)
    base[:, 4] += (clusters.astype(int) == 3) * rng.poisson(5, size=n_obs)
    base[:, 5] += (coords[:, 0] > np.quantile(coords[:, 0], 0.75)) * rng.poisson(5, size=n_obs)

    adata = ad.AnnData(
        X=sparse.csr_matrix(base),
        obs=pd.DataFrame({"demo_region": clusters}, index=[f"cell_{i:03d}" for i in range(n_obs)]),
        var=pd.DataFrame(index=genes),
    )
    adata.obsm["spatial"] = coords
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/demo_tiny.h5ad")
    parser.add_argument("--n-obs", type=int, default=240)
    parser.add_argument("--n-genes", type=int, default=80)
    args = parser.parse_args()
    create_demo_data(args.output, n_obs=args.n_obs, n_genes=args.n_genes)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()

