from __future__ import annotations

from pathlib import Path

import app

from spatialscope.ui.helpers import load_plan_from_text, plan_to_text
from spatialscope.ui.landing_preview import ensure_landing_preview


def test_app_entrypoint_is_thin_router():
    source = Path("app.py").read_text(encoding="utf-8")
    assert "render_app()" in source
    assert len(source.splitlines()) < 40
    assert callable(app.main)


def test_ui_plan_json_roundtrip_validates_registry_tools():
    plan = [{"id": "qc", "tool": "run_qc", "params": {}, "rationale": "QC"}]
    restored = load_plan_from_text(plan_to_text(plan))
    assert restored[0]["tool"] == "run_qc"


def test_ui_theme_and_signature_visual_exist():
    assert Path("spatialscope/ui/assets/theme.css").exists()
    app_shell = Path("spatialscope/ui/app_shell.py").read_text(encoding="utf-8")
    assert "st.navigation" in app_shell
    assert "st.Page" in app_shell


def test_landing_preview_uses_real_demo_asset():
    paths = ensure_landing_preview()
    assert paths["png"].exists()
    assert paths["png"].stat().st_size > 10_000
