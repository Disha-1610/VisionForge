# backend/app/shared/llm_client.py
"""
Shared LLM Client — provider-agnostic text/vision generation with
primary -> fallback routing, retry/backoff, and structured JSON output.

Used exclusively by:
  - pipeline/agents/vlm_agent.py      (generate_vision)
  - pipeline/stages/judge.py          (generate_json / generate_text)

Routing (fixed per VisionForge MVP architecture):
  judge -> primary: groq/openai/gpt-oss-20b   | fallback: gemini/gemini-3.5-flash
  vlm   -> primary: gemini/gemini-3.5-flash   | fallback: groq/qwen/qwen3.8-27b
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, Optional, Protocol, TypeVar

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings

logger = logging.getLogger("visionforge.llm_client")

T = TypeVar("T", bound=BaseModel)


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #


class LLMProvider(str, Enum):
    GROQ = "groq"
    GEMINI = "gemini"


class LLMCapability(str, Enum):
    TEXT = "text"
    VISION = "vision"


class LLMTask(str, Enum):
    JUDGE = "judge"
    VLM = "vlm"


class FinishReason(str, Enum):
    STOP = "stop"
    LENGTH = "length"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"
    UNKNOWN = "unknown"


class ResponseFormat(str, Enum):
    TEXT = "text"
    JSON = "json"


# --------------------------------------------------------------------------- #
# Data models
# --------------------------------------------------------------------------- #


class ImageInput(BaseModel):
    source: str = Field(..., description="Local file path or base64-encoded payload")
    mime_type: str = Field(..., description="e.g. image/jpeg, image/png")


class LLMMessage(BaseModel):
    role: str = Field(..., pattern="^(system|user|assistant)$")
    content: str


class LLMRequest(BaseModel):
    task: LLMTask
    capability: LLMCapability
    messages: list[LLMMessage]
    images: Optional[list[ImageInput]] = None
    model: Optional[str] = None
    temperature: float = 0.2
    max_tokens: int = 2048
    response_format: ResponseFormat = ResponseFormat.TEXT
    inspection_id: Optional[str] = None
    stage_name: Optional[str] = None


class LLMResponse(BaseModel, Generic[T]):
    provider: LLMProvider
    model: str
    content: str
    parsed: Optional[dict[str, Any]] = None
    finish_reason: FinishReason
    latency_ms: float
    attempt: int
    used_fallback: bool


class LLMErrorInfo(BaseModel):
    provider: LLMProvider
    model: str
    code: str
    message: str
    retryable: bool
    attempt: int
    failover_available: bool


class LLMClientError(Exception):
    """Raised when all configured providers/models are exhausted."""

    def __init__(self, message: str, errors: list[LLMErrorInfo]) -> None:
        super().__init__(message)
        self.errors = errors


# --------------------------------------------------------------------------- #
# Provider configuration
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ProviderConfig:
    provider: LLMProvider
    api_key: str
    base_url: str
    text_model: str
    vision_model: str
    timeout_seconds: float = 30.0
    max_retries: int = 3
    initial_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 8.0


@dataclass(frozen=True)
class ModelRoute:
    provider: LLMProvider
    model: str


@dataclass(frozen=True)
class TaskRouting:
    primary: ModelRoute
    fallback: ModelRoute


@dataclass(frozen=True)
class ModelRouting:
    judge: TaskRouting
    vlm: TaskRouting


DEFAULT_ROUTING = ModelRouting(
    judge=TaskRouting(
        primary=ModelRoute(
            provider=LLMProvider.GROQ,
            model=getattr(settings, "GROQ_JUDGE_MODEL", "openai/gpt-oss-20b"),
        ),
        fallback=ModelRoute(
            provider=LLMProvider.GEMINI,
            model=getattr(settings, "GEMINI_JUDGE_MODEL", "gemini-3.5-flash"),
        ),
    ),
    vlm=TaskRouting(
        primary=ModelRoute(
            provider=LLMProvider.GEMINI,
            model=getattr(settings, "GEMINI_VLM_MODEL", "gemini-3.5-flash"),
        ),
        fallback=ModelRoute(
            provider=LLMProvider.GROQ,
            model=getattr(settings, "GROQ_VLM_MODEL", "qwen/qwen3.8-27b"),
        ),
    ),
)


@dataclass(frozen=True)
class LLMClientConfig:
    groq: ProviderConfig
    gemini: ProviderConfig
    max_retries: int = 3
    request_timeout_seconds: float = 30.0
    initial_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 8.0
    routing: ModelRouting = field(default_factory=lambda: DEFAULT_ROUTING)


def build_default_config() -> LLMClientConfig:
    """Build provider config from environment/settings (no secrets logged)."""
    groq_cfg = ProviderConfig(
        provider=LLMProvider.GROQ,
        api_key=settings.GROQ_API_KEY,
        base_url=settings.GROQ_BASE_URL or "https://api.groq.com/openai/v1",
        text_model=settings.GROQ_JUDGE_MODEL or "openai/gpt-oss-20b",
        vision_model=settings.GROQ_VLM_MODEL or "qwen/qwen3.8-27b",
        timeout_seconds=getattr(settings, "LLM_TIMEOUT_SECONDS", 30.0),
        max_retries=getattr(settings, "LLM_MAX_RETRIES", 3),
        initial_backoff_seconds=getattr(settings, "LLM_INITIAL_BACKOFF_SECONDS", 1.0),
        max_backoff_seconds=getattr(settings, "LLM_MAX_BACKOFF_SECONDS", 8.0),
    )
    gemini_cfg = ProviderConfig(
        provider=LLMProvider.GEMINI,
        api_key=settings.GEMINI_API_KEY,
        base_url=settings.GEMINI_BASE_URL
        or "https://generativelanguage.googleapis.com/v1beta",
        text_model=settings.GEMINI_JUDGE_MODEL or "gemini-3.5-flash",
        vision_model=settings.GEMINI_VLM_MODEL or "gemini-3.5-flash",
        timeout_seconds=getattr(settings, "LLM_TIMEOUT_SECONDS", 30.0),
        max_retries=getattr(settings, "LLM_MAX_RETRIES", 3),
        initial_backoff_seconds=getattr(settings, "LLM_INITIAL_BACKOFF_SECONDS", 1.0),
        max_backoff_seconds=getattr(settings, "LLM_MAX_BACKOFF_SECONDS", 8.0),
    )
    return LLMClientConfig(
        groq=groq_cfg,
        gemini=gemini_cfg,
        max_retries=getattr(settings, "LLM_MAX_RETRIES", 3),
        request_timeout_seconds=getattr(settings, "LLM_TIMEOUT_SECONDS", 30.0),
        initial_backoff_seconds=getattr(settings, "LLM_INITIAL_BACKOFF_SECONDS", 1.0),
        max_backoff_seconds=getattr(settings, "LLM_MAX_BACKOFF_SECONDS", 8.0),
        routing=DEFAULT_ROUTING,
    )


# --------------------------------------------------------------------------- #
# Provider client protocol + implementations
# --------------------------------------------------------------------------- #


class LLMProviderClient(Protocol):
    provider: LLMProvider

    async def generate_text(self, request: LLMRequest, model: str) -> LLMResponse: ...

    async def generate_vision(self, request: LLMRequest, model: str) -> LLMResponse: ...

    async def health_check(self) -> bool: ...


def _extract_retryable(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


class BaseProviderClient:
    """Shared HTTP plumbing for provider clients."""

    provider: LLMProvider

    def __init__(self, config: ProviderConfig, client: httpx.AsyncClient) -> None:
        self._config = config
        self._client = client

    async def _post_with_retry(
        self,
        url: str,
        headers: dict[str, str],
        json_body: dict[str, Any],
    ) -> tuple[dict[str, Any], int, float]:
        """POST with exponential backoff + jitter. Returns (body, attempt, latency_ms)."""
        attempt = 0
        last_exc: Exception | None = None
        backoff = self._config.initial_backoff_seconds

        while attempt < self._config.max_retries:
            attempt += 1
            start = time.perf_counter()
            try:
                response = await self._client.post(
                    url,
                    headers=headers,
                    json=json_body,
                    timeout=self._config.timeout_seconds,
                )
                latency_ms = (time.perf_counter() - start) * 1000.0

                if response.status_code == 200:
                    return response.json(), attempt, latency_ms

                retryable = _extract_retryable(response.status_code)
                body_text = response.text[:500]
                logger.warning(
                    "provider=%s status=%s attempt=%s retryable=%s body=%s",
                    self.provider.value,
                    response.status_code,
                    attempt,
                    retryable,
                    body_text,
                )
                if not retryable or attempt >= self._config.max_retries:
                    raise LLMProviderHTTPError(
                        provider=self.provider,
                        status_code=response.status_code,
                        message=body_text,
                        retryable=retryable,
                        attempt=attempt,
                    )

            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                logger.warning(
                    "provider=%s transport_error=%s attempt=%s",
                    self.provider.value,
                    str(exc),
                    attempt,
                )
                if attempt >= self._config.max_retries:
                    raise LLMProviderHTTPError(
                        provider=self.provider,
                        status_code=0,
                        message=f"transport error: {exc}",
                        retryable=True,
                        attempt=attempt,
                    ) from exc

            sleep_for = min(
                backoff + random.uniform(0, backoff * 0.25),
                self._config.max_backoff_seconds,
            )
            await asyncio.sleep(sleep_for)
            backoff = min(backoff * 2, self._config.max_backoff_seconds)

        # Should be unreachable, but guards against falling through the loop.
        raise LLMProviderHTTPError(
            provider=self.provider,
            status_code=0,
            message=f"exhausted retries: {last_exc}",
            retryable=False,
            attempt=attempt,
        )


class LLMProviderHTTPError(Exception):
    def __init__(
        self,
        provider: LLMProvider,
        status_code: int,
        message: str,
        retryable: bool,
        attempt: int,
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.message = message
        self.retryable = retryable
        self.attempt = attempt


class GroqProviderClient(BaseProviderClient):
    provider = LLMProvider.GROQ

    async def generate_text(self, request: LLMRequest, model: str) -> LLMResponse:
        url = f"{self._config.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        body: dict[str, Any] = {
            "model": model,
            "messages": [m.model_dump() for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.response_format == ResponseFormat.JSON:
            body["response_format"] = {"type": "json_object"}

        raw, attempt, latency_ms = await self._post_with_retry(url, headers, body)
        return self._parse_openai_style(raw, model, attempt, latency_ms, request)

    async def generate_vision(self, request: LLMRequest, model: str) -> LLMResponse:
        url = f"{self._config.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
        }
        content_blocks: list[dict[str, Any]] = []
        text_parts = "\n".join(m.content for m in request.messages if m.role == "user")
        if text_parts:
            content_blocks.append({"type": "text", "text": text_parts})
        for img in request.images or []:
            content_blocks.append(
                {
                    "type": "image_url",
                    "image_url": {"url": self._to_data_url(img)},
                }
            )

        system_messages = [m.model_dump() for m in request.messages if m.role == "system"]
        body: dict[str, Any] = {
            "model": model,
            "messages": [
                *system_messages,
                {"role": "user", "content": content_blocks},
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.response_format == ResponseFormat.JSON:
            body["response_format"] = {"type": "json_object"}

        raw, attempt, latency_ms = await self._post_with_retry(url, headers, body)
        return self._parse_openai_style(raw, model, attempt, latency_ms, request)

    async def health_check(self) -> bool:
        url = f"{self._config.base_url}/models"
        headers = {"Authorization": f"Bearer {self._config.api_key}"}
        try:
            response = await self._client.get(
                url, headers=headers, timeout=self._config.timeout_seconds
            )
            return response.status_code == 200
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            logger.warning("groq health_check failed: %s", exc)
            return False

    @staticmethod
    def _to_data_url(image: ImageInput) -> str:
        if image.source.startswith("http://") or image.source.startswith("https://"):
            return image.source
        return f"data:{image.mime_type};base64,{image.source}"

    @staticmethod
    def _parse_openai_style(
        raw: dict[str, Any],
        model: str,
        attempt: int,
        latency_ms: float,
        request: LLMRequest,
    ) -> LLMResponse:
        choices = raw.get("choices") or []
        if not choices:
            raise LLMProviderHTTPError(
                provider=LLMProvider.GROQ,
                status_code=200,
                message="empty choices array in response",
                retryable=False,
                attempt=attempt,
            )
        choice = choices[0]
        content = choice.get("message", {}).get("content", "") or ""
        finish_reason_raw = choice.get("finish_reason", "stop")
        finish_reason = _map_finish_reason(finish_reason_raw)

        parsed = None
        if request.response_format == ResponseFormat.JSON:
            parsed = _safe_json_loads(content)

        return LLMResponse(
            provider=LLMProvider.GROQ,
            model=model,
            content=content,
            parsed=parsed,
            finish_reason=finish_reason,
            latency_ms=latency_ms,
            attempt=attempt,
            used_fallback=False,
        )


class GeminiProviderClient(BaseProviderClient):
    provider = LLMProvider.GEMINI

    async def generate_text(self, request: LLMRequest, model: str) -> LLMResponse:
        return await self._generate(request, model, images=None)

    async def generate_vision(self, request: LLMRequest, model: str) -> LLMResponse:
        return await self._generate(request, model, images=request.images)

    async def _generate(
        self,
        request: LLMRequest,
        model: str,
        images: Optional[list[ImageInput]],
    ) -> LLMResponse:
        url = (
            f"{self._config.base_url}/models/{model}:generateContent"
            f"?key={self._config.api_key}"
        )
        headers = {"Content-Type": "application/json"}

        parts: list[dict[str, Any]] = []
        user_text = "\n".join(m.content for m in request.messages if m.role != "system")
        if user_text:
            parts.append({"text": user_text})
        for img in images or []:
            parts.append(
                {
                    "inline_data": {
                        "mime_type": img.mime_type,
                        "data": img.source,
                    }
                }
            )

        system_text = "\n".join(m.content for m in request.messages if m.role == "system")

        body: dict[str, Any] = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }
        if system_text:
            body["systemInstruction"] = {"parts": [{"text": system_text}]}
        if request.response_format == ResponseFormat.JSON:
            body["generationConfig"]["responseMimeType"] = "application/json"

        raw, attempt, latency_ms = await self._post_with_retry(url, headers, body)
        return self._parse_gemini_response(raw, model, attempt, latency_ms, request)

    async def health_check(self) -> bool:
        url = f"{self._config.base_url}/models?key={self._config.api_key}"
        try:
            response = await self._client.get(url, timeout=self._config.timeout_seconds)
            return response.status_code == 200
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            logger.warning("gemini health_check failed: %s", exc)
            return False

    @staticmethod
    def _parse_gemini_response(
        raw: dict[str, Any],
        model: str,
        attempt: int,
        latency_ms: float,
        request: LLMRequest,
    ) -> LLMResponse:
        candidates = raw.get("candidates") or []
        if not candidates:
            block_reason = raw.get("promptFeedback", {}).get("blockReason")
            raise LLMProviderHTTPError(
                provider=LLMProvider.GEMINI,
                status_code=200,
                message=f"no candidates returned (blockReason={block_reason})",
                retryable=False,
                attempt=attempt,
            )
        candidate = candidates[0]
        content_parts = candidate.get("content", {}).get("parts", [])
        content = "".join(p.get("text", "") for p in content_parts)
        finish_reason_raw = candidate.get("finishReason", "STOP")
        finish_reason = _map_finish_reason(finish_reason_raw.lower())

        parsed = None
        if request.response_format == ResponseFormat.JSON:
            parsed = _safe_json_loads(content)

        return LLMResponse(
            provider=LLMProvider.GEMINI,
            model=model,
            content=content,
            parsed=parsed,
            finish_reason=finish_reason,
            latency_ms=latency_ms,
            attempt=attempt,
            used_fallback=False,
        )


def _map_finish_reason(raw: str) -> FinishReason:
    mapping = {
        "stop": FinishReason.STOP,
        "length": FinishReason.LENGTH,
        "max_tokens": FinishReason.LENGTH,
        "content_filter": FinishReason.CONTENT_FILTER,
        "safety": FinishReason.CONTENT_FILTER,
    }
    return mapping.get(raw, FinishReason.UNKNOWN)


def _safe_json_loads(content: str) -> Optional[dict[str, Any]]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return result
        logger.warning("parsed JSON is not an object: %s", type(result))
        return None
    except json.JSONDecodeError as exc:
        logger.warning("failed to parse JSON content: %s", exc)
        return None


# --------------------------------------------------------------------------- #
# LLMClient — public shared-service interface
# --------------------------------------------------------------------------- #


class LLMClient:
    """
    Provider-agnostic LLM/VLM client with task-based primary -> fallback
    routing, retry/backoff, and structured JSON parsing.

    This is the ONLY place provider/API-specific logic should live.
    Agents and pipeline stages must call this client rather than
    talking to Groq/Gemini directly.
    """

    def __init__(
        self,
        config: Optional[LLMClientConfig] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._config = config or build_default_config()
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.AsyncClient()

        self._providers: dict[LLMProvider, LLMProviderClient] = {
            LLMProvider.GROQ: GroqProviderClient(self._config.groq, self._http_client),
            LLMProvider.GEMINI: GeminiProviderClient(self._config.gemini, self._http_client),
        }

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self._http_client.aclose()

    async def __aenter__(self) -> "LLMClient":
        return self

    async def __aexit__(self, *_exc_info: object) -> None:
        await self.aclose()

    def _route_for(self, task: LLMTask) -> TaskRouting:
        if task == LLMTask.JUDGE:
            return self._config.routing.judge
        if task == LLMTask.VLM:
            return self._config.routing.vlm
        raise ValueError(f"Unknown task for routing: {task}")

    async def _dispatch(
        self,
        request: LLMRequest,
        capability: LLMCapability,
    ) -> LLMResponse:
        routing = self._route_for(request.task)
        candidates: list[tuple[ModelRoute, bool]] = [
            (routing.primary, False),
            (routing.fallback, True),
        ]
        errors: list[LLMErrorInfo] = []

        for route, is_fallback in candidates:
            model = request.model if (request.model and not is_fallback) else route.model
            client = self._providers[route.provider]

            try:
                logger.info(
                    "llm_dispatch task=%s capability=%s provider=%s model=%s "
                    "fallback=%s inspection_id=%s stage=%s",
                    request.task.value,
                    capability.value,
                    route.provider.value,
                    model,
                    is_fallback,
                    request.inspection_id,
                    request.stage_name,
                )
                if capability == LLMCapability.VISION:
                    response = await client.generate_vision(request, model)
                else:
                    response = await client.generate_text(request, model)

                return response.model_copy(update={"used_fallback": is_fallback})

            except LLMProviderHTTPError as exc:
                failover_available = not is_fallback
                errors.append(
                    LLMErrorInfo(
                        provider=exc.provider,
                        model=model,
                        code=str(exc.status_code) if exc.status_code else "transport_error",
                        message=exc.message,
                        retryable=exc.retryable,
                        attempt=exc.attempt,
                        failover_available=failover_available,
                    )
                )
                logger.error(
                    "llm_provider_failed provider=%s model=%s code=%s "
                    "message=%s failover_available=%s",
                    exc.provider.value,
                    model,
                    exc.status_code,
                    exc.message,
                    failover_available,
                )
                continue

        raise LLMClientError(
            message=(
                f"All providers exhausted for task={request.task.value} "
                f"capability={capability.value}"
            ),
            errors=errors,
        )

    async def generate_text(self, request: LLMRequest) -> LLMResponse:
        """Text generation with task-based routing (primarily used by AI Judge)."""
        if request.capability != LLMCapability.TEXT:
            request = request.model_copy(update={"capability": LLMCapability.TEXT})
        return await self._dispatch(request, LLMCapability.TEXT)

    async def generate_vision(self, request: LLMRequest) -> LLMResponse:
        """Multimodal generation with task-based routing (used by VLM Agent)."""
        if request.capability != LLMCapability.VISION:
            request = request.model_copy(update={"capability": LLMCapability.VISION})
        if not request.images:
            raise ValueError("generate_vision requires at least one image in request.images")
        return await self._dispatch(request, LLMCapability.VISION)

    async def generate_json(
        self,
        request: LLMRequest,
        response_model: type[T],
    ) -> tuple[LLMResponse, T]:
        """
        Generate a response and validate it against `response_model`.
        Returns (raw LLMResponse, validated Pydantic instance).
        Raises LLMClientError if all providers fail, or ValidationError
        if the final successful response cannot be parsed into response_model.
        """
        json_request = request.model_copy(update={"response_format": ResponseFormat.JSON})

        if json_request.capability == LLMCapability.VISION:
            response = await self.generate_vision(json_request)
        else:
            response = await self.generate_text(json_request)

        if response.parsed is None:
            # One repair attempt: re-parse raw content defensively.
            repaired = _safe_json_loads(response.content)
            if repaired is None:
                raise LLMClientError(
                    message="Model response was not valid JSON",
                    errors=[
                        LLMErrorInfo(
                            provider=response.provider,
                            model=response.model,
                            code="invalid_json",
                            message="response content could not be parsed as JSON",
                            retryable=False,
                            attempt=response.attempt,
                            failover_available=False,
                        )
                    ],
                )
            response = response.model_copy(update={"parsed": repaired})

        try:
            validated = response_model.model_validate(response.parsed)
        except ValidationError:
            logger.error(
                "llm_json_schema_validation_failed provider=%s model=%s parsed=%s",
                response.provider.value,
                response.model,
                response.parsed,
            )
            raise

        return response, validated

    async def health_check(
        self, provider: Optional[LLMProvider] = None
    ) -> dict[LLMProvider, bool]:
        """Check connectivity for one or all configured providers."""
        targets = [provider] if provider else list(self._providers.keys())
        results: dict[LLMProvider, bool] = {}

        checks = await asyncio.gather(
            *(self._providers[p].health_check() for p in targets),
            return_exceptions=True,
        )
        for p, result in zip(targets, checks):
            if isinstance(result, Exception):
                logger.error("health_check_error provider=%s error=%s", p.value, result)
                results[p] = False
            else:
                results[p] = bool(result)

        return results


# --------------------------------------------------------------------------- #
# Singleton accessor (FastAPI dependency-friendly)
# --------------------------------------------------------------------------- #

_client_singleton: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """FastAPI dependency: returns a process-wide shared LLMClient instance."""
    global _client_singleton
    if _client_singleton is None:
        _client_singleton = LLMClient()
    return _client_singleton


async def shutdown_llm_client() -> None:
    """Call on app shutdown to release the shared httpx client."""
    global _client_singleton
    if _client_singleton is not None:
        await _client_singleton.aclose()
        _client_singleton = None