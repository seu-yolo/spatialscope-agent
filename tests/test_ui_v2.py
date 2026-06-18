from __future__ import annotations

from pathlib import Path

import app

from spatialscope.ui.components import atlas_svg
from spatialscope.ui.helpers import load_plan_from_text, plan_to_text


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
    assert "SPOTS" in atlas_svg()
