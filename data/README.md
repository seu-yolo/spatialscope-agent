# Data

Do not commit large `.h5ad` files to GitHub.

Recommended workflow:

1. Generate tiny demo data:
   `python scripts/create_demo_data.py --output data/demo_tiny.h5ad`
2. Use the demo data for smoke tests and classroom demonstration.
3. Download the recommended real-data sample when you want a stronger demo:
   `scripts/download_real_demo.sh`

Real-data source:

- GEO accession: [GSE278603](https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE278603)
- Study: "Digital reconstruction of spatiotemporal atlas unveils the cellular
  origins and signaling networks underlying early mouse organogenesis"
- Organism: `Mus musculus`
- Platform context: Stereo-seq whole mouse embryos at E7.5, E7.75, and E8.0
- Official archive: `GSE278603_RAW.tar` from the NCBI GEO supplementary FTP area
- Local lightweight sample used for testing:
  `GSM9046244_Embryo_E7.5_stereo_rep2.h5ad`

The archive is about 803 MB. The extracted E7.5 replicate used by the demo is
about 31 MB and is ignored by Git. The source file stores spatial coordinates as
`adata.obsm["X_spatial"]`; SpatialScope normalizes that to `adata.obsm["spatial"]`
at load time.

Real-data smoke test:

```bash
python cli.py run \
  --data data/GSM9046244_Embryo_E7.5_stereo_rep2.h5ad \
  --query "Inspect this real E7.5 mouse embryo Stereo-seq spatial transcriptomics dataset. Run quick spatial analysis for Sox17, T, Mesp1 and Pou5f1, then summarize spatial structure and caveats." \
  --mode quick
```

Demo dataset requirements:

- valid spatial coordinates in `adata.obsm["spatial"]`
- sparse count matrix
- gene names suitable for query and fuzzy matching
- clustering and marker gene analysis should produce non-empty outputs
- small enough for Standard Mode to finish within several minutes
