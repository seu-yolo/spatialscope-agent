# SpatialScope Agent Grading Guide

This checklist maps likely course expectations to concrete browser-visible
evidence in the project.

## Requirement Mapping

| Requirement | SpatialScope implementation | Where to show it |
| --- | --- | --- |
| Spatial transcriptomics analysis | AnnData inspection, QC, preprocessing, PCA/UMAP/Leiden, marker ranking, spatial plots, gene panels | Streamlit Project -> Run -> Explore; `outputs/runs/<run_id>/report.html` |
| Agent workflow | LangGraph state machine with dataset inspection, plan review, execution, validation, repair, interpretation, report | Run page live execution events; `agent_trace.json` |
| LLM integration | OpenAI-compatible GLM 5.1 configuration, LLM research brief, Copilot, evidence-bounded interpretation | Advanced LLM status; Explore Copilot answers with evidence IDs |
| Human-in-the-loop control | Plan review before execution and review buttons on findings | Project plan review; Report finding review decisions |
| Scientific caution | Expression-source checks, evidence IDs, caveats, fallback labels, marker interpretation guardrails | Report findings and Copilot caveats |
| Visualization quality | Spatial + UMAP linked views, shared cluster palette, gene/layer controls, polished report figure ordering | Explore page and Report page |
| Reproducibility | `run_metadata.json`, `parameters.yaml`, `agent_trace.json`, dataset card, rerun recipe, bundle | Report downloads; Advanced / Provenance |
| Public deployment | GitHub repository, GitHub Pages, Streamlit Cloud app | README links and public URLs |
| Real data | GEO GSE278603 real-data download script and smoke-test command | README Demo Data section; `scripts/download_real_demo.sh` |
| GitHub management | CI, issue templates, PR template, license, citation, security, changelog | `.github/`, root metadata files, Actions badge |

## Recommended Live Demo Flow

1. Open https://spatialscope-seu.streamlit.app/.
2. Click `使用早期胚胎 Demo`.
3. Generate the dataset-aware plan.
4. Point out that the agent inspected 240 spots, 80 genes, spatial coordinates,
   and safe expression source before planning.
5. Approve the 7-step standard analysis plan.
6. On Run, show live LangGraph events and current-step details.
7. On Explore, show Spatial + UMAP side by side and ask two Copilot questions:
   - `哪个 cluster 的 Sox17 平均表达最高？`
   - `Pou5f1 的表达是否更像集中在某些 cluster？请给出证据和局限。`
8. Point out exact evidence IDs in Copilot answers.
9. Open Report and show 3-5 findings with evidence IDs and caveats.
10. Open Advanced only at the end to show provenance, LLM status, tool registry,
    and run library.

## Scoring Emphasis

- Do not present this as a simple Scanpy wrapper. Present it as an evidence
  workspace: every conclusion is linked to tool outputs.
- The most important browser-visible behaviors are data inspection before
  planning, live execution trace, linked visualization, evidence-grounded
  Copilot, and final report with caveats.
- Mention that real GEO data is supported locally but not committed to GitHub
  because `.h5ad` files are intentionally ignored.

