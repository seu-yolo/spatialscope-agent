from __future__ import annotations

from pathlib import Path

from spatialscope.ui.v7_helpers import project_stage_for_state, signature_meta


def test_scene_frame_component_exists():
    source = Path("spatialscope/ui/components/scene_frame.py").read_text(encoding="utf-8")
    assert "render_scene_header" in source
    assert "scene_frame" in source


def test_project_stage_model_defaults_to_landing():
    assert project_stage_for_state(None) == "landing"


def test_signature_does_not_invent_author_or_email(monkeypatch):
    monkeypatch.delenv("SPATIALSCOPE_AUTHOR_NAME", raising=False)
    monkeypatch.delenv("SPATIALSCOPE_AUTHOR_EMAIL", raising=False)
    meta = signature_meta()
    assert meta["author"] == ""
    assert meta["email"] == ""
    assert "Southeast University" in meta["affiliation"]


def test_theme_uses_standard_font_weights():
    css = Path("spatialscope/ui/assets/theme.css").read_text(encoding="utf-8")
    unusual = ["560", "620", "640", "650", "680", "720", "740", "760", "770", "780"]
    assert not any(f"font-weight: {weight}" in css for weight in unusual)
