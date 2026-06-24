from __future__ import annotations

from pathlib import Path
from typing import Any


def _record_text(record: dict[str, Any]) -> str:
    parts = [
        record.get("title"),
        record.get("caption"),
        record.get("path"),
        record.get("relpath"),
        record.get("evidence_id"),
    ]
    return " ".join(str(part) for part in parts if part).lower()


def visual_evidence_rank(record: dict[str, Any]) -> tuple[int, str]:
    text = _record_text(record)
    path = Path(str(record.get("path") or record.get("relpath") or "")).name.lower()
    title = str(record.get("title") or "").lower()

    if path.startswith("spatial_") or title.startswith("spatial view"):
        return (0, title or path)
    if "umap" in text:
        return (1, title or path)
    if "gene_panel" in path or "gene panel" in text:
        return (2, title or path)
    if "marker" in text:
        return (3, title or path)
    if "neighborhood" in text or "svg" in text:
        return (4, title or path)
    if "highly_variable" in path or "highly variable" in text or "hvg" in text:
        return (5, title or path)
    if path.startswith("qc_") or "qc " in text or "quality" in text:
        return (6, title or path)
    return (7, title or path)


def prioritize_visual_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = list(enumerate(records))
    indexed.sort(key=lambda item: (*visual_evidence_rank(item[1]), item[0]))
    return [record for _, record in indexed]

