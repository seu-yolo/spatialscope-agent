from __future__ import annotations

import streamlit as st

from spatialscope.ui.helpers import load_theme
from spatialscope.ui.pages import render_app
from spatialscope.ui.state import init_session_state


def main() -> None:
    st.set_page_config(page_title="SpatialScope Agent", page_icon="S", layout="wide")
    init_session_state()
    load_theme()
    render_app()


if __name__ == "__main__":
    main()
