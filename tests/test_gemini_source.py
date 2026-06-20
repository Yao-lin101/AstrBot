from types import SimpleNamespace

import httpx
import pytest

from astrbot.core.exceptions import EmptyModelOutputError
import astrbot.core.provider.sources.request_retry as request_retry
from astrbot.core.provider.entities import LLMResponse
from astrbot.core.provider.sources.gemini_source import ProviderGoogleGenAI


def test_gemini_empty_output_raises_empty_model_output_error():
    llm_response = LLMResponse(role="assistant")

    with pytest.raises(EmptyModelOutputError):
        ProviderGoogleGenAI._ensure_usable_response(
            llm_response,
            response_id="resp_empty",
            finish_reason="STOP",
        )


def test_gemini_reasoning_only_output_is_allowed():
    llm_response = LLMResponse(
        role="assistant",
        reasoning_content="chain of thought placeholder",
    )

    ProviderGoogleGenAI._ensure_usable_response(
        llm_response,
        response_id="resp_reasoning",
        finish_reason="STOP",
    )


@pytest.mark.asyncio
async def test_gemini_encode_image_data_uri():
    provider = ProviderGoogleGenAI.__new__(ProviderGoogleGenAI)
    data_uri = "data:image/jpeg;base64,UklGRkAAAABXRUJQVlA4"

    # Test encode_image_bs64 returns the data URI directly
    res = await provider.encode_image_bs64(data_uri)
    assert res == data_uri

    # Test assemble_context with a data URI in image_urls
    context = await provider.assemble_context(text="", image_urls=[data_uri])
    assert context["role"] == "user"
    assert len(context["content"]) == 2  # text placeholder + image_part
    assert context["content"][1]["type"] == "image_url"
    assert context["content"][1]["image_url"]["url"] == data_uri


def test_gemini_proxy_no_proxy_mounts(monkeypatch):
    import httpx
    # Mock environment variables
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1,cli-proxy-api")

    config = {
        "proxy": "http://mihomo:7897",
        "key": ["fake_key"],
        "api_base": "https://generativelanguage.googleapis.com",
    }

    provider = ProviderGoogleGenAI(config, {})

    client = provider._http_client
    assert client is not None

    # Verify mounts routing
    t_cli = client._transport_for_url(httpx.URL("http://cli-proxy-api:8317/v1beta/models"))
    t_google = client._transport_for_url(httpx.URL("https://generativelanguage.googleapis.com/v1beta/models"))

    # Bypassed local endpoint
    cli_proxy = getattr(t_cli, "_proxy_url", None) or getattr(getattr(t_cli, "_pool", None), "_proxy_url", None)
    assert cli_proxy is None

    # Proxied endpoint
    google_proxy = getattr(t_google, "_proxy_url", None) or getattr(getattr(t_google, "_pool", None), "_proxy_url", None)
    assert google_proxy is not None
    assert google_proxy.host == b"mihomo"
    assert google_proxy.port == 7897


@pytest.mark.asyncio
async def test_gemini_get_models_retries_transient_request_error(monkeypatch):
    monkeypatch.setattr(request_retry, "REQUEST_RETRY_WAIT_MIN_S", 0)
    monkeypatch.setattr(request_retry, "REQUEST_RETRY_WAIT_MAX_S", 0)

    class FakeModels:
        def __init__(self):
            self.calls = 0

        async def list(self):
            self.calls += 1
            if self.calls == 1:
                raise httpx.ConnectError("temporary connection failure")
            return [
                SimpleNamespace(
                    name="models/gemini-a",
                    supported_actions=["generateContent"],
                ),
                SimpleNamespace(
                    name="models/gemini-b",
                    supported_actions=["embedContent"],
                ),
            ]

    models = FakeModels()
    provider = ProviderGoogleGenAI.__new__(ProviderGoogleGenAI)
    provider.client = SimpleNamespace(models=models)

    assert await provider.get_models() == ["gemini-a"]
    assert models.calls == 2
