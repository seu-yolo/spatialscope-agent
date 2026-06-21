from __future__ import annotations

from spatialscope.ui.app_shell import render_app
from spatialscope.ui.page_advanced import advanced_page as render_provenance_page
from spatialscope.ui.page_explore import explore_page as render_explore_page
from spatialscope.ui.page_project import project_page as render_project_page
from spatialscope.ui.page_report import report_page as render_report_page
from spatialscope.ui.page_run import run_page as render_run_page

__all__ = [
    "render_app",
    "render_project_page",
    "render_run_page",
    "render_explore_page",
    "render_report_page",
    "render_provenance_page",
]
