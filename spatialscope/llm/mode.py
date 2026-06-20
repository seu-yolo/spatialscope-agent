from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping


LLMMode = Literal["auto", "full", "fallback"]
ResolvedLLMMode = Literal["full", "fallback"]


@dataclass(frozen=True)
class LLMModeResolution:
    requested_mode: LLMMode
    active_mode: ResolvedLLMMode
    enabled: bool
    label: str
    reason: str


def resolve_llm_mode(
    *,
    requested: str | None,
    has_api_key: bool,
    has_base_url: bool,
    has_model: bool,
) -> LLMModeResolution:
    value = (requested or "auto").strip().lower()
    if value not in {"auto", "full", "fallback"}:
        value = "auto"
    configured = bool(has_api_key and has_base_url and has_model)
    if value == "fallback":
        return LLMModeResolution(
            requested_mode="fallback",
            active_mode="fallback",
            enabled=False,
            label="规则模式：未调用外部 LLM",
            reason="SPATIALSCOPE_LLM_MODE=fallback",
        )
    if value == "full":
        return LLMModeResolution(
            requested_mode="full",
            active_mode="full" if configured else "fallback",
            enabled=configured,
            label="LLM full mode" if configured else "规则模式：LLM 配置不完整",
            reason="configured" if configured else "full mode requested but configuration is incomplete",
        )
    return LLMModeResolution(
        requested_mode="auto",
        active_mode="full" if configured else "fallback",
        enabled=configured,
        label="LLM auto → full" if configured else "规则模式：未调用外部 LLM",
        reason="valid provider configuration" if configured else "auto mode without complete provider configuration",
    )


def mode_from_status(status: Mapping[str, object]) -> LLMModeResolution:
    return resolve_llm_mode(
        requested=str(status.get("requested_mode") or "auto"),
        has_api_key=bool(status.get("api_key_present")),
        has_base_url=bool(status.get("base_url") and status.get("base_url") != "not configured"),
        has_model=bool(status.get("model") and status.get("model") != "not configured"),
    )
