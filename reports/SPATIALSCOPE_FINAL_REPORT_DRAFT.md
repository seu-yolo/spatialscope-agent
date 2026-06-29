# SpatialScope Agent：面向空间转录组的证据驱动分析智能体

## 摘要

SpatialScope Agent 是一个面向空间转录组数据分析的交互式科研智能体。项目以
Streamlit 为产品界面，以 LangGraph 组织 Agent 工作流，以 Scanpy/Squidpy
风格的确定性工具执行分析，并通过 OpenAI-compatible LLM 接口接入 GLM 5.1
用于自然语言理解、方案生成、结果解释和上下文 Copilot。系统强调三个原则：
先检查数据再规划，先生成证据再解释，所有结论都绑定 evidence IDs 和 caveats。

项目已经部署为公开交互式网页：

- Streamlit App: https://spatialscope-seu.streamlit.app/
- GitHub Repository: https://github.com/seu-yolo/spatialscope-agent
- Static Project Site: https://seu-yolo.github.io/spatialscope-agent/

## 1. 背景与问题

空间转录组数据同时包含表达矩阵与空间坐标，分析过程通常涉及质量控制、
归一化、降维聚类、空间可视化、marker 基因解释和报告生成。传统 notebook
工作流虽然灵活，但存在以下问题：

- 分析步骤分散，参数和中间结果难以追踪。
- 用户的问题往往是自然语言，而工具调用需要结构化参数。
- 图表和解释容易脱节，结论缺少证据编号和局限说明。
- LLM 直接接触大矩阵存在隐私、成本和幻觉风险。

SpatialScope Agent 的目标不是替代生物学判断，而是把空间组学分析整理成一个
可审阅、可复现、可展示的证据工作台。

## 2. 系统目标

本项目的核心目标包括：

1. 用自然语言启动空间转录组分析任务。
2. 在执行前自动检查 AnnData 数据结构、空间坐标和表达层安全性。
3. 生成可审阅的结构化分析计划，并允许用户批准后再运行。
4. 用确定性工具完成 QC、预处理、UMAP/Leiden、空间图、基因面板和 marker 排名。
5. 通过 LLM 只基于工具摘要和 evidence packs 进行解释，不传入原始表达矩阵。
6. 在 Explore 页面提供 Spatial + UMAP 联动视图和 evidence-grounded Copilot。
7. 自动生成包含 findings、证据、局限和可复现文件的 Research Brief。
8. 用 evidence IDs 与 schema validation 约束 LLM 输出，使解释可追踪、计划可执行。

## 3. Agent 架构

系统采用 LangGraph 构建状态机：

```text
inspect_dataset -> parse_request -> plan_analysis -> review_plan
-> execute_tool -> validate_result -> repair_or_continue
-> interpret -> report
```

状态中保存 `run_id`、`dataset_hash`、`task_plan`、`approved_plan`、
参数、figures、tables、warnings、errors、execution trace 和环境信息。
真正的大型对象 AnnData 不进入公共状态；运行时只保存工作副本路径和摘要。

### 3.1 数据检查优先

在生成最终计划前，Agent 会先读取数据规模、基因数、空间坐标、表达矩阵状态、
可用 obs/obsm 字段和候选基因匹配结果。这样可以避免“还不知道数据是否可用就
直接解释”的常见问题。

### 3.2 Human-in-the-loop

Streamlit Project 页面会展示分析契约，包括每一步的目的、参数、预期产物和方法
边界。用户批准后才进入执行；这使 Agent 更像一个可审阅的研究助手，而不是黑箱
脚本。

### 3.3 Repair 与 Clarification

当基因名拼写错误或工具参数不安全时，系统不会直接生成错误结论，而是进入
clarification / repair flow。例如基因名未匹配时，工具会返回候选基因；
空间图 color 参数错误时，repair 节点会尝试使用可用 cluster 字段重试。

## 4. LLM 设计与安全边界

项目使用 OpenAI-compatible LLM 接口，部署配置为 GLM 5.1。LLM 负责：

- 解析自然语言研究问题。
- 生成 ResearchBrief 和分析计划建议。
- 基于 evidence packs 回答 Copilot 问题。
- 基于工具摘要生成谨慎的结果解释。

LLM 不负责：

- 直接读取完整表达矩阵。
- 直接读取完整空间坐标矩阵。
- 替代 Scanpy/Squidpy 的确定性计算。
- 在没有证据 ID 的情况下生成最终结论。

这种设计把 LLM 放在“理解、组织、解释”的位置，把数值计算交给可复现工具。

### 4.1 Evidence IDs 与 Schema 校验

Evidence ID 是系统为图、表、指标和交互式摘要生成的证据编号，例如
`execute_tool:plot_umap:figure:0`、`execute_tool:rank_markers:table:0`
或 `gene:Sox17:summary`。Copilot 与 Report 中的结论必须显示使用过的
evidence IDs，使用户能够从一句解释反查到具体图表、表格或工具输出。

LLM prompt 按 Agent 阶段拆分为 ResearchBrief、V2AnalysisPlan、
RepairDecision、ScientificFinding 和 CopilotAnswer 等结构化输出。模型返回的
JSON 会经过 Pydantic schema 校验；计划步骤还会与工具注册表匹配，finding 还会检查
引用的 evidence IDs 是否真实存在。若输出格式错误、证据不足或引用不存在，系统会记录
telemetry 并切换到确定性 fallback，而不是把自由文本直接交给执行器。

## 5. 分析功能

当前版本实现了以下核心分析能力：

- AnnData `.h5ad` 数据读取与空间坐标标准化。
- QC 指标计算与过滤摘要。
- 归一化、log1p、HVG、scale 等预处理。
- PCA、邻接图、UMAP 和 Leiden 聚类。
- 空间 cluster 图。
- 空间基因表达图和多基因 panel。
- marker gene ranking 与 marker heatmap。
- gene fuzzy matching 与修复建议。
- 可选 SVG / neighborhood enrichment 扩展。
- HTML report、metadata、trace、parameters、figures、tables 和 bundle 输出。

## 6. 可视化与产品体验

项目主界面压缩为四个主要页面：

- Project：选择数据、提出问题、生成并审阅计划。
- Run：实时显示 LangGraph 节点事件、当前工具、参数和产物数量。
- Explore：并排展示 Spatial 与 UMAP 视图，共享 cluster 颜色，支持基因、cluster、
  expression layer 和 percentile clipping 控制。
- Report：显示 3-5 条 evidence-linked findings，每条包含 quantitative support、
  evidence IDs、caveats 和人工审阅按钮。

Advanced / Provenance 页面集中放置 LLM 状态、tool registry、run library、trace、
audits 和原始 public state，避免干扰主研究流程。

## 7. Demo 数据与真实数据

为了保证在线展示稳定，项目内置一个小型 synthetic early embryo spatial demo，
包含早期小鼠胚胎相关基因，例如 Pou5f1、Sox17、T、Mesp1、Gata6、Eomes 等。
该 demo 用于展示完整 Agent 流程，不被解释为真实生物发现。

项目还提供真实数据下载脚本：

```bash
scripts/download_real_demo.sh
```

该脚本从 NCBI GEO GSE278603 下载官方补充文件，并提取
`GSM9046244_Embryo_E7.5_stereo_rep2.h5ad`。真实样本约 31 MB，包含 8190 spots、
16364 genes 和空间坐标。大型 `.h5ad` 文件被 `.gitignore` 排除，避免污染仓库。

## 8. 结果与验证

在线 demo 的标准运行会生成：

- 6 张左右 figures。
- 4 张左右 tables。
- 10 个左右 LangGraph trace events。
- `report.html` Research Brief。
- `run_metadata.json`、`agent_trace.json`、`parameters.yaml`。
- dataset card、storyboard、rerun recipe 和 run bundle。

在 Explore 页面中，Copilot 能基于当前证据回答问题，并显示使用的 evidence IDs。
例如：

- Sox17 最高表达 cluster 问题使用 `gene:Sox17:summary`。
- Pou5f1 cluster 分布问题使用 `gene:Pou5f1:summary`。

这说明 LLM 输出不是静态文本，而是依赖当前选择的基因、表达层、cluster 和 evidence
pack。

## 9. GitHub 与部署

仓库采用标准开源项目组织方式：

- CI workflow：自动运行测试和 CLI smoke demo。
- Issue templates：bug report 与 feature request。
- PR template：包含科学边界与验证清单。
- LICENSE：MIT。
- SECURITY.md：说明 secret 和数据安全边界。
- CITATION.cff：方便软件引用。
- CHANGELOG.md：记录课程提交版本变化。
- GitHub Pages：静态项目首页。
- Streamlit Cloud：公开交互式 Agent。

## 10. 创新性

本项目的创新性不在于提出新的聚类算法，而在于把成熟的空间转录组分析流程重构成
一个可审阅、可修复、证据约束、可部署的科研 Agent。与固定 Scanpy notebook 相比，
SpatialScope 把一次性脚本执行变成了围绕数据、计划、工具、证据和解释持续流动的研究工作台。

可以概括为：

- 标准空间转录组流程被显式 Agent 化：数据检查、计划审阅、执行、校验、修复、解释和报告都有状态记录。
- LLM 被限制在 evidence pack 与 schema validation 内，不接触完整矩阵，不生成无证据结论。
- Copilot 和 Report 必须显示 exact evidence IDs，使解释能反查到具体图、表或统计摘要。
- 表达层安全检查阻止把 scaled 或 unknown matrix state 当作可靠表达来源解释。
- 浏览器端 Project、Run、Explore、Report 让用户能真正体验 Agent 行为，而不是只看到代码或 JSON。

## 11. 局限性

当前版本仍有以下限制：

- 在线 demo 主要使用 synthetic 数据，真实 GEO 数据建议本地运行。
- marker ranking 是候选差异表达线索，不等同于确定细胞类型注释。
- 高级方法如 STAGATE、GraphST、Tangram、cell2location、LIANA/COMMOT 仍属于路线图。
- Streamlit Community Cloud 对大型空间组学数据的内存和启动时间有限。
- LLM 解释依赖 evidence pack 质量，不能替代人工生物学审阅。

## 12. 未来工作

后续可以扩展：

- 引入更强的空间可变基因算法和空间邻域统计。
- 支持真实数据示例的轻量在线缓存或远程加载。
- 增加细胞类型注释数据库和 marker ontology 映射。
- 支持多 run 对比和参数敏感性分析。
- 将报告导出为 PDF / Word 版本，便于课程提交。

## 13. 致谢

We gratefully acknowledge Professor Peng Xie from the School of Biological
Science and Medical Engineering, Southeast University. We also thank Teaching
Assistant Binyu Gao for guidance and support throughout the course project.

## 参考资料

- Wolf, F. A., Angerer, P., and Theis, F. J. Scanpy: large-scale single-cell gene expression data analysis. Genome Biology 19, 15 (2018). https://doi.org/10.1186/s13059-017-1382-0
- Palla, G. et al. Squidpy: a scalable framework for spatial omics analysis. Nature Methods 19, 171-178 (2022). https://doi.org/10.1038/s41592-021-01358-2
- Virshup, I. et al. anndata: Access and store annotated data matrices. Journal of Open Source Software 9(101), 4371 (2024). https://doi.org/10.21105/joss.04371
- Righelli, D. et al. SpatialExperiment: infrastructure for spatially-resolved transcriptomics data in R using Bioconductor. Bioinformatics 38(11), 3128-3131 (2022). https://doi.org/10.1093/bioinformatics/btac299
- OSTA: https://www.bioconductor.org/books/OSTA/
- Scanpy documentation: https://scanpy.readthedocs.io/
- AnnData documentation: https://anndata.readthedocs.io/
- Squidpy documentation: https://squidpy.readthedocs.io/
- LangGraph documentation: https://docs.langchain.com/oss/python/langgraph/overview
- Streamlit documentation: https://docs.streamlit.io/
- NCBI GEO GSE278603: https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=GSE278603
- Xie, P., Shen, J., Yang, Y., et al. Digital reconstruction of full embryos during early mouse organogenesis. Cell (2025). https://doi.org/10.1016/j.cell.2025.05.035
