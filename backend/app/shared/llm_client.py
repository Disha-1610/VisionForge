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
    NVIDIA_NIM = "nvidia_nim"
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


ROUTES: dict[LLMRole, list[ModelRoute]] = {
    LLMRole.JUDGE: [
        ModelRoute(provider=LLMProvider.GROQ, model="openai/gpt-oss-20b"),
        ModelRoute(provider=LLMProvider.NVIDIA_NIM, model="nvidia/nemotron-3-super-120b-a12b"),
    ],
    LLMRole.VLM: [
        ModelRoute(
            provider=LLMProvider.NVIDIA_NIM,
            model="nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
            is_vision=True,
        ),
        ModelRoute(provider=LLMProvider.GROQ, model="qwen/qwen3.6-27b", is_vision=True),
    ],
}

NIM_BASE_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
GROQ_BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

MAX_RETRIES_PER_PROVIDER = 3
BASE_BACKOFF_SECONDS = 1.0
MAX_BACKOFF_SECONDS = 20.0
REQUEST_TIMEOUT_SECONDS = 60.0
RETRYABLE_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


class LLMClient:
    """Unified async client for NVIDIA NIM + Groq with retry/backoff and failover."""

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
        url, headers = self._provider_endpoint(route.provider)
        payload_messages = self._build_messages(messages, image_base64, image_media_type)

        body: dict[str, Any] = {
            "model": route.model,
            "messages": payload_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format_json:
            body["response_format"] = {"type": "json_object"}

        start = asyncio.get_event_loop().time()
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
            content = data["choices"][0]["message"]["content"]
            usage_raw = data.get("usage", {})
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMCallError(f"malformed response: {exc}", provider=route.provider) from exc

        return LLMResponse(
            content=content,
            provider_used=route.provider,
            model_used=route.model,
            latency_ms=latency_ms,
            usage=LLMUsage(
                prompt_tokens=usage_raw.get("prompt_tokens", 0),
                completion_tokens=usage_raw.get("completion_tokens", 0),
                total_tokens=usage_raw.get("total_tokens", 0),
            ),
            raw=data,
        )

    def _provider_endpoint(self, provider: LLMProvider) -> tuple[str, dict[str, str]]:
        if provider == LLMProvider.NVIDIA_NIM:
            base_url = settings.NVIDIA_NIM_BASE_URL.rstrip("/")
            endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
            return endpoint, {
                "Authorization": f"Bearer {settings.NVIDIA_NIM_API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        if provider == LLMProvider.GROQ:
            base_url = settings.GROQ_BASE_URL.rstrip("/")
            endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
            return endpoint, {
                "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                "Content-Type": "application/json",
            }
        raise ValueError(f"unknown provider: {provider}")

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