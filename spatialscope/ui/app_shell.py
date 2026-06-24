from __future__ import annotations

import streamlit as st

from spatialscope.ui.page_advanced import advanced_page
from spatialscope.ui.page_explore import explore_page
from spatialscope.ui.page_project import project_page
from spatialscope.ui.page_report import report_page
from spatialscope.ui.page_run import run_page
from spatialscope.ui.state import active_state
from spatialscope.ui.v6_helpers import dataset_identity, h, llm_surface_label
from spatialscope.ui.helpers import agent_companion_html, spatialscope_logo_uri


def _render_brand_header() -> None:
    state = active_state()
    llm = llm_surface_label()
    logo = spatialscope_logo_uri()
    companion = agent_companion_html("LLM", llm, active=llm.startswith("LLM"))
    if state:
        ident = dataset_identity(state)
        title = f"SpatialScope / {ident.get('name', 'project')}"
        facts = f"{ident.get('n_obs')} spots · {ident.get('n_vars')} genes · {ident.get('mode', '')}"
        st.markdown(
            f"""
            <header class="v6-brand-header active">
              <div class="v6-brand-lockup">
                <img class="v6-brand-logo" src="{logo}" alt="SpatialScope logo">
                <div>
                  <div class="v6-brand-title">{h(title)}</div>
                  <div class="v6-brand-subtitle">{h(facts)}</div>
                </div>
              </div>
              <nav>
                {companion}
                <a href="https://github.com/seu-yolo/spatialscope-agent" target="_blank">GitHub</a>
                <a href="https://github.com/seu-yolo/spatialscope-agent/blob/main/README.md" target="_blank">Documentation</a>
              </nav>
            </header>
            """,
            unsafe_allow_html=True,
        )
        return
    st.markdown(
        f"""
        <header class="v6-brand-header">
          <div class="v6-brand-lockup">
            <img class="v6-brand-logo" src="{logo}" alt="SpatialScope logo">
            <div class="v6-brand-title">SpatialScope</div>
          </div>
          <nav>
            <a href="https://github.com/seu-yolo/spatialscope-agent/blob/main/README.md" target="_blank">Documentation</a>
            <a href="https://github.com/seu-yolo/spatialscope-agent" target="_blank">GitHub</a>
            {companion}
          </nav>
        </header>
        """,
        unsafe_allow_html=True,
    )


def render_app() -> None:
    project = st.Page(project_page, title="项目", icon=":material/science:", url_path="project", default=True)
    run = st.Page(run_page, title="运行", icon=":material/route:", url_path="run")
    explore = st.Page(explore_page, title="探索", icon=":material/scatter_plot:", url_path="explore")
    report = st.Page(report_page, title="报告", icon=":material/article:", url_path="report")
    advanced = st.Page(advanced_page, title="高级", icon=":material/settings:", url_path="advanced")
    st.session_state["_v6_project_page"] = project
    st.session_state["_v6_run_page"] = run
    st.session_state["_v6_explore_page"] = explore
    st.session_state["_v6_report_page"] = report
    st.session_state["_v6_advanced_page"] = advanced
    pg = st.navigation(
        {
            "": [project, run, explore, report],
            "More": [advanced],
        },
        position="top",
    )
    _render_brand_header()
    pg.run()
