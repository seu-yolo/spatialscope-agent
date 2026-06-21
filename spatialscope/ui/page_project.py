from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from spatialscope.ui.helpers import MODE_VALUES, apply_ui_overrides, plan_from_state, plan_to_text, save_upload
from spatialscope.ui.landing_preview import ensure_landing_preview
from spatialscope.ui.state import active_state, set_draft
from spatialscope.ui.v6_helpers import (
    PROMPT_SUGGESTIONS,
    analyses_for_state,
    compact_list,
    dataset_identity,
    dataset_identity_text,
    h,
    render_dataset_identity_strip,
    resolved_genes_for_state,
)
from spatialscope.ui.v6_runner import prepare_state
from spatialscope.utils.demo import ensure_demo_data, get_demo_preset


TOOL_LABELS = {
    "load_h5ad": "数据读取",
    "run_qc": "数据质量检查",
    "preprocess": "预处理",
    "run_clustering": "PCA / UMAP / Leiden 聚类",
    "plot_spatial_clusters": "空间聚类图",
    "plot_gene_panel": "基因空间表达",
    "find_marker_genes": "Marker genes",
    "run_svg": "空间可变基因",
    "run_neighborhood_enrichment": "邻域富集",
    "suggest_cluster_annotations": "Cluster annotation",
    "generate_report": "证据报告",
}


def _defaults() -> dict[str, Any]:
    preset = get_demo_preset()
    return {
        "mode": str(preset["mode"]),
        "outdir": str(preset["outdir"]),
        "min_genes": int(preset["min_genes"]),
        "min_cells": int(preset["min_cells"]),
        "max_mt_pct": float(preset["max_mt_pct"]),
        "resolution": float(preset["resolution"]),
        "gene_text": str(preset["gene_text"]),
        "annotation_top_n": int(preset["annotation_top_n"]),
    }


def _selected_data_path() -> str:
    path = str(st.session_state.get("selected_data_path") or "")
    if path:
        return path
    if st.session_state.get("dataset_choice") == "demo":
        return str(get_demo_preset()["data_path"])
    return ""


def _choose_demo() -> None:
    demo = ensure_demo_data(get_demo_preset()["data_path"])
    st.session_state.dataset_choice = "demo"
    st.session_state.selected_data_path = str(demo["path"])
    st.session_state.uploaded_dataset_name = ""
    st.session_state.research_question = str(get_demo_preset()["query"])


def _render_landing() -> None:
    paths = ensure_landing_preview()
    pending_prompt = st.session_state.pop("pending_research_question", "")
    if pending_prompt:
        st.session_state.research_question = pending_prompt
    left, right = st.columns([0.59, 0.41], gap="large")
    with left:
        st.markdown(
            """
            <section class="v6-landing-copy">
              <div class="v6-product-name">SpatialScope</div>
              <div class="v6-overline">Spatial transcriptomics research copilot</div>
              <h1>从空间数据，到可追踪的科研证据</h1>
              <p>用自然语言提出研究问题。SpatialScope 会先检查数据，再生成可审阅的分析方案，并把解释绑定到真实图表与统计结果。</p>
            </section>
            """,
            unsafe_allow_html=True,
        )

        with st.container(border=True, key="landing_composer"):
            st.markdown("<div class='v6-field-label'>Dataset</div>", unsafe_allow_html=True)
            choice_cols = st.columns([0.48, 0.52], gap="small")
            if choice_cols[0].button("上传 .h5ad", width="stretch", key="show_upload_dataset"):
                st.session_state.show_upload_panel = not bool(st.session_state.get("show_upload_panel"))
            if choice_cols[1].button("使用早期胚胎 Demo", width="stretch", key="use_demo_dataset"):
                _choose_demo()
                st.rerun()

            if st.session_state.get("show_upload_panel"):
                uploaded = st.file_uploader("选择 AnnData 文件", type=["h5ad"], label_visibility="collapsed")
                if uploaded is not None:
                    saved = save_upload(uploaded)
                    st.session_state.dataset_choice = "upload"
                    st.session_state.selected_data_path = saved
                    st.session_state.uploaded_dataset_name = uploaded.name

            selected_path = _selected_data_path()
            if selected_path:
                name = st.session_state.get("uploaded_dataset_name") or Path(selected_path).name
                st.markdown(f"<div class='v6-selected-data'>已选择：{h(name)}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='v6-selected-data muted'>请选择 demo 或上传 .h5ad</div>", unsafe_allow_html=True)

            question = st.text_area(
                "你希望研究什么？",
                value=str(st.session_state.get("research_question") or ""),
                height=112,
                placeholder="例如：检查数据质量，比较空间结构与 UMAP 聚类，并查看 Sox17、T 和 Mesp1 的空间表达。",
                key="research_question",
            )
            chip_cols = st.columns(4, gap="small")
            for col, label in zip(chip_cols, PROMPT_SUGGESTIONS):
                if col.button(label, key=f"suggestion_{label}", width="stretch"):
                    st.session_state.pending_research_question = PROMPT_SUGGESTIONS[label]
                    st.rerun()

            if st.button("检查数据并生成方案 →", type="primary", width="stretch", key="inspect_and_plan"):
                if not selected_path:
                    st.warning("请先选择早期胚胎 Demo 或上传 .h5ad。")
                elif not question.strip():
                    st.warning("请先写下研究问题。")
                else:
                    defaults = _defaults()
                    with st.status("正在检查数据并生成可审阅方案...", expanded=False):
                        state = prepare_state(
                            data_path=selected_path,
                            query=question.strip(),
                            mode=defaults["mode"],
                            outdir=defaults["outdir"],
                            min_genes=defaults["min_genes"],
                            min_cells=defaults["min_cells"],
                            max_mt_pct=defaults["max_mt_pct"],
                            resolution=defaults["resolution"],
                            gene_text=defaults["gene_text"],
                            annotation_top_n=defaults["annotation_top_n"],
                        )
                    set_draft(state)
                    st.session_state.plan_text = plan_to_text(plan_from_state(state))
                    st.rerun()

        st.markdown(
            "<div class='v6-trust-line'>确定性工具负责计算 · LLM 负责理解与解释 · 每条结论绑定证据</div>",
            unsafe_allow_html=True,
        )

    with right:
        st.markdown("<section class='v6-preview-panel'>", unsafe_allow_html=True)
        st.image(str(paths["webp"] if paths["webp"].exists() else paths["png"]), width="stretch")
        st.markdown(
            """
            <div class="v6-preview-caption">
              <strong>Early mouse embryo demo</strong>
              <span>240 spots · Mus musculus · spatial coordinates available</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("</section>", unsafe_allow_html=True)


def _render_conversation(state: dict[str, Any]) -> None:
    ident = dataset_identity(state)
    genes = resolved_genes_for_state(state)
    analyses = analyses_for_state(state)
    warnings = list(map(str, state.get("warnings", [])[:3]))
    caveats = warnings or ["当前 demo 数据为 synthetic embryo demo，解释应以流程展示和方法边界为主。"]
    st.markdown(
        f"""
        <div class="v6-thread">
          <div class="v6-message user">
            <div class="v6-speaker">YOU</div>
            <p>{h(state.get("user_query", ""))}</p>
          </div>
          <div class="v6-message agent">
            <div class="v6-speaker">SPATIALSCOPE</div>
            <p>我先检查了数据：{h(ident.get("n_obs"))} spots、{h(ident.get("n_vars"))} genes，{h("包含空间坐标" if ident.get("has_spatial") else "未发现空间坐标")}，表达矩阵判断为 {h(ident.get("matrix_state"))}。</p>
            <div class="v6-agent-grid">
              <div><span>可用基因</span><strong>{h(compact_list(genes, empty="未从问题中解析到指定基因"))}</strong></div>
              <div><span>建议分析</span><strong>{h(compact_list(analyses, limit=4, empty="标准 QC + 聚类"))}</strong></div>
              <div><span>注意事项</span><strong>{h(compact_list(caveats, limit=2))}</strong></div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_clarifications_inline(state: dict[str, Any]) -> None:
    items = state.get("clarification_items", []) or []
    if not items:
        return
    st.markdown("<div class='v6-interrupt-title'>需要确认</div>", unsafe_allow_html=True)
    for i, item in enumerate(items[:3]):
        suggestions = item.get("suggestions", {}) if isinstance(item, dict) else {}
        st.warning(str(item.get("message") or "需要人工确认后继续。"))
        if suggestions:
            options = ["跳过该项"]
            for _, value in suggestions.items():
                if isinstance(value, list):
                    options.extend([str(candidate.get("gene") or candidate.get("match") or candidate) for candidate in value[:4]])
            st.radio("选择修复方式", list(dict.fromkeys(options)), key=f"clarification_choice_{i}")


def _render_plan_stepper(state: dict[str, Any]) -> None:
    plan = plan_from_state(state)
    if not plan:
        st.info("还没有分析方案。")
        return
    rows: list[str] = []
    for index, step in enumerate(plan, start=1):
        tool = str(step.get("tool") or "step")
        params = step.get("params") or {}
        purpose = str(step.get("rationale") or step.get("scientific_purpose") or "生成可追踪证据")
        expected = " · ".join(map(str, step.get("expected_evidence", []) or [])) or "trace record"
        param_text = " · ".join(f"{key} {value}" for key, value in list(params.items())[:4]) or "默认参数"
        rows.append(
            f"""
            <div class="v6-plan-row">
              <div class="v6-plan-index">{index:02d}</div>
              <div>
                <h3>{h(TOOL_LABELS.get(tool, tool.replace("_", " ")))}</h3>
                <p>目的：{h(purpose)}</p>
                <p>参数：{h(param_text)}</p>
                <p>预期：{h(expected)}</p>
              </div>
            </div>
            """
        )
    st.html(f"<div class='v6-plan-stepper'>{''.join(rows)}</div>")


def _render_settings_and_approve(state: dict[str, Any]) -> None:
    defaults = _defaults()
    params = state.get("parameters") or {}
    qc = params.get("qc") or {}
    clustering = params.get("clustering") or {}
    with st.expander("分析设置", expanded=False):
        c0, c1, c2 = st.columns(3)
        mode_label = c0.selectbox("运行深度", ["快速", "标准", "高阶"], index=1, key="v6_mode_label")
        min_genes = c1.number_input("Spot 最少基因", min_value=0, max_value=5000, value=int(qc.get("min_genes", defaults["min_genes"])), step=5)
        min_cells = c2.number_input("基因最少 spots", min_value=0, max_value=200, value=int(qc.get("min_cells", defaults["min_cells"])), step=1)
        c3, c4, c5 = st.columns([0.75, 1.45, 0.8])
        max_mt_pct = c3.number_input("MT% 上限", min_value=0.0, max_value=100.0, value=float(qc.get("max_mt_pct", defaults["max_mt_pct"])), step=1.0)
        gene_text = c4.text_input("Gene panel", value=str(defaults["gene_text"]))
        resolution = c5.slider("Leiden resolution", min_value=0.1, max_value=2.0, value=float(clustering.get("resolution", defaults["resolution"])), step=0.1)
        annotation_top_n = st.number_input("Annotation top N", min_value=3, max_value=30, value=int(defaults["annotation_top_n"]), step=1)

    cols = st.columns([0.72, 0.28], gap="medium")
    if cols[0].button("批准并运行", type="primary", width="stretch", key="approve_and_run"):
        updated = apply_ui_overrides(
            dict(state),
            min_genes=int(min_genes),
            min_cells=int(min_cells),
            max_mt_pct=float(max_mt_pct),
            resolution=float(resolution),
            gene_text=gene_text,
            annotation_top_n=int(annotation_top_n),
        )
        updated["mode"] = MODE_VALUES.get(str(mode_label), "standard")
        set_draft(updated)
        st.session_state.pending_run_approval = True
        st.session_state.pending_run_plan_source = "project_approved"
        run_page = st.session_state.get("_v6_run_page")
        if run_page is not None:
            st.switch_page(run_page)
        st.rerun()
    if cols[1].button("修改研究问题", width="stretch", key="edit_question"):
        st.session_state.research_question = str(state.get("user_query") or "")
        st.session_state.draft_state = None
        st.rerun()


def _render_dataset_ready(state: dict[str, Any]) -> None:
    render_dataset_identity_strip(state)
    st.markdown("<div class='v6-flow-label'>Research conversation</div>", unsafe_allow_html=True)
    _render_conversation(state)
    _render_clarifications_inline(state)
    st.markdown("<div class='v6-flow-label'>Reviewable plan</div>", unsafe_allow_html=True)
    _render_plan_stepper(state)
    _render_settings_and_approve(state)


def project_page() -> None:
    state = active_state()
    if not state:
        _render_landing()
        return
    if state.get("report_path"):
        render_dataset_identity_strip(state)
        st.markdown(
            f"""
            <div class="v6-complete-callout">
              <div class="v6-overline">Analysis complete</div>
              <h2>报告和探索工作区已经准备好</h2>
              <p>{h(dataset_identity_text(state))}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        cols = st.columns(2)
        if cols[0].button("打开探索工作区", type="primary", width="stretch"):
            page = st.session_state.get("_v6_explore_page")
            if page is not None:
                st.switch_page(page)
        if cols[1].button("查看报告", width="stretch"):
            page = st.session_state.get("_v6_report_page")
            if page is not None:
                st.switch_page(page)
        return
    _render_dataset_ready(state)
