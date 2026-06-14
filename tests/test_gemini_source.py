import pytest

from astrbot.core.exceptions import EmptyModelOutputError
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
