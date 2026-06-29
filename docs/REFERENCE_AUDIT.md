# Reference Authenticity Audit

Verification date: 2026-06-29

This file records the sources checked for the final report and presentation. The goal is to keep the project references traceable to official documentation, journal pages, PubMed/PMC records, DOI landing pages, or NCBI GEO.

## Verified References

| Reference | Status | Verification source | Notes |
|---|---|---|---|
| Wolf, Angerer, Theis. Scanpy: large-scale single-cell gene expression data analysis. Genome Biology 19(1), 15 (2018). DOI: 10.1186/s13059-017-1382-0 | Verified | PubMed, Springer/Genome Biology, Scanpy docs references, Crossref | Supports use of Scanpy for preprocessing, visualization, clustering and scalable single-cell analysis. |
| Palla et al. Squidpy: a scalable framework for spatial omics analysis. Nature Methods 19(2), 171-178 (2022). DOI: 10.1038/s41592-021-01358-2 | Verified | Nature Methods, PubMed, Squidpy docs references | Supports Squidpy spatial graph/statistics/image workflow framing. |
| Virshup et al. anndata: Access and store annotated data matrices. JOSS 9(101), 4371 (2024). DOI: 10.21105/joss.04371 | Verified | Journal of Open Source Software, AnnData docs | Supports AnnData as the annotated matrix/storage layer used by Scanpy-style workflows. |
| Righelli et al. SpatialExperiment: infrastructure for spatially-resolved transcriptomics data in R using Bioconductor. Bioinformatics 38(11), 3128-3131 (2022). DOI: 10.1093/bioinformatics/btac299 | Verified | Oxford Academic search result, PMC, Bioconductor | Supports the broader claim that spatial transcriptomics needs explicit data infrastructure for coordinates, images and metadata. Direct DOI/Oxford script access may return HTTP 403, but the PMC record is open and verifies the citation metadata. |
| Crowell et al. Orchestrating spatial transcriptomics analysis with Bioconductor. bioRxiv (2025). DOI: 10.1101/2025.11.20.688607; OSTA online book | Verified | Bioconductor book site, OSTA citation appendix | Supports the standard workflow framing: data structure, QC, intermediate processing and downstream spatial analysis. |
| LangGraph documentation | Verified | LangChain official docs | Current official overview URL is `https://docs.langchain.com/oss/python/langgraph/overview`; it describes durable execution, streaming, human-in-the-loop and persistence. |
| Streamlit documentation | Verified | Streamlit official docs | Supports the public app and interactive workspace implementation. |
| NCBI GEO Series GSE278603: Digital reconstruction of spatiotemporal atlas unveils the cellular origins and signaling networks underlying early mouse organogenesis | Verified | NCBI GEO accession viewer | Public on 2025-06-19; contains six mouse embryo samples including `GSM9046244 embryo E7.5 rep2`; supplementary archive is `GSE278603_RAW.tar` containing H5AD resources. GEO page currently displays "Citation missing", so the report treats the Cell paper as the corresponding research background rather than claiming GEO has already linked the citation. |
| Xie, Shen, Yang et al. Digital reconstruction of full embryos during early mouse organogenesis. Cell 188(17), 4754-4772.e18 (2025). DOI: 10.1016/j.cell.2025.05.035 | Verified | Cell Press / DOI search / PubMed search result / Crossref metadata | Supports the biological background for the digital embryo dataset and the presentation narrative. |

## Reporting Decision

The final report now cites both method references and data references. For GSE278603, the wording is intentionally cautious: SpatialScope uses the public GEO series as a real-data smoke test and cites the Cell paper as the matching research background. This avoids overstating the GEO citation metadata while still documenting why the dataset is biologically relevant.
