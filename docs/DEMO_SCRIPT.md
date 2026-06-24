# SpatialScope Agent Demo Script

Use this script for classroom presentation or grading review.

## Public Links

- Live app: https://spatialscope-seu.streamlit.app/
- GitHub repo: https://github.com/seu-yolo/spatialscope-agent
- Static project site: https://seu-yolo.github.io/spatialscope-agent/

## Main Demo Flow

1. Open the live Streamlit app.
2. On Project, click `使用早期胚胎 Demo`.
3. Keep the default research question:

   ```text
   检查这个早期小鼠胚胎空间数据的质量，比较空间结构与 UMAP 聚类，并查看 Pou5f1、Sox17、T 和 Mesp1 的空间表达。总结主要观察和局限。
   ```

4. Click `检查数据并生成方案`.
5. Show that the agent inspected:
   - 240 spots
   - 80 genes
   - spatial coordinates
   - count-like expression source
   - requested genes: Pou5f1, Sox17, T, Mesp1
6. Click `继续查看方案`.
7. Show the 7-step plan:
   - QC
   - preprocessing
   - PCA / UMAP / Leiden
   - UMAP plot
   - spatial plot
   - gene panel
   - marker ranking
8. Click `批准并运行`.
9. On Run, show live LangGraph events, current-step details, parameters, and
   outputs. Emphasize that it is not a static spinner.
10. Click `打开探索工作区`.
11. On Explore, show Spatial + UMAP side by side with shared cluster colors.
12. Ask Copilot:

    ```text
    哪个 cluster 的 Sox17 平均表达最高？
    ```

13. Point out `Evidence IDs used: gene:Sox17:summary`.
14. Ask a second different question:

    ```text
    Pou5f1 的表达是否更像集中在某些 cluster？请给出证据和局限。
    ```

15. Point out that the answer changes and uses `gene:Pou5f1:summary`.
16. Open Report and show 5 findings with quantitative support, evidence IDs,
    caveats, and review buttons.
17. Open Advanced only at the end to show LLM status, tool registry, run library,
    trace, and provenance.

## Repair Demonstration

Use a misspelled gene in the Project question, for example:

```text
查看 Soxl7 和 Mespl 的空间表达，并总结可能的修复建议。
```

Expected behavior:

- The gene panel step should not silently invent a result.
- The tool should identify unresolved genes and propose close matches.
- The same step can be retried with repaired gene names.
- The trace/report should record the repair or clarification.

## Real Data Path

For local real-data evidence:

```bash
scripts/download_real_demo.sh
python cli.py run \
  --data data/GSM9046244_Embryo_E7.5_stereo_rep2.h5ad \
  --query "Inspect this real E7.5 mouse embryo Stereo-seq spatial transcriptomics dataset. Run quick spatial analysis for Sox17, T, Mesp1 and Pou5f1, then summarize spatial structure and caveats." \
  --mode quick
```

Large `.h5ad` files are intentionally not committed to GitHub.

