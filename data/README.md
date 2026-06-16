# Data

Do not commit large `.h5ad` files to GitHub.

Recommended workflow:

1. Generate tiny demo data:
   `python scripts/create_demo_data.py --output data/demo_tiny.h5ad`
2. Use the demo data for smoke tests and classroom demonstration.
3. Download the full recommended assignment dataset separately if needed:
   GSE278603, "Digital reconstruction of full embryos during early mouse organogenesis".

Demo dataset requirements:

- valid spatial coordinates in `adata.obsm["spatial"]`
- sparse count matrix
- gene names suitable for query and fuzzy matching
- clustering and marker gene analysis should produce non-empty outputs
- small enough for Standard Mode to finish within several minutes

