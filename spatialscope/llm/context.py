from __future__ import annotations

from typing import Any, Mapping


RAW_PAYLOAD_KEYS = {
    "x",
    "adata_x",
    "raw_x",
    "raw_matrix",
    "matrix_values",
    "expression_matrix",
    "count_matrix",
    "coordinate_matrix",
    "coordinates",
    "spatial_coordinates",
    "obsm_spatial",
}


def safe_for_llm(value: Any) -> Any:
    """Redact accidental matrix-like payloads before prompt assembly."""

    if isinstance(value, Mapping):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower().replace(".", "_").replace(" ", "_")
            if normalized in RAW_PAYLOAD_KEYS or normalized.endswith("_matrix"):
                safe[str(key)] = "[redacted matrix-like payload]"
            else:
                safe[str(key)] = safe_for_llm(item)
        return safe
    if isinstance(value, list):
        if len(value) > 12 and any(isinstance(item, (list, tuple, dict)) for item in value):
            return f"[redacted nested sequence with {len(value)} items]"
        return [safe_for_llm(item) for item in value]
    if isinstance(value, tuple):
        return safe_for_llm(list(value))
    return value


def context_for_copilot(
    *,
    selected_evidence: list[dict[str, Any]],
    warnings: list[str],
    table_titles: list[str],
    conversation_memory: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return safe_for_llm(
        {
            "evidence_ids": [str(item.get("evidence_id")) for item in selected_evidence if item.get("evidence_id")],
            "selected_evidence": selected_evidence,
            "selected_table_titles": table_titles[:6],
            "warnings": warnings[:8],
            "conversation_memory": (conversation_memory or [])[-6:],
        }
    )
