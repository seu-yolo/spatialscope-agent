from __future__ import annotations

import streamlit as st
from dotenv import load_dotenv

from spatialscope.ui.app_shell import render_app
from spatialscope.ui.helpers import load_theme
from spatialscope.ui.state import init_session_state


def main() -> None:
    load_dotenv()
    st.set_page_config(page_title="SpatialScope Agent", page_icon="S", layout="wide")
    init_session_state()
    load_theme()
    render_app()


if __name__ == "__main__":
    main()
