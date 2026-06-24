# SpatialScope Agent Submission Checklist

This checklist is aligned with the course assignment document
`计算生物学期末大作业.docx`.

## Deadlines

| Deadline | Required item | Current status | Next action |
| --- | --- | --- | --- |
| 2026-06-25 20:00 | GitHub repository link | Ready: `https://github.com/seu-yolo/spatialscope-agent` | Submit the repository link by email before the deadline. |
| 2026-06-26 12:00 | Deployment link, optional but recommended | Ready: `https://spatialscope-seu.streamlit.app/`; GitHub Pages also ready | Re-test Streamlit app before submitting the deployment link. |
| 2026-06-26 24:00 | Final report in Word or PDF | Draft exists in `reports/SPATIALSCOPE_FINAL_REPORT_DRAFT.md` | Convert the draft into a polished Word/PDF report with figures and screenshots. |
| 2026-06-27 afternoon | Classroom presentation with live demo | Demo script exists in `docs/DEMO_SCRIPT.md` | Build a PPT and rehearse a 5-7 minute demo. |

## Assignment Requirements Mapping

| Requirement | Evidence in this project | Status |
| --- | --- | --- |
| Use LangGraph as the core Agent framework | `spatialscope/agent/graph.py`, live Run page events, checkpointed plan review | Done |
| Node design: task understanding, planning, tools, interpretation, errors | Agent graph nodes and `agent_trace.json` | Done |
| Conditional edges and flow control | Plan approval, repair, validation, and continuation logic | Done |
| State/Memory management | `spatialscope/agent/state.py`, run metadata, trace, public state bundle | Done |
| Loop design: plan-execute-check-repair | `repair_or_continue` and validation flow | Done |
| Prompt design | `spatialscope/llm/prompts.py`, LLM guardrails and evidence-bound interpretation | Done |
| Tool design | Tool registry and analysis tools under `spatialscope/tools/` | Done |
| Skill/Workflow packaging | Quick, Standard, Advanced workflows and reusable tool contracts | Done |
| Natural-language user input | Project page query input and CLI `--query` | Done |
| Read `.h5ad` and summarize obs/var | IO inspection and dataset card | Done |
| QC filtering and QC plots | QC tools and generated QC figures/tables | Done |
| Preprocessing: normalize, log1p, HVG, scale | Preprocess tools | Done |
| PCA/UMAP/Leiden or Louvain | Clustering tools | Done |
| Cluster annotation suggestions | Marker-based candidate annotations | Done |
| Spatial visualization | Spatial cluster and gene expression plots | Done |
| Marker gene analysis | Marker tools and marker tables/heatmaps | Done |
| Result interpretation without fabrication | Evidence IDs, caveats, and LLM guardrails | Done |
| Figures for analysis results | Report and Explore pages | Done |
| Spatial neighborhood analysis | Optional Squidpy-backed tool with graceful fallback | Partial / extension |
| SVG identification | Optional Squidpy-backed tool with graceful fallback | Partial / extension |
| Cell communication | Roadmap only | Not in v1 |
| Automatic report generation | HTML report and report draft | Done |
| Frontend interaction | Streamlit app with Project, Run, Explore, Report, Advanced | Done |
| Different spatial technologies | AnnData-compatible loader; Stereo-seq demo; broader format support described | Partial |
| GitHub repo with code, README, environment, commands, data instructions | README, env files, scripts, data docs, CI | Done |
| Online deployment link in GitHub | README and GitHub Pages include Streamlit app link | Done |

## Highest-Priority Remaining Work

1. Prepare final report as Word/PDF.
2. Run and save one real-data demo result using `GSM9046244_Embryo_E7.5_stereo_rep2.h5ad`.
3. Create a PPT for the 2026-06-27 classroom presentation.
4. Re-test the public Streamlit app after every push.
5. Submit repository and deployment links by email with subject `姓名+学号`.

