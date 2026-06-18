import pytest

from spatialscope.agent.llm import LLMClient, llm_config_status, smoke_test_llm


def test_llm_config_status_masks_key_and_prefers_generic_provider():
    status = llm_config_status(
        {
            "SPATIALSCOPE_LLM_API_KEY": "sk-test-secret-1234",
            "SPATIALSCOPE_LLM_BASE_URL": "https://example.test/api",
            "SPATIALSCOPE_LLM_MODEL": "glm-5.1",
            "SPATIALSCOPE_LLM_TIMEOUT_SECONDS": "12",
        }
    )
    assert status["provider"] == "openai_compatible"
    assert status["enabled"] is True
    assert status["api_key_preview"] == "configured (19 chars)"
    assert "secret" not in status["api_key_preview"]
    assert status["model"] == "glm-5.1"
    assert status["timeout_seconds"] == 12


def test_llm_config_status_falls_back_without_key():
    status = llm_config_status({})
    assert status["provider"] == "disabled"
    assert status["enabled"] is False
    assert "API key" in status["missing"]
    assert status["fallback"] == "rule_based"


def test_smoke_test_skips_without_key():
    class DisabledClient:
        enabled = False

    result = smoke_test_llm(DisabledClient())  # type: ignore[arg-type]
    assert result["status"] == "skipped"
    assert result["ok"] is False


def test_complete_json_does_not_retry_transport_failures():
    class FailingTransportClient(LLMClient):
        def __init__(self) -> None:
            super().__init__(api_key="sk-test", base_url="https://example.test", model="mock")
            self.calls = 0

        def complete(self, messages, *, temperature=0.1):  # type: ignore[no-untyped-def]
            self.calls += 1
            raise RuntimeError("network timeout")

    client = FailingTransportClient()
    with pytest.raises(RuntimeError, match="network timeout"):
        client.complete_json([{"role": "user", "content": "{}"}])
    assert client.calls == 1
