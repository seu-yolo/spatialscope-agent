from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class LLMCallRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    call_id: str = Field(default_factory=lambda: uuid4().hex)
    purpose: str
    provider: str = "disabled"
    model: str = ""
    started_at: str = ""
    finished_at: str = ""
    latency_sec: float | None = None
    success: bool = False
    structured_schema: str = ""
    validation_outcome: str = "not_run"
    fallback_reason: str = ""
    input_summary: dict[str, Any] = Field(default_factory=dict)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
