# backend/tests/test_llm_client.py
"""
Unit tests for app.shared.llm_client (W1 D5 & W2 D4 deliverable).

Tests:
  - Primary -> Fallback routing for Judge (Groq -> Gemini)
  - Primary -> Fallback routing for VLM (Gemini -> Groq)
  - Exhaustion of providers raising LLMClientError
  - generate_vision validation (requires images)
  - Structured JSON parsing and Pydantic validation (generate_json)
  - Markdown JSON block stripping repair
  - HTTP retry/backoff on 429/5xx status
  - Health check connectivity
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pydantic import BaseModel, Field

from app.shared.llm_client import (
    FinishReason,
    ImageInput,
    LLMCapability,
    LLMClient,
    LLMClientConfig,
    LLMClientError,
    LLMMessage,
    LLMProvider,
    LLMRequest,
    LLMTask,
    ModelRoute,
    ModelRouting,
    ProviderConfig,
    ResponseFormat,
    TaskRouting,
)


class JudgeResultSchema(BaseModel):
    verdict: str
    fraud_probability: int = Field(ge=0, le=100)
    confidence: int = Field(ge=0, le=100)
    category: str


def make_test_config() -> LLMClientConfig:
    groq_cfg = ProviderConfig(
        provider=LLMProvider.GROQ,
        api_key="test-groq-key",
        base_url="https://api.groq.test/v1",
        text_model="groq-judge-test",
        vision_model="groq-vlm-test",
        timeout_seconds=5.0,
        max_retries=2,
        initial_backoff_seconds=0.01,
        max_backoff_seconds=0.05,
    )
    gemini_cfg = ProviderConfig(
        provider=LLMProvider.GEMINI,
        api_key="test-gemini-key",
        base_url="https://api.gemini.test/v1",
        text_model="gemini-judge-test",
        vision_model="gemini-vlm-test",
        timeout_seconds=5.0,
        max_retries=2,
        initial_backoff_seconds=0.01,
        max_backoff_seconds=0.05,
    )
    routing = ModelRouting(
        judge=TaskRouting(
            primary=ModelRoute(provider=LLMProvider.GROQ, model="groq-judge-test"),
            fallback=ModelRoute(provider=LLMProvider.GEMINI, model="gemini-judge-test"),
        ),
        vlm=TaskRouting(
            primary=ModelRoute(provider=LLMProvider.GEMINI, model="gemini-vlm-test"),
            fallback=ModelRoute(provider=LLMProvider.GROQ, model="groq-vlm-test"),
        ),
    )
    return LLMClientConfig(
        groq=groq_cfg,
        gemini=gemini_cfg,
        max_retries=2,
        request_timeout_seconds=5.0,
        initial_backoff_seconds=0.01,
        max_backoff_seconds=0.05,
        routing=routing,
    )


# ── Text Generation (Judge) Tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_judge_primary_groq_success():
    """Judge task queries Groq primarily and succeeds without fallback."""
    config = make_test_config()
    mock_http = AsyncMock(spec=httpx.AsyncClient)

    groq_response = {
        "choices": [
            {
                "message": {"role": "assistant", "content": "VERDICT: REJECT - Counterfeit chip"},
                "finish_reason": "stop",
            }
        ]
    }
    mock_http.post.return_value = httpx.Response(
        status_code=200, json=groq_response, request=httpx.Request("POST", "https://api.groq.test/v1/chat/completions")
    )

    client = LLMClient(config=config, http_client=mock_http)
    req = LLMRequest(
        task=LLMTask.JUDGE,
        capability=LLMCapability.TEXT,
        messages=[LLMMessage(role="user", content="Analyze evidence")],
    )

    resp = await client.generate_text(req)

    assert resp.provider == LLMProvider.GROQ
    assert resp.model == "groq-judge-test"
    assert resp.used_fallback is False
    assert "REJECT" in resp.content
    assert resp.finish_reason == FinishReason.STOP


@pytest.mark.asyncio
async def test_judge_primary_fails_uses_gemini_fallback():
    """Judge task falls back to Gemini when Groq fails with 500 error."""
    config = make_test_config()
    mock_http = AsyncMock(spec=httpx.AsyncClient)

    gemini_response = {
        "candidates": [
            {
                "content": {"parts": [{"text": "VERDICT: ACCEPT"}]},
                "finishReason": "STOP",
            }
        ]
    }

    # First call (Groq) fails with 500, Second call (Gemini) succeeds with 200
    mock_http.post.side_effect = [
        httpx.Response(status_code=500, text="Internal Server Error", request=httpx.Request("POST", "https://api.groq.test")),
        httpx.Response(status_code=500, text="Internal Server Error", request=httpx.Request("POST", "https://api.groq.test")),
        httpx.Response(status_code=200, json=gemini_response, request=httpx.Request("POST", "https://api.gemini.test")),
    ]

    client = LLMClient(config=config, http_client=mock_http)
    req = LLMRequest(
        task=LLMTask.JUDGE,
        capability=LLMCapability.TEXT,
        messages=[LLMMessage(role="user", content="Analyze evidence")],
    )

    resp = await client.generate_text(req)

    assert resp.provider == LLMProvider.GEMINI
    assert resp.model == "gemini-judge-test"
    assert resp.used_fallback is True
    assert "ACCEPT" in resp.content


@pytest.mark.asyncio
async def test_all_providers_exhausted_raises_client_error():
    """When both primary and fallback fail, LLMClientError is raised."""
    config = make_test_config()
    mock_http = AsyncMock(spec=httpx.AsyncClient)

    mock_http.post.return_value = httpx.Response(
        status_code=503, text="Service Unavailable", request=httpx.Request("POST", "https://api.test")
    )

    client = LLMClient(config=config, http_client=mock_http)
    req = LLMRequest(
        task=LLMTask.JUDGE,
        capability=LLMCapability.TEXT,
        messages=[LLMMessage(role="user", content="Analyze evidence")],
    )

    with pytest.raises(LLMClientError) as exc_info:
        await client.generate_text(req)

    assert "All providers exhausted" in str(exc_info.value)
    assert len(exc_info.value.errors) >= 2


# ── Vision Generation (VLM) Tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_vlm_primary_gemini_success():
    """VLM task queries Gemini primarily and parses multimodal response."""
    config = make_test_config()
    mock_http = AsyncMock(spec=httpx.AsyncClient)

    gemini_response = {
        "candidates": [
            {
                "content": {"parts": [{"text": "Missing SMD capacitor at C14"}]},
                "finishReason": "STOP",
            }
        ]
    }
    mock_http.post.return_value = httpx.Response(
        status_code=200, json=gemini_response, request=httpx.Request("POST", "https://api.gemini.test")
    )

    client = LLMClient(config=config, http_client=mock_http)
    req = LLMRequest(
        task=LLMTask.VLM,
        capability=LLMCapability.VISION,
        messages=[LLMMessage(role="user", content="Inspect ROI")],
        images=[ImageInput(source="fake_base64_data", mime_type="image/jpeg")],
    )

    resp = await client.generate_vision(req)

    assert resp.provider == LLMProvider.GEMINI
    assert resp.model == "gemini-vlm-test"
    assert resp.used_fallback is False
    assert "capacitor" in resp.content


@pytest.mark.asyncio
async def test_generate_vision_requires_images():
    """Calling generate_vision without images raises ValueError."""
    config = make_test_config()
    mock_http = AsyncMock(spec=httpx.AsyncClient)

    client = LLMClient(config=config, http_client=mock_http)
    req = LLMRequest(
        task=LLMTask.VLM,
        capability=LLMCapability.VISION,
        messages=[LLMMessage(role="user", content="Inspect")],
        images=[],
    )

    with pytest.raises(ValueError) as exc_info:
        await client.generate_vision(req)

    assert "requires at least one image" in str(exc_info.value)


# ── Structured JSON Generation Tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_json_validates_pydantic_schema():
    """generate_json parses valid JSON response into a typed Pydantic instance."""
    config = make_test_config()
    mock_http = AsyncMock(spec=httpx.AsyncClient)

    groq_json_payload = {
        "verdict": "REJECT",
        "fraud_probability": 92,
        "confidence": 96,
        "category": "Counterfeit Component",
    }
    groq_response = {
        "choices": [
            {
                "message": {"role": "assistant", "content": json.dumps(groq_json_payload)},
                "finish_reason": "stop",
            }
        ]
    }
    mock_http.post.return_value = httpx.Response(
        status_code=200, json=groq_response, request=httpx.Request("POST", "https://api.groq.test")
    )

    client = LLMClient(config=config, http_client=mock_http)
    req = LLMRequest(
        task=LLMTask.JUDGE,
        capability=LLMCapability.TEXT,
        messages=[LLMMessage(role="user", content="Deliver verdict")],
    )

    raw_resp, parsed_data = await client.generate_json(req, JudgeResultSchema)

    assert isinstance(parsed_data, JudgeResultSchema)
    assert parsed_data.verdict == "REJECT"
    assert parsed_data.fraud_probability == 92
    assert parsed_data.confidence == 96
    assert parsed_data.category == "Counterfeit Component"


@pytest.mark.asyncio
async def test_generate_json_repairs_markdown_fences():
    """generate_json handles responses wrapped in ```json ... ``` markdown codeblocks."""
    config = make_test_config()
    mock_http = AsyncMock(spec=httpx.AsyncClient)

    markdown_wrapped = """```json
    {
        "verdict": "ACCEPT",
        "fraud_probability": 5,
        "confidence": 98,
        "category": "Genuine"
    }
    ```"""
    groq_response = {
        "choices": [
            {
                "message": {"role": "assistant", "content": markdown_wrapped},
                "finish_reason": "stop",
            }
        ]
    }
    mock_http.post.return_value = httpx.Response(
        status_code=200, json=groq_response, request=httpx.Request("POST", "https://api.groq.test")
    )

    client = LLMClient(config=config, http_client=mock_http)
    req = LLMRequest(
        task=LLMTask.JUDGE,
        capability=LLMCapability.TEXT,
        messages=[LLMMessage(role="user", content="Deliver verdict")],
    )

    raw_resp, parsed_data = await client.generate_json(req, JudgeResultSchema)

    assert parsed_data.verdict == "ACCEPT"
    assert parsed_data.fraud_probability == 5


# ── Health Check Tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check_connectivity():
    """Health check queries models endpoint for configured providers."""
    config = make_test_config()
    mock_http = AsyncMock(spec=httpx.AsyncClient)

    mock_http.get.return_value = httpx.Response(
        status_code=200, json={"data": []}, request=httpx.Request("GET", "https://api.test")
    )

    client = LLMClient(config=config, http_client=mock_http)
    health = await client.health_check()

    assert health[LLMProvider.GROQ] is True
    assert health[LLMProvider.GEMINI] is True
