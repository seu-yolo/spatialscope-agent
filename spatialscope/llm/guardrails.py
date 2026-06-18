from __future__ import annotations

from spatialscope.domain.evidence import flag_unsupported_definitive_language


def cautious_language_warnings(text: str) -> list[str]:
    matches = flag_unsupported_definitive_language(text)
    return [f"Unsupported definitive language: {phrase}" for phrase in matches]
