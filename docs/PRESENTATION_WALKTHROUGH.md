# SpatialScope Agent 答辩讲解流程

这份流程用于配合本地 PPT 和在线网站；PPT 文件不纳入 GitHub 仓库版本：

https://spatialscope-seu.streamlit.app/

PPT 的 speaker notes 已经内置逐页讲稿和操作提示。正式演示时建议使用 PowerPoint/Keynote 的演讲者视图。

建议时间：12-15 分钟。

## 总体节奏

1. Slide 1-4：先讲空间转录组数据是什么。
2. Slide 5-8：讲标准分析流程，以及为什么解释需要谨慎。
3. Slide 9-11：讲为什么要做成 Agent，以及 SpatialScope 的架构。
4. Slide 12：从 PPT 自然切到网站。
5. Slide 13：作为 live demo 路线图，看完后切浏览器演示。
6. Slide 14-16：回到 PPT，讲真实数据验证、科研场景和总结。

## 开场

Slide 1：

可以这样说：

> SpatialScope Agent 是一个面向空间转录组的交互式分析 Agent。我的讲解会先从空间转录组数据本身出发，说明标准分析流程是什么；然后介绍我如何把这套流程做成一个可计划、可执行、可追踪、可解释的科研 Agent。中间我会切到网站，展示这个流程在真实交互界面里是如何运行的。

## 第一部分：空间转录组数据

Slides 2-4：

核心意思：

- 普通转录组回答“表达了什么”。
- 单细胞转录组回答“有哪些细胞状态或细胞类型”。
- 空间转录组进一步回答“这些表达和状态在组织中位于哪里”。
- 一个空间转录组对象通常包含表达矩阵、metadata、空间坐标、raw/layers 和可选组织图像。
- 不同平台的数据结构不同，所以系统必须先 inspect dataset。

过渡句：

> 理解数据结构之后，下一步是看这种数据通常如何分析。

## 第二部分：标准分析流程

Slides 5-8：

核心意思：

- 标准流程包括数据读取、QC、归一化、降维聚类、空间可视化、marker/SVG/邻域分析和解释。
- QC 很重要，因为后续分析依赖表达矩阵是否可靠、空间坐标是否存在、表达层是否安全。
- UMAP 和 Spatial plot 要一起看：UMAP 看表达空间相似性，Spatial 看组织空间位置。
- 从图到生物学解释不能跳太快，必须有统计摘要、evidence ID 和 caveat。

过渡句：

> 所以我的项目不是发明一套新的空间转录组算法，而是把这套标准流程组织成一个可靠的 Agent。

## 第三部分：Agent 设计

Slides 9-11：

核心意思：

- 传统 notebook 需要用户自己把研究问题翻译成代码。
- 数据字段、表达层、空间坐标都可能不统一，容易误用。
- SpatialScope 的价值是先检查数据，再生成计划，再用确定性工具执行，最后基于证据解释。
- LLM 不是直接拿表达矩阵做计算，而是作为 sidecar 参与问题理解、计划补全和 evidence-grounded interpretation。
- LangGraph 负责组织 state machine，工具层负责实际分析。

过渡句：

> 到这里为止，PPT 展示的是设计逻辑。接下来我切到网站，看这套设计能不能变成一个实际可用的分析体验。

## 从 PPT 切到网站

Slide 12：

可以这样说：

> 这个网站的四个主要页面对应刚才讲过的流程。Project 负责理解数据和问题；Run 负责执行计划并显示 LangGraph 事件；Explore 把 Spatial、UMAP 和 Copilot 放在一起；Report 最后把 findings、evidence 和 caveats 组织起来。现在我切到网站演示。

然后切到：

https://spatialscope-seu.streamlit.app/

## 网站演示路线

Slide 13 可以先停 10-15 秒，说明演示路线，然后切浏览器。

### Project 页面

操作：

1. 点击早期胚胎 demo。
2. 使用默认问题，或输入：

```text
检查这个早期小鼠胚胎空间数据的质量，比较空间结构与 UMAP 聚类，并查看 Pou5f1、Sox17、T 和 Mesp1 的空间表达。总结主要观察和局限。
```

讲法：

> 我不会一上来就运行分析。Agent 首先要理解数据：有多少 spots、多少 genes、有没有 spatial coordinates、表达层是不是 count-like，以及用户关心哪些基因。

### Run 页面

操作：

1. 生成分析方案。
2. 指出计划步骤。
3. 批准运行。
4. 展示 live LangGraph events。

讲法：

> 这个计划对应前面讲的标准流程：QC、preprocess、PCA/UMAP/Leiden、空间图、基因图、marker ranking 和 report。运行时可以看到 LangGraph events，所以它不是一个静态 spinner，而是可追踪的执行过程。

### Explore 页面

操作：

1. 展示 Spatial 和 UMAP side by side。
2. 指出 cluster 颜色一致。
3. 展示 gene panel。
4. 问 Copilot：

```text
哪个 cluster 的 Sox17 平均表达最高？
```

再问：

```text
Pou5f1 是否集中在某些 cluster？请给出证据和局限。
```

讲法：

> Spatial 图回答组织位置，UMAP 回答表达结构。Copilot 的作用不是自由发挥，而是基于当前 evidence pack 回答，并显示 evidence IDs。

### Report 页面

操作：

1. 打开 Report。
2. 展示 3-5 条 findings。
3. 指出 evidence IDs 和 caveats。

讲法：

> 最后的 report 不是简单总结，而是把每条观察和证据、局限放在一起。这样可以避免把 marker ranking 或空间聚集过度解释成机制结论。

## 从网站回到 PPT

回到 Slide 14。

过渡句：

> 刚才演示的是一个稳定的小型胚胎 demo。为了说明它不只是 toy example，我也用真实的公开 Stereo-seq 小鼠胚胎数据做了验证。

## 真实数据与科研场景

Slides 14-15：

核心意思：

- 真实数据来自 GSE278603 E7.5 mouse embryo。
- 系统能处理真实 AnnData、真实空间坐标字段和更大的基因集。
- 真实科研中可用于发育生物学、肿瘤微环境、病理切片探索和教学复现。
- 需要强调边界：不能替代专家注释，不能把 marker ranking 当作机制证明。

## 创新点怎么讲

可以放在 Slide 15 或总结前，用 40-60 秒讲清楚：

> 我认为这个项目的创新点不是重新发明一个聚类算法，而是把空间转录组分析这套成熟流程做成一个真正可体验的科研 Agent。第一，它不是直接跑脚本，而是先检查数据，再生成可审阅计划，再执行工具、校验结果、必要时修复。第二，LLM 不是自由发挥，它被限制在 evidence pack 和 schema validation 里，每条解释都要显示 evidence IDs，也就是能追溯到具体图、表或统计摘要。第三，用户不是看一堆 JSON，而是在浏览器里经历 Project、Run、Explore、Report 这条研究路径。因此 SpatialScope 的价值是降低进入空间转录组分析的门槛，同时保留可复核性、可复现性和科学解释的谨慎性。

如果老师问“和普通 Scanpy notebook 有什么区别”，可以回答：

> 普通 notebook 更像分析脚本，重点是代码执行；SpatialScope 更像研究工作台，重点是把数据状态、分析计划、工具执行、证据编号、LLM 解释和最终报告串成一个可追踪流程。它不是替代 Scanpy，而是把 Scanpy/AnnData/Squidpy 这类工具组织成一个可审阅的 Agent。

## 收尾

Slide 16：

可以这样说：

> 这个项目的核心是把空间转录组的标准分析流程转化为一个 LangGraph Agent。数值分析由确定性工具完成，LLM 被限制在 evidence pack 内，用于计划和解释。这样既能降低分析门槛，也保留了可追踪性、可复现性和科学解释的谨慎性。

## 时间控制

如果时间紧：

- Slide 3-4 快速讲，不展开平台细节。
- Slide 5、8、10 和网站 demo 是重点。
- Copilot 只问一个问题。
- Advanced/Provenance 不主动打开，除非老师问。

如果网站卡顿：

- 用 Slide 12 的截图讲产品流程。
- 用 Slide 13 讲 demo 路线。
- 继续回到 Slide 14 讲真实数据验证。
