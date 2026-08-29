from __future__ import annotations

import asyncio
import base64
import logging
import random
from enum import Enum
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger("app.shared.llm_client")


class LLMRole(str, Enum):
    JUDGE = "judge"
    VLM = "vlm"


class LLMProvider(str, Enum):
    GEMINI = "gemini"
    GROQ = "groq"


class LLMCallError(Exception):
    def __init__(self, message: str, provider: LLMProvider, status_code: int | None = None) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code


class AllProvidersFailedError(Exception):
    def __init__(self, errors: list[LLMCallError]) -> None:
        self.errors = errors
        msg = "; ".join(f"{e.provider.value}: {e}" for e in errors)
        super().__init__(f"all providers failed -> {msg}")


class LLMUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    content: str
    provider_used: LLMProvider
    model_used: str
    latency_ms: int
    usage: LLMUsage = Field(default_factory=LLMUsage)
    raw: dict[str, Any] = Field(default_factory=dict)


class ModelRoute(BaseModel):
    provider: LLMProvider
    model: str
    is_vision: bool = False


# Primary & Fallback Route Hierarchy:
# VLM (Vision): Primary = Gemini 3.5 Flash -> Fallback = Groq Qwen 3.6 27B
# Judge (Reasoning): Primary = Groq GPT-OSS 20B -> Fallback = Gemini 3.5 Flash
ROUTES: dict[LLMRole, list[ModelRoute]] = {
    LLMRole.VLM: [
        ModelRoute(
            provider=LLMProvider.GEMINI,
            model=settings.GEMINI_VLM_MODEL,
            is_vision=True,
        ),
        ModelRoute(
            provider=LLMProvider.GROQ,
            model=settings.GROQ_VLM_MODEL,
            is_vision=True,
        ),
    ],
    LLMRole.JUDGE: [
        ModelRoute(
            provider=LLMProvider.GROQ,
            model=settings.GROQ_JUDGE_MODEL,
        ),
        ModelRoute(
            provider=LLMProvider.GEMINI,
            model=settings.GEMINI_JUDGE_MODEL,
        ),
    ],
}

MAX_RETRIES_PER_PROVIDER = 3
BASE_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 20.0
REQUEST_TIMEOUT_SECONDS = 60.0
RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


class LLMClient:
    """Unified async client for Google Gemini + Groq with retry/backoff and failover."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def chat(
        self,
        role: LLMRole,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1024,
        image_base64: str | None = None,
        image_media_type: str = "image/jpeg",
        response_format_json: bool = False,
    ) -> LLMResponse:
        """Run chat completion for given role, failing over across routed providers."""
        routes = ROUTES[role]
        errors: list[LLMCallError] = []

        for route in routes:
            if image_base64 and not route.is_vision:
                continue
            try:
                return await self._call_with_retry(
                    route=route,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    image_base64=image_base64,
                    image_media_type=image_media_type,
                    response_format_json=response_format_json,
                )
            except LLMCallError as exc:
                logger.warning(
                    "provider_failed role=%s provider=%s model=%s error=%s",
                    role.value,
                    route.provider.value,
                    route.model,
                    exc,
                )
                errors.append(exc)
                continue

        raise AllProvidersFailedError(errors)

    async def _call_with_retry(
        self,
        route: ModelRoute,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        image_base64: str | None,
        image_media_type: str,
        response_format_json: bool,
    ) -> LLMResponse:
        last_error: LLMCallError | None = None

        for attempt in range(1, MAX_RETRIES_PER_PROVIDER + 1):
            try:
                return await self._single_call(
                    route=route,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    image_base64=image_base64,
                    image_media_type=image_media_type,
                    response_format_json=response_format_json,
                )
            except LLMCallError as exc:
                last_error = exc
                retryable = exc.status_code is None or exc.status_code in RETRYABLE_STATUS_CODES
                if not retryable or attempt == MAX_RETRIES_PER_PROVIDER:
                    raise
                backoff = min(BASE_BACKOFF_SECONDS * (2 ** (attempt - 1)), MAX_BACKOFF_SECONDS)
                jitter = random.uniform(0, backoff * 0.25)
                sleep_for = backoff + jitter
                logger.info(
                    "retrying provider=%s model=%s attempt=%s sleep=%.2fs",
                    route.provider.value,
                    route.model,
                    attempt,
                    sleep_for,
                )
                await asyncio.sleep(sleep_for)

        assert last_error is not None
        raise last_error

    async def _single_call(
        self,
        route: ModelRoute,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        image_base64: str | None,
        image_media_type: str,
        response_format_json: bool,
    ) -> LLMResponse:
        start = asyncio.get_event_loop().time()

        if route.provider == LLMProvider.GEMINI:
            url = f"{settings.GEMINI_BASE_URL.rstrip('/')}/models/{route.model}:generateContent?key={settings.GEMINI_API_KEY}"
            headers = {"Content-Type": "application/json"}
            
            # Format Gemini payload
            contents = []
            for msg in messages:
                role = "model" if msg.get("role") in ("assistant", "model") else "user"
                parts = []
                content = msg.get("content")
                if isinstance(content, str):
                    parts.append({"text": content})
                elif isinstance(content, list):
                    for item in content:
                        if item.get("type") == "text":
                            parts.append({"text": item.get("text", "")})
                        elif item.get("type") == "image_url":
                            data_url = item.get("image_url", {}).get("url", "")
                            if ";base64," in data_url:
                                h, b64 = data_url.split(";base64,")
                                m_type = h.replace("data:", "")
                                parts.append({"inline_data": {"mime_type": m_type, "data": b64}})
                contents.append({"role": role, "parts": parts})

            if image_base64:
                if contents and contents[-1]["role"] == "user":
                    contents[-1]["parts"].append({
                        "inline_data": {"mime_type": image_media_type, "data": image_base64}
                    })
                else:
                    contents.append({
                        "role": "user",
                        "parts": [{"inline_data": {"mime_type": image_media_type, "data": image_base64}}]
                    })

            body: dict[str, Any] = {
                "contents": contents,
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                },
            }
            if response_format_json:
                body["generationConfig"]["responseMimeType"] = "application/json"

        elif route.provider == LLMProvider.GROQ:
            base_url = settings.GROQ_BASE_URL.rstrip("/")
            url = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            }
            payload_messages = self._build_messages(messages, image_base64, image_media_type)
            body = {
                "model": route.model,
                "messages": payload_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if response_format_json:
                body["response_format"] = {"type": "json_object"}
        else:
            raise ValueError(f"unknown provider: {route.provider}")

        try:
            resp = await self._client.post(url, headers=headers, json=body)
        except httpx.RequestError as exc:
            raise LLMCallError(f"network error: {exc}", provider=route.provider) from exc

        latency_ms = int((asyncio.get_event_loop().time() - start) * 1000)

        if resp.status_code >= 400:
            raise LLMCallError(
                f"http {resp.status_code}: {resp.text[:500]}",
                provider=route.provider,
                status_code=resp.status_code,
            )

        try:
            data = resp.json()
            if route.provider == LLMProvider.GEMINI:
                candidate = data.get("candidates", [{}])[0]
                parts = candidate.get("content", {}).get("parts", [])
                text_chunks = [p.get("text", "") for p in parts if isinstance(p, dict) and "text" in p]
                content = "\n".join(text_chunks) if text_chunks else ""
                usage_meta = data.get("usageMetadata", {})
                prompt_tokens = usage_meta.get("promptTokenCount", 0)
                completion_tokens = usage_meta.get("candidatesTokenCount", 0)
                total_tokens = usage_meta.get("totalTokenCount", 0)
            else:  # GROQ
                choices = data.get("choices", [{}])
                content = choices[0].get("message", {}).get("content", "") if choices else ""
                usage_raw = data.get("usage", {})
                prompt_tokens = usage_raw.get("prompt_tokens", 0)
                completion_tokens = usage_raw.get("completion_tokens", 0)
                total_tokens = usage_raw.get("total_tokens", 0)
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMCallError(f"malformed response: {exc}", provider=route.provider) from exc

        return LLMResponse(
            content=content,
            provider_used=route.provider,
            model_used=route.model,
            latency_ms=latency_ms,
            usage=LLMUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
            raw=data,
        )

    def _build_messages(
        self,
        messages: list[dict[str, Any]],
        image_base64: str | None,
        image_media_type: str,
    ) -> list[dict[str, Any]]:
        if not image_base64:
            return messages

        out = [m for m in messages if m.get("role") != "user"]
        user_messages = [m for m in messages if m.get("role") == "user"]
        text_prompt = user_messages[-1]["content"] if user_messages else ""

        image_url = f"data:{image_media_type};base64,{image_base64}"
        out.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text_prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        )
        return out

    @staticmethod
    def encode_image(image_bytes: bytes) -> str:
        return base64.b64encode(image_bytes).decode("utf-8")


llm_client = LLMClient()