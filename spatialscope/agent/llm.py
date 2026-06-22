from __future__ import annotations

import os
import json
import time
from dataclasses import dataclass
from typing import Any, Mapping

from spatialscope.agent.schemas import (
    AnalysisPlan,
    ParsedRequest,
    analysis_plan_json_schema,
    parsed_request_json_schema,
)
from spatialscope.agent.state import RunMode
from spatialscope.llm.mode import resolve_llm_mode
from spatialscope.llm.prompts import SYSTEM_PROMPT
from spatialscope.tools.registry import available_tool_names
from spatialscope.utils.json_utils import extract_json_object


@dataclass
class LLMClient:
    api_key: str | None = None
    base_url: str = ""
    model: str = "glm-5.1"
    timeout_seconds: float = 15.0

    @classmethod
    def from_env(cls) -> "LLMClient":
        generic_api_key = os.getenv("SPATIALSCOPE_LLM_API_KEY")
        if generic_api_key:
            return cls(
                api_key=generic_api_key,
                base_url=os.getenv("SPATIALSCOPE_LLM_BASE_URL", ""),
                model=os.getenv("SPATIALSCOPE_LLM_MODEL", "glm-5.1"),
                timeout_seconds=float(os.getenv("SPATIALSCOPE_LLM_TIMEOUT_SECONDS", "10")),
            )
        return cls(
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv("SPATIALSCOPE_LLM_MODEL", "deepseek-v4-flash"),
            timeout_seconds=float(os.getenv("SPATIALSCOPE_LLM_TIMEOUT_SECONDS", "10")),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _client(self) -> Any:
        if not self.api_key:
            raise RuntimeError("SPATIALSCOPE_LLM_API_KEY is not configured.")
        if not self.base_url:
            raise RuntimeError("SPATIALSCOPE_LLM_BASE_URL is not configured.")
        try:
            from openai import OpenAI
        except Exception as exc:
            raise RuntimeError("The `openai` package is required for OpenAI-compatible LLM access.") from exc
        return OpenAI(api_key=self.api_key, base_url=self.base_url, timeout=self.timeout_seconds, max_retries=0)

    def complete(self, messages: list[dict[str, str]], *, temperature: float = 0.1) -> str:
        client = self._client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, *messages],
            temperature=temperature,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("The configured LLM returned an empty response.")
        return content

    def complete_json(self, messages: list[dict[str, str]], *, temperature: float = 0.1) -> dict[str, Any]:
        last_error: Exception | None = None
        for _ in range(2):
            content = self.complete(messages, temperature=temperature)
            try:
                return extract_json_object(content)
            except Exception as exc:  # noqa: BLE001 - retry parser failures only
                last_error = exc
                messages = [
                    *messages,
                    {
                        "role": "user",
                        "content": "Return only one valid JSON object. Do not include Markdown fences.",
                    },
                ]
        raise RuntimeError(f"Could not parse JSON response from the configured LLM: {last_error}")


DeepSeekClient = LLMClient


def _env_value(env: Mapping[str, str] | None, key: str, default: str = "") -> str:
    if env is None:
        return os.getenv(key, default)
    return env.get(key, default)


def _mask_secret(value: str | None) -> str:
    if not value:
        return "not configured"
    return f"configured ({len(value)} chars)"


def llm_config_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return safe, displayable LLM configuration status without exposing secrets."""

    generic_key = _env_value(env, "SPATIALSCOPE_LLM_API_KEY")
    deepseek_key = _env_value(env, "DEEPSEEK_API_KEY")
    if generic_key:
        provider = "openai_compatible"
        api_key = generic_key
        base_url = _env_value(env, "SPATIALSCOPE_LLM_BASE_URL")
        model = _env_value(env, "SPATIALSCOPE_LLM_MODEL", "glm-5.1")
    elif deepseek_key:
        provider = "deepseek_compatible"
        api_key = deepseek_key
        base_url = _env_value(env, "DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        model = _env_value(env, "SPATIALSCOPE_LLM_MODEL", "deepseek-v4-flash")
    else:
        provider = "disabled"
        api_key = ""
        base_url = _env_value(env, "SPATIALSCOPE_LLM_BASE_URL") or _env_value(env, "DEEPSEEK_BASE_URL", "")
        model = _env_value(env, "SPATIALSCOPE_LLM_MODEL", "glm-5.1")
    timeout_raw = _env_value(env, "SPATIALSCOPE_LLM_TIMEOUT_SECONDS", "10")
    try:
        timeout_seconds = float(timeout_raw)
    except ValueError:
        timeout_seconds = 10.0
    enabled = bool(api_key and base_url and model)
    requested_mode = _env_value(env, "SPATIALSCOPE_LLM_MODE", "auto")
    mode = resolve_llm_mode(
        requested=requested_mode,
        has_api_key=bool(api_key),
        has_base_url=bool(base_url),
        has_model=bool(model),
    )
    missing: list[str] = []
    if not api_key:
        missing.append("API key")
    if api_key and not base_url:
        missing.append("base URL")
    if not model:
        missing.append("model")
    return {
        "provider": provider,
        "enabled": enabled and mode.enabled,
        "configured": enabled,
        "requested_mode": mode.requested_mode,
        "active_mode": mode.active_mode,
        "mode_label": mode.label,
        "mode_reason": mode.reason,
        "api_key_present": bool(api_key),
        "api_key_preview": _mask_secret(api_key),
        "base_url": base_url or "not configured",
        "model": model or "not configured",
        "timeout_seconds": timeout_seconds,
        "missing": missing,
        "fallback": "rule_based",
    }


def smoke_test_llm(client: LLMClient | None = None) -> dict[str, Any]:
    client = client or LLMClient.from_env()
    status = llm_config_status()
    if not client.enabled:
        return {
            "status": "skipped",
            "ok": False,
            "summary": "LLM API key is not configured; rule-based fallback remains available.",
            "config": status,
        }
    start = time.time()
    try:
        payload = client.complete_json(
            [
                {
                    "role": "user",
                    "content": (
                        "Return exactly one JSON object for a connection test: "
                        '{"ok": true, "service": "spatialscope-llm-smoke"}.'
                    ),
                }
            ],
            temperature=0.0,
        )
        ok = bool(payload.get("ok"))
        return {
            "status": "success" if ok else "warn",
            "ok": ok,
            "latency_sec": round(time.time() - start, 3),
            "summary": "LLM returned valid JSON." if ok else "LLM responded, but the JSON did not include ok=true.",
            "response": payload,
            "config": status,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "failed",
            "ok": False,
            "latency_sec": round(time.time() - start, 3),
            "summary": str(exc),
            "config": status,
        }


def parse_query_with_llm(client: LLMClient, query: str) -> dict[str, Any]:
    if not client.enabled:
        raise RuntimeError("LLM client is disabled.")
    payload = client.complete_json(
        [
            {
                "role": "user",
                "content": (
                    "Parse this spatial transcriptomics request into the required JSON schema. "
                    "Only include genes explicitly requested by the user. Do not treat words like "
                    "marker, cluster, spatial, variable, panel, dataset, card, or analysis as gene names.\n\n"
                    f"JSON schema:\n{json.dumps(parsed_request_json_schema(), ensure_ascii=False)}\n\n"
                    f"Request: {query}"
                ),
            }
        ]
    )
    return ParsedRequest.model_validate(payload).model_dump()


def plan_with_llm(
    client: LLMClient,
    *,
    query: str,
    parsed_request: dict[str, Any],
    dataset_summary: dict[str, Any],
    mode: RunMode,
    tool_contracts: list[dict[str, Any]],
) -> dict[str, Any]:
    if not client.enabled:
        raise RuntimeError("LLM client is disabled.")
    payload = client.complete_json(
        [
            {
                "role": "user",
                "content": (
                    "Generate a reproducible SpatialScope analysis plan. Return one JSON object "
                    "matching the AnalysisPlan schema. Use only tools from the provided registry. "
                    "Do not invent tools. Keep parameters conservative. Mark Squidpy-dependent "
                    "steps as optional when mode is advanced.\n\n"
                    f"AnalysisPlan JSON schema:\n{json.dumps(analysis_plan_json_schema(), ensure_ascii=False)}\n\n"
                    f"Allowed tools: {sorted(available_tool_names())}\n\n"
                    f"Tool contracts: {json.dumps(tool_contracts, ensure_ascii=False)}\n\n"
                    f"User query: {query}\n"
                    f"Parsed request: {json.dumps(parsed_request, ensure_ascii=False)}\n"
                    f"Dataset summary: {json.dumps(dataset_summary, ensure_ascii=False, default=str)}\n"
                    f"Requested mode: {mode}"
                ),
            }
        ],
        temperature=0.05,
    )
    if "steps" not in payload and "plan" in payload:
        payload["steps"] = payload.pop("plan")
    payload.setdefault("mode", mode)
    payload["source"] = "llm"
    plan = AnalysisPlan.model_validate(payload)
    allowed = available_tool_names()
    for step in plan.steps:
        if step.tool not in allowed:
            raise ValueError(f"The configured LLM proposed an unknown tool: {step.tool}")
    return plan.model_dump()


def interpret_with_llm(
    client: LLMClient,
    *,
    query: str,
    dataset_summary: dict[str, Any],
    tool_summaries: list[dict[str, Any]],
) -> str:
    if not client.enabled:
        raise RuntimeError("LLM client is disabled.")
    content = client.complete(
        [
            {
                "role": "user",
                "content": (
                    "Write a concise scientific interpretation for this spatial transcriptomics run. "
                    "Use cautious language. Do not infer mechanisms. Ground every statement in the "
                    "provided summaries.\n\n"
                    f"User query: {query}\n"
                    f"Dataset summary: {dataset_summary}\n"
                    f"Tool summaries: {tool_summaries[-12:]}"
                ),
            }
        ],
        temperature=0.2,
    )
    return content.strip()


def suggest_repair_with_llm(
    client: LLMClient,
    *,
    failed_step: dict[str, Any],
    tool_result: dict[str, Any],
    tool_contract: dict[str, Any],
    dataset_summary: dict[str, Any],
) -> dict[str, Any]:
    if not client.enabled:
        raise RuntimeError("LLM client is disabled.")
    payload = client.complete_json(
        [
            {
                "role": "user",
                "content": (
                    "A SpatialScope tool failed. Suggest a cautious repair diagnosis using only the "
                    "provided step metadata, tool contract, dataset summary, and error summary. Do not "
                    "ask for or infer from raw matrices. Return one JSON object with keys: "
                    "`likely_cause` (string), `recommended_actions` (array of short strings), "
                    "`user_message` (string), and `should_retry` (boolean). Keep `should_retry` false "
                    "unless a safe parameter-only retry is obvious.\n\n"
                    f"Failed step: {json.dumps(failed_step, ensure_ascii=False, default=str)}\n"
                    f"Tool result: {json.dumps(tool_result, ensure_ascii=False, default=str)}\n"
                    f"Tool contract: {json.dumps(tool_contract, ensure_ascii=False, default=str)}\n"
                    f"Dataset summary: {json.dumps(dataset_summary, ensure_ascii=False, default=str)}"
                ),
            }
        ],
        temperature=0.05,
    )
    if not isinstance(payload.get("recommended_actions"), list):
        payload["recommended_actions"] = []
    payload["likely_cause"] = str(payload.get("likely_cause") or "")
    payload["user_message"] = str(payload.get("user_message") or "")
    payload["should_retry"] = bool(payload.get("should_retry", False))
    return payload
