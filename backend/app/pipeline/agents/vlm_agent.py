# backend/app/pipeline/agents/vlm_agent.py
"""
VLM Agent — general visual-anomaly evidence agent.

Receives cropped Golden ROI + Inspection ROI image pairs, sends them to a
vision-capable LLM (primary: Gemini 3.5 Flash, fallback: Groq Qwen 3.6 27B)
via the shared `llm_client`, and returns standardized `AgentEvidence` for
storage in the Evidence Store.

This agent MUST NOT perform ROI scheduling, evidence fusion, verdict
generation, policy decisions, or mutate another agent's evidence.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.shared.llm_client import (
    LLMClient,
    LLMClientError as LLMProviderError,
    LLMClientError as LLMTimeoutError,
    ImageInput as VisionImage,
    LLMRequest as VisionLLMRequest,
    LLMResponse as VisionLLMResponse,
)

logger = logging.getLogger(__name__)


# ============================================================
# Shared primitives
# ============================================================

ProductType = Literal["MOTHERBOARD", "BATTERY", "RAM"]
ROIType = Literal["TEXT", "LABEL", "STRUCTURAL", "VISUAL"]
EvidenceStatus = Literal["PASS", "FAIL", "INCONCLUSIVE", "ERROR"]
VLMProvider = Literal["gemini", "groq"]
AnomalySeverity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

_CONFIDENCE_MIN = 0.0
_CONFIDENCE_MAX = 1.0

_VALID_STATUSES: set[str] = {"PASS", "FAIL", "INCONCLUSIVE", "ERROR"}
_VALID_SEVERITIES: set[str] = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


# ============================================================
# Image / ROI contract
# ============================================================

class BoundingBox(BaseModel):
    model_config = ConfigDict(frozen=True)

    x: float = Field(ge=0.0)
    y: float = Field(ge=0.0)
    width: float = Field(gt=0.0)
    height: float = Field(gt=0.0)


class ROIMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    roi_id: str
    roi_type: ROIType
    name: str
    bounding_box: BoundingBox
    priority: int = Field(ge=0)
    critical: bool = False
    product_type: ProductType


class ImageInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    image_path: str
    image_id: str | None = None
    angle_id: str | None = None

    @field_validator("image_path")
    @classmethod
    def _validate_path_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("image_path must not be empty")
        return v


class VLMEvidenceInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    inspection_id: uuid.UUID
    roi: ROIMetadata

    golden_image: ImageInput
    inspection_image: ImageInput

    product_type: ProductType

    expected_description: str | None = None
    checkpoint: str | None = None

    metadata: dict[str, str | float | int | bool] | None = None


# ============================================================
# VLM finding contract
# ============================================================

class VLMAnomaly(BaseModel):
    description: str
    category: str
    severity: AnomalySeverity
    confidence: float = Field(ge=_CONFIDENCE_MIN, le=_CONFIDENCE_MAX)
    location: BoundingBox | None = None
    evidence: str


class VLMAnalysisResult(BaseModel):
    status: EvidenceStatus
    is_anomalous: bool
    summary: str
    explanation: str
    anomalies: list[VLMAnomaly] = Field(default_factory=list)
    confidence: float = Field(ge=_CONFIDENCE_MIN, le=_CONFIDENCE_MAX)
    provider: VLMProvider
    model: str


# ============================================================
# Agent output / Evidence Store contract
# ============================================================

class AgentEvidence(BaseModel):
    evidence_id: uuid.UUID
    inspection_id: uuid.UUID

    agent_name: Literal["vlm_agent"] = "vlm_agent"
    roi: ROIMetadata

    status: EvidenceStatus

    finding: VLMAnalysisResult

    confidence: float = Field(ge=_CONFIDENCE_MIN, le=_CONFIDENCE_MAX)

    explanation: str

    processing_time_ms: int = Field(ge=0)

    created_at: datetime

    metadata: dict[str, Any] | None = None


# ============================================================
# Agent config
# ============================================================

class VLMAgentConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    primary_provider: Literal["gemini"] = "gemini"
    primary_model: str = "gemini-3.5-flash"

    fallback_provider: Literal["groq"] = "groq"
    fallback_model: str = "qwen/qwen3.6-27b"

    confidence_min: float = _CONFIDENCE_MIN
    confidence_max: float = _CONFIDENCE_MAX

    request_timeout_ms: int = Field(default=30_000, gt=0)

    max_retries_per_provider: int = Field(default=2, ge=0)


# ============================================================
# Exceptions
# ============================================================

class VLMAgentError(Exception):
    """Base exception for VLM Agent failures."""


class VLMAllProvidersFailedError(VLMAgentError):
    """Raised when both primary and fallback vision providers fail."""


class VLMResponseParseError(VLMAgentError):
    """Raised when the LLM response cannot be parsed into a valid result."""


# ============================================================
# VLM Agent
# ============================================================

_SYSTEM_PROMPT = (
    "You are a meticulous industrial-parts visual-inspection analyst working "
    "inside an automated fraud-detection pipeline. You are given two cropped "
    "images of the SAME region of interest (ROI): a GOLDEN REFERENCE image "
    "(known-authentic part) and an INSPECTION image (the part under review). "
    "Your job is to identify visual anomalies in the inspection image relative "
    "to the golden reference that are NOT already covered by dedicated OCR, "
    "label-matching, or structural/component-count agents — you are the "
    "general-purpose visual anomaly detector of last resort. Focus on things "
    "like: discoloration, physical damage, incorrect finish/texture, unexpected "
    "markings, warping, corrosion, foreign material, or any other visible "
    "irregularity. Do not speculate about text content or exact component "
    "counts — other agents handle those. "
    "You MUST respond with a single valid JSON object and nothing else — no "
    "markdown fences, no prose before or after. The JSON object must match "
    "exactly this schema:\n"
    "{\n"
    '  "status": "PASS" | "FAIL" | "INCONCLUSIVE",\n'
    '  "is_anomalous": boolean,\n'
    '  "summary": string,\n'
    '  "explanation": string,\n'
    '  "confidence": number (0.0 to 1.0),\n'
    '  "anomalies": [\n'
    "    {\n"
    '      "description": string,\n'
    '      "category": string,\n'
    '      "severity": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",\n'
    '      "confidence": number (0.0 to 1.0),\n'
    '      "evidence": string\n'
    "    }\n"
    "  ]\n"
    "}\n"
    'If no anomalies are found, return an empty "anomalies" array and set '
    '"status" to "PASS" and "is_anomalous" to false.'
)


class VLM_Agent(BaseAgent):
    """
    General-purpose visual anomaly evidence agent.

    Runs after ROI scheduling (Stage 4) as part of Evidence Execution
    (Stage 5). Consumes cropped Golden/Inspection ROI image pairs and
    produces standardized AgentEvidence for the Evidence Store.
    """

    name: Literal["vlm_agent"] = "vlm_agent"

    def __init__(self, llm_client: LLMClient, config: VLMAgentConfig | None = None) -> None:
        if llm_client is None:
            raise ValueError("llm_client is required for VLM_Agent")
        self._llm_client = llm_client
        self._config = config or VLMAgentConfig()

    # --------------------------------------------------------
    # Public entrypoint
    # --------------------------------------------------------

    async def run(self, input: VLMEvidenceInput) -> AgentEvidence:
        """
        Execute the full VLM evidence-gathering flow for a single ROI pair.

        Never raises for provider/model failures — those are captured as
        ERROR-status AgentEvidence so the pipeline can continue and let the
        Judge weigh a missing/failed agent appropriately. Programming errors
        (bad input) still raise, since those indicate a caller bug upstream.
        """
        start_time = time.perf_counter()

        try:
            result = await self.analyze(input)
        except VLMAgentError as exc:
            logger.error(
                "vlm_agent.run: analysis failed for inspection_id=%s roi_id=%s: %s",
                input.inspection_id,
                input.roi.roi_id,
                exc,
                exc_info=True,
            )
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            result = self._build_error_result(str(exc))
            return self.create_evidence(input, result, elapsed_ms)
        except Exception as exc:  # noqa: BLE001 - last-resort containment boundary
            logger.exception(
                "vlm_agent.run: unexpected error for inspection_id=%s roi_id=%s",
                input.inspection_id,
                input.roi.roi_id,
            )
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            result = self._build_error_result(f"Unexpected error: {exc}")
            return self.create_evidence(input, result, elapsed_ms)

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        return self.create_evidence(input, result, elapsed_ms)

    # --------------------------------------------------------
    # Core analysis with primary -> fallback failover
    # --------------------------------------------------------

    async def analyze(self, input: VLMEvidenceInput) -> VLMAnalysisResult:
        request = self.build_prompt(input)

        errors: list[str] = []

        # Primary provider attempts
        for attempt in range(1, self._config.max_retries_per_provider + 2):
            try:
                response = await self._llm_client.analyze_vision(
                    VisionLLMRequest(
                        provider=self._config.primary_provider,
                        model=self._config.primary_model,
                        system_prompt=request.system_prompt,
                        user_prompt=request.user_prompt,
                        images=request.images,
                    )
                )
                return self.parse_response(response)
            except LLMTimeoutError as exc:
                msg = f"primary provider timeout (attempt {attempt}): {exc}"
                logger.warning("vlm_agent.analyze: %s", msg)
                errors.append(msg)
            except LLMProviderError as exc:
                msg = f"primary provider error (attempt {attempt}): {exc}"
                logger.warning("vlm_agent.analyze: %s", msg)
                errors.append(msg)
            except VLMResponseParseError as exc:
                msg = f"primary provider returned unparsable response (attempt {attempt}): {exc}"
                logger.warning("vlm_agent.analyze: %s", msg)
                errors.append(msg)

        # Fallback provider attempts
        for attempt in range(1, self._config.max_retries_per_provider + 2):
            try:
                response = await self._llm_client.analyze_vision(
                    VisionLLMRequest(
                        provider=self._config.fallback_provider,
                        model=self._config.fallback_model,
                        system_prompt=request.system_prompt,
                        user_prompt=request.user_prompt,
                        images=request.images,
                    )
                )
                return self.parse_response(response)
            except LLMTimeoutError as exc:
                msg = f"fallback provider timeout (attempt {attempt}): {exc}"
                logger.warning("vlm_agent.analyze: %s", msg)
                errors.append(msg)
            except LLMProviderError as exc:
                msg = f"fallback provider error (attempt {attempt}): {exc}"
                logger.warning("vlm_agent.analyze: %s", msg)
                errors.append(msg)
            except VLMResponseParseError as exc:
                msg = f"fallback provider returned unparsable response (attempt {attempt}): {exc}"
                logger.warning("vlm_agent.analyze: %s", msg)
                errors.append(msg)

        raise VLMAllProvidersFailedError(
            f"Both primary ({self._config.primary_provider}/{self._config.primary_model}) "
            f"and fallback ({self._config.fallback_provider}/{self._config.fallback_model}) "
            f"providers failed after retries. Errors: {'; '.join(errors)}"
        )

    # --------------------------------------------------------
    # Prompt construction
    # --------------------------------------------------------

    def build_prompt(self, input: VLMEvidenceInput) -> VisionLLMRequest:
        context_lines = [
            f"Product type: {input.product_type}",
            f"ROI name: {input.roi.name}",
            f"ROI type: {input.roi.roi_type}",
            f"ROI critical: {input.roi.critical}",
        ]

        if input.checkpoint:
            context_lines.append(f"Checkpoint to verify: {input.checkpoint}")

        if input.expected_description:
            context_lines.append(
                f"Expected appearance per golden reference: {input.expected_description}"
            )

        if input.metadata:
            for key, value in input.metadata.items():
                context_lines.append(f"Additional context — {key}: {value}")

        user_prompt = (
            "Compare the two attached images: the first is the GOLDEN REFERENCE "
            "ROI crop, the second is the INSPECTION ROI crop of the same region. "
            "Identify any visual anomalies in the inspection image relative to "
            "the golden reference.\n\n"
            + "\n".join(context_lines)
            + "\n\nRespond with the JSON object described in the system prompt, "
            "and nothing else."
        )

        images = [
            VisionImage(
                path=input.golden_image.image_path,
                mime_type=self._infer_mime_type(input.golden_image.image_path),
                role="golden_reference",
            ),
            VisionImage(
                path=input.inspection_image.image_path,
                mime_type=self._infer_mime_type(input.inspection_image.image_path),
                role="inspection",
            ),
        ]

        return VisionLLMRequest(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            images=images,
        )

    # --------------------------------------------------------
    # Response parsing
    # --------------------------------------------------------

    def parse_response(self, response: VisionLLMResponse) -> VLMAnalysisResult:
        raw_content = response.content.strip()
        payload = self._extract_json_object(raw_content)

        if payload is None:
            raise VLMResponseParseError(
                f"No valid JSON object found in provider response: {raw_content[:500]!r}"
            )

        try:
            status_raw = str(payload.get("status", "")).strip().upper()
            if status_raw not in _VALID_STATUSES or status_raw == "ERROR":
                # ERROR is agent-internal only; a model claiming ERROR is
                # treated as INCONCLUSIVE rather than trusted verbatim.
                status: EvidenceStatus = (
                    status_raw if status_raw in ("PASS", "FAIL", "INCONCLUSIVE") else "INCONCLUSIVE"
                )
            else:
                status = status_raw  # type: ignore[assignment]

            is_anomalous = bool(payload.get("is_anomalous", status == "FAIL"))

            summary = str(payload.get("summary", "")).strip()
            if not summary:
                summary = "No summary provided by model."

            explanation = str(payload.get("explanation", "")).strip()
            if not explanation:
                explanation = "No explanation provided by model."

            overall_confidence = self.normalize_confidence(
                self._coerce_float(payload.get("confidence"), default=0.5)
            )

            anomalies_raw = payload.get("anomalies", [])
            if not isinstance(anomalies_raw, list):
                anomalies_raw = []

            anomalies: list[VLMAnomaly] = []
            for item in anomalies_raw:
                if not isinstance(item, dict):
                    continue
                anomalies.append(self._parse_anomaly(item))

            return VLMAnalysisResult(
                status=status,
                is_anomalous=is_anomalous,
                summary=summary,
                explanation=explanation,
                anomalies=anomalies,
                confidence=overall_confidence,
                provider=response.provider,
                model=response.model,
            )
        except VLMResponseParseError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise VLMResponseParseError(
                f"Failed to construct VLMAnalysisResult from payload {payload!r}: {exc}"
            ) from exc

    def _parse_anomaly(self, item: dict[str, Any]) -> VLMAnomaly:
        severity_raw = str(item.get("severity", "MEDIUM")).strip().upper()
        severity: AnomalySeverity = (
            severity_raw if severity_raw in _VALID_SEVERITIES else "MEDIUM"  # type: ignore[assignment]
        )

        description = str(item.get("description", "")).strip() or "Unspecified anomaly."
        category = str(item.get("category", "")).strip() or "uncategorized"
        evidence = str(item.get("evidence", "")).strip() or description

        confidence = self.normalize_confidence(
            self._coerce_float(item.get("confidence"), default=0.5)
        )

        location: BoundingBox | None = None
        loc_raw = item.get("location")
        if isinstance(loc_raw, dict):
            try:
                location = BoundingBox(
                    x=float(loc_raw.get("x", 0.0)),
                    y=float(loc_raw.get("y", 0.0)),
                    width=float(loc_raw.get("width", 1.0)),
                    height=float(loc_raw.get("height", 1.0)),
                )
            except (TypeError, ValueError):
                location = None

        return VLMAnomaly(
            description=description,
            category=category,
            severity=severity,
            confidence=confidence,
            location=location,
            evidence=evidence,
        )

    @staticmethod
    def _coerce_float(value: Any, default: float) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.strip())
            except ValueError:
                return default
        return default

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any] | None:
        """Extract a JSON object from raw model output, tolerating stray
        markdown fences or leading/trailing prose some providers add despite
        instructions."""
        candidate = text.strip()

        # Strip markdown code fences if present.
        fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", candidate, re.DOTALL)
        if fence_match:
            candidate = fence_match.group(1).strip()

        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # Fallback: find the first balanced {...} block.
        start = candidate.find("{")
        if start == -1:
            return None

        depth = 0
        for idx in range(start, len(candidate)):
            char = candidate[idx]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    fragment = candidate[start : idx + 1]
                    try:
                        parsed = json.loads(fragment)
                        if isinstance(parsed, dict):
                            return parsed
                    except json.JSONDecodeError:
                        return None
        return None

    @staticmethod
    def _infer_mime_type(path: str) -> str:
        lowered = path.lower()
        if lowered.endswith(".png"):
            return "image/png"
        if lowered.endswith(".jpg") or lowered.endswith(".jpeg"):
            return "image/jpeg"
        if lowered.endswith(".webp"):
            return "image/webp"
        # Default to JPEG since ROI crops are generated internally as JPEG.
        return "image/jpeg"

    # --------------------------------------------------------
    # Confidence normalization
    # --------------------------------------------------------

    def normalize_confidence(self, confidence: float) -> float:
        if confidence != confidence:  # NaN check
            return self._config.confidence_min
        clamped = max(self._config.confidence_min, min(self._config.confidence_max, confidence))
        return round(clamped, 4)

    # --------------------------------------------------------
    # Evidence construction
    # --------------------------------------------------------

    def create_evidence(
        self,
        input: VLMEvidenceInput,
        result: VLMAnalysisResult,
        processing_time_ms: int,
    ) -> AgentEvidence:
        return AgentEvidence(
            evidence_id=uuid.uuid4(),
            inspection_id=input.inspection_id,
            agent_name="vlm_agent",
            roi=input.roi,
            status=result.status,
            finding=result,
            confidence=result.confidence,
            explanation=result.explanation,
            processing_time_ms=processing_time_ms,
            created_at=datetime.now(timezone.utc),
            metadata={
                "golden_image": input.golden_image.image_path,
                "inspection_image": input.inspection_image.image_path,
                "provider": result.provider,
                "model": result.model,
                "anomaly_count": len(result.anomalies),
            },
        )

    def _build_error_result(self, message: str) -> VLMAnalysisResult:
        return VLMAnalysisResult(
            status="ERROR",
            is_anomalous=False,
            summary="VLM agent failed to produce a result.",
            explanation=message,
            anomalies=[],
            confidence=self._config.confidence_min,
            provider=self._config.primary_provider,
            model=self._config.primary_model,
        )


VLMAgent = VLM_Agent