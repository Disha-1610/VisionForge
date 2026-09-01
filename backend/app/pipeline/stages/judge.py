"""
backend/app/pipeline/stages/judge.py

Stage 7 — AI Judge (single LLM reasoning pass).

Consumes Stage 6 (Multi-View Evidence Fusion) output, resolves evidence
conflicts, produces a final Accept / Reject / Review verdict with fraud
probability, confidence, category, and root-cause reasoning.

Architectural rules enforced by this module:
  - Judge NEVER executes OCR/YOLO/VLM detectors directly; it only reasons
    over already-fused evidence.
  - Judge NEVER instantiates Groq/Gemini clients directly; it depends on
    the shared `LLMClient` protocol (Groq `openai/gpt-oss-20b` primary,
    Gemini `gemini-3.5-flash` fallback — routing lives in llm_client.py).
  - Judge reports failure rather than fabricating a verdict.
  - Judge writes its result to Working Memory under `JUDGE_RESULT_KEY`.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

logger = logging.getLogger("visionforge.pipeline.judge")

JUDGE_RESULT_KEY = "judge_result"

_PRIMARY_MODEL = "openai/gpt-oss-20b"
_FALLBACK_MODEL = "gemini-3.5-flash"


# ---------------------------------------------------------------------------
# 1. Core domain enums
# ---------------------------------------------------------------------------

class Verdict(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    REVIEW = "REVIEW"


class FraudCategory(str, Enum):
    COUNTERFEIT_COMPONENT = "COUNTERFEIT_COMPONENT"
    MISSING_COMPONENT = "MISSING_COMPONENT"
    EXTRA_COMPONENT = "EXTRA_COMPONENT"
    MISPLACED_COMPONENT = "MISPLACED_COMPONENT"
    LABEL_TAMPERING = "LABEL_TAMPERING"
    SERIAL_MISMATCH = "SERIAL_MISMATCH"
    STRUCTURAL_TAMPERING = "STRUCTURAL_TAMPERING"
    AUTHENTICITY_RISK = "AUTHENTICITY_RISK"
    MULTIPLE_ANOMALIES = "MULTIPLE_ANOMALIES"
    NO_FRAUD_DETECTED = "NO_FRAUD_DETECTED"
    UNCERTAIN = "UNCERTAIN"


class EvidenceSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EvidenceDecision(str, Enum):
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"
    UNCERTAIN = "UNCERTAIN"


class EvidenceSource(str, Enum):
    OCR = "OCR"
    LABEL = "LABEL"
    STRUCTURAL = "STRUCTURAL"
    VLM = "VLM"
    AUTHENTICITY = "AUTHENTICITY"
    REFERENCE_MATCH = "REFERENCE_MATCH"
    FUSION = "FUSION"


class ModelProvider(str, Enum):
    GROQ = "GROQ"
    GEMINI = "GEMINI"


class ProductType(str, Enum):
    MOTHERBOARD = "MOTHERBOARD"
    BATTERY = "BATTERY"
    RAM = "RAM"


class JudgeErrorCode(str, Enum):
    NO_FUSED_EVIDENCE = "NO_FUSED_EVIDENCE"
    INVALID_EVIDENCE = "INVALID_EVIDENCE"
    LLM_REQUEST_FAILED = "LLM_REQUEST_FAILED"
    LLM_RESPONSE_INVALID = "LLM_RESPONSE_INVALID"
    INVALID_VERDICT = "INVALID_VERDICT"
    INVALID_FRAUD_PROBABILITY = "INVALID_FRAUD_PROBABILITY"
    INVALID_CONFIDENCE = "INVALID_CONFIDENCE"
    UNSUPPORTED_FRAUD_CLAIM = "UNSUPPORTED_FRAUD_CLAIM"
    JUDGE_EXECUTION_FAILED = "JUDGE_EXECUTION_FAILED"


class JudgeStageError(Exception):
    """Raised internally when the Judge stage cannot produce a valid result."""

    def __init__(self, code: JudgeErrorCode, message: str, *, retryable: bool = False,
                 provider: ModelProvider | None = None, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.provider = provider
        self.details = details or {}


# ---------------------------------------------------------------------------
# 2. Evidence contract (input from Stage 6 — Evidence Fusion)
# ---------------------------------------------------------------------------

class DetectorMetrics(BaseModel):
    model_config = {"extra": "forbid"}

    ssim_score: float | None = None
    golden_component_counts: dict[str, int] = Field(default_factory=dict)
    inspection_component_counts: dict[str, int] = Field(default_factory=dict)
    missing_components: list[str] = Field(default_factory=list)
    extra_components: list[str] = Field(default_factory=list)
    misplaced_components: list[str] = Field(default_factory=list)
    ocr_expected_text: str | None = None
    ocr_detected_text: str | None = None
    text_mismatch: bool | None = None
    template_match_score: float | None = None


class FusedEvidence(BaseModel):
    model_config = {"extra": "forbid"}

    evidence_id: str = Field(min_length=1)
    source: EvidenceSource
    roi_id: str | None = None
    finding: str = Field(min_length=1)
    explanation: str = ""
    confidence: float = Field(ge=0, le=100)
    severity: EvidenceSeverity
    decision: EvidenceDecision
    inspection_image_ids: list[str] = Field(default_factory=list)
    contributing_angles: list[str] = Field(default_factory=list)
    detector_metrics: DetectorMetrics | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 3. Inspection context
# ---------------------------------------------------------------------------

class JudgeInspectionContext(BaseModel):
    model_config = {"extra": "forbid"}

    inspection_id: str = Field(min_length=1)
    case_id: str = Field(min_length=1)
    product_type: ProductType
    part_id: str | None = None
    vendor_id: str | None = None
    location: str | None = None
    reference_image_id: str | None = None
    authenticity_score: float | None = Field(default=None, ge=0, le=100)
    reference_similarity: float | None = Field(default=None, ge=0, le=1)


# ---------------------------------------------------------------------------
# 4. Judge input
# ---------------------------------------------------------------------------

class EvidenceSummary(BaseModel):
    model_config = {"extra": "forbid"}

    total_evidence: int = Field(ge=0)
    supporting_evidence: int = Field(ge=0)
    conflicting_evidence: int = Field(ge=0)
    uncertain_evidence: int = Field(ge=0)
    highest_confidence: float = Field(ge=0, le=100)
    critical_findings: list[str] = Field(default_factory=list)


class JudgeConstraints(BaseModel):
    model_config = {"extra": "forbid"}

    min_confidence_for_definitive_verdict: float = Field(default=60.0, ge=0, le=100)
    max_fraud_probability_for_accept: float = Field(default=20.0, ge=0, le=100)
    min_fraud_probability_for_reject: float = Field(default=75.0, ge=0, le=100)
    allowed_verdicts: list[Verdict] = Field(
        default_factory=lambda: [Verdict.ACCEPT, Verdict.REJECT, Verdict.REVIEW]
    )
    require_evidence_for_fraud_claim: bool = True


class JudgeInput(BaseModel):
    model_config = {"extra": "forbid"}

    inspection: JudgeInspectionContext
    fused_evidence: list[FusedEvidence]
    evidence_summary: EvidenceSummary
    system_constraints: JudgeConstraints = Field(default_factory=JudgeConstraints)

    @field_validator("fused_evidence")
    @classmethod
    def _non_empty_evidence(cls, v: list[FusedEvidence]) -> list[FusedEvidence]:
        if not v:
            raise ValueError("fused_evidence must not be empty")
        return v


# ---------------------------------------------------------------------------
# 5. Conflict resolution contract
# ---------------------------------------------------------------------------

class EvidenceAssessment(BaseModel):
    model_config = {"extra": "forbid"}

    evidence_id: str
    weight: float = Field(ge=0, le=1)
    decision: EvidenceDecision
    rationale: str = Field(min_length=1)


class ConflictResolution(BaseModel):
    model_config = {"extra": "forbid"}

    conflict_detected: bool
    conflicting_evidence_ids: list[str] = Field(default_factory=list)
    assessments: list[EvidenceAssessment] = Field(default_factory=list)
    resolution: str = ""
    uncertainty: str | None = None


# ---------------------------------------------------------------------------
# 6. Root-cause contract
# ---------------------------------------------------------------------------

class RootCauseAnalysis(BaseModel):
    model_config = {"extra": "forbid"}

    root_cause: str = Field(min_length=1)
    secondary_effects: list[str] = Field(default_factory=list)
    causal_chain: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    unsupported_relationships: list[str] = Field(default_factory=list)
    uncertainty: str | None = None


# ---------------------------------------------------------------------------
# 7. Judge output
# ---------------------------------------------------------------------------

class JudgeResult(BaseModel):
    model_config = {"extra": "forbid"}

    verdict: Verdict
    fraud_probability: float = Field(ge=0, le=100)
    confidence: float = Field(ge=0, le=100)
    category: FraudCategory
    root_cause_analysis: RootCauseAnalysis
    conflict_resolution: ConflictResolution
    evidence_assessments: list[EvidenceAssessment]
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    rejected_evidence_ids: list[str] = Field(default_factory=list)
    uncertain_evidence_ids: list[str] = Field(default_factory=list)
    reasoning: str = Field(min_length=1)
    model_provider: ModelProvider
    model_name: str
    processing_time_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def _verdict_probability_consistency(self) -> "JudgeResult":
        if self.verdict == Verdict.ACCEPT and self.fraud_probability > 90:
            raise ValueError(
                "verdict=ACCEPT is inconsistent with fraud_probability > 90"
            )
        if self.verdict == Verdict.REJECT and self.fraud_probability < 10:
            raise ValueError(
                "verdict=REJECT is inconsistent with fraud_probability < 10"
            )
        if self.category == FraudCategory.NO_FRAUD_DETECTED and self.fraud_probability > 50:
            raise ValueError(
                "category=NO_FRAUD_DETECTED is inconsistent with fraud_probability > 50"
            )
        return self


# ---------------------------------------------------------------------------
# 8. LLM Client boundary (Protocol — implemented by shared/llm_client.py)
# ---------------------------------------------------------------------------

class JudgeLLMRequest(BaseModel):
    model_config = {"extra": "forbid"}

    system_prompt: str
    user_prompt: str
    response_format: Literal["json"] = "json"
    temperature: float = Field(default=0.1, ge=0, le=2)
    max_tokens: int = Field(default=2048, ge=1)
    model_preference: Literal["GROQ_PRIMARY_GEMINI_FALLBACK"] = "GROQ_PRIMARY_GEMINI_FALLBACK"


class JudgeLLMResponse(BaseModel):
    model_config = {"extra": "forbid"}

    content: str
    provider: ModelProvider
    model: str
    latency_ms: int
    request_id: str | None = None


class LLMGenerateResult(BaseModel):
    model_config = {"extra": "forbid", "arbitrary_types_allowed": True}

    data: dict[str, Any]
    provider: ModelProvider
    model: str
    latency_ms: int


@runtime_checkable
class LLMClient(Protocol):
    """Shared LLM client boundary. Concrete implementation lives in
    `app.shared.llm_client`; Judge only depends on this protocol."""

    async def generate_structured(self, request: JudgeLLMRequest) -> LLMGenerateResult:
        ...


@runtime_checkable
class WorkingMemory(Protocol):
    """Shared working-memory boundary. Concrete implementation lives in
    `app.shared.memory`; Judge only depends on this protocol."""

    async def get(self, inspection_id: str, key: str) -> Any | None:
        ...

    async def set(self, inspection_id: str, key: str, value: Any) -> None:
        ...


# ---------------------------------------------------------------------------
# 10. Pipeline stage contract
# ---------------------------------------------------------------------------

class JudgeDependencies(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    llm_client: LLMClient
    working_memory: WorkingMemory


class JudgeError(BaseModel):
    model_config = {"extra": "forbid"}

    code: JudgeErrorCode
    message: str
    retryable: bool
    provider: ModelProvider | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class JudgeStageResult(BaseModel):
    model_config = {"extra": "forbid"}

    result: JudgeResult | None
    stage_name: Literal["judge"] = "judge"
    status: Literal["completed", "failed"]
    started_at: datetime
    completed_at: datetime
    processing_time_ms: int = Field(ge=0)
    error: JudgeError | None = None


# ---------------------------------------------------------------------------
# 13. Prompt construction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are the AI Judge in an industrial fraud-detection pipeline \
(VisionForge). You receive fused evidence from four specialized detectors \
(OCR, Label, Structural [SSIM + YOLO], VLM) plus authenticity and reference-match \
signals for a single part inspection.

Your job, in one reasoning pass:
1. Resolve conflicts between evidence sources explicitly — state which evidence \
you weighted higher and why. Never silently discard conflicting evidence.
2. Build a cause-and-effect explanation connecting anomalies into a coherent \
fraud scenario. Distinguish the root cause from secondary effects.
3. Reject conclusions that are not supported by the provided evidence. Mark \
uncertain relationships explicitly rather than guessing.
4. Produce exactly one final verdict: ACCEPT, REJECT, or REVIEW, together with \
a fraud probability (0-100), confidence (0-100), and a fraud category.

You must respond with ONLY a single valid JSON object — no markdown fences, no \
prose before or after — matching exactly this schema:

{
  "verdict": "ACCEPT" | "REJECT" | "REVIEW",
  "fraud_probability": <number 0-100>,
  "confidence": <number 0-100>,
  "category": "COUNTERFEIT_COMPONENT" | "MISSING_COMPONENT" | "EXTRA_COMPONENT" | \
"MISPLACED_COMPONENT" | "LABEL_TAMPERING" | "SERIAL_MISMATCH" | \
"STRUCTURAL_TAMPERING" | "AUTHENTICITY_RISK" | "MULTIPLE_ANOMALIES" | \
"NO_FRAUD_DETECTED" | "UNCERTAIN",
  "root_cause_analysis": {
    "root_cause": "<string>",
    "secondary_effects": ["<string>", ...],
    "causal_chain": ["<string>", ...],
    "supporting_evidence_ids": ["<evidence_id>", ...],
    "unsupported_relationships": ["<string>", ...],
    "uncertainty": "<string or null>"
  },
  "conflict_resolution": {
    "conflict_detected": <boolean>,
    "conflicting_evidence_ids": ["<evidence_id>", ...],
    "assessments": [
      {"evidence_id": "<id>", "weight": <0-1>, "decision": "SUPPORTED"|"REJECTED"|"UNCERTAIN", "rationale": "<string>"}
    ],
    "resolution": "<string>",
    "uncertainty": "<string or null>"
  },
  "evidence_assessments": [
    {"evidence_id": "<id>", "weight": <0-1>, "decision": "SUPPORTED"|"REJECTED"|"UNCERTAIN", "rationale": "<string>"}
  ],
  "supporting_evidence_ids": ["<evidence_id>", ...],
  "rejected_evidence_ids": ["<evidence_id>", ...],
  "uncertain_evidence_ids": ["<evidence_id>", ...],
  "reasoning": "<full reasoning summary, string>"
}

Rules:
- Every evidence_id you reference MUST come from the provided evidence list.
- evidence_assessments MUST cover every evidence_id provided.
- If system_constraints.require_evidence_for_fraud_claim is true, fraud_probability \
above 50 REQUIRES at least one SUPPORTED evidence assessment with severity \
MEDIUM or higher.
- Output strictly valid JSON. Do not include comments or trailing commas."""


def build_judge_prompt(input_data: JudgeInput) -> tuple[str, str]:
    """Builds (system_prompt, user_prompt) for the Judge LLM call."""

    evidence_payload = [e.model_dump(mode="json") for e in input_data.fused_evidence]

    user_payload = {
        "inspection": input_data.inspection.model_dump(mode="json"),
        "fused_evidence": evidence_payload,
        "evidence_summary": input_data.evidence_summary.model_dump(mode="json"),
        "system_constraints": input_data.system_constraints.model_dump(mode="json"),
    }

    user_prompt = (
        "Evaluate the following inspection using the evidence provided. "
        "Respond with ONLY the JSON object described in your instructions.\n\n"
        f"{json.dumps(user_payload, ensure_ascii=False, indent=2)}"
    )

    return _SYSTEM_PROMPT, user_prompt


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _extract_json_object(raw: str) -> dict[str, Any]:
    """Extracts a JSON object from raw LLM output, tolerating stray markdown
    fences some providers still emit despite instructions."""

    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise JudgeStageError(
            JudgeErrorCode.LLM_RESPONSE_INVALID,
            "LLM response did not contain a parseable JSON object.",
            retryable=True,
            details={"raw_preview": text[:500]},
        )

    candidate = text[start : end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise JudgeStageError(
            JudgeErrorCode.LLM_RESPONSE_INVALID,
            f"Failed to parse JSON from LLM response: {exc}",
            retryable=True,
            details={"raw_preview": candidate[:500]},
        ) from exc

    if not isinstance(parsed, dict):
        raise JudgeStageError(
            JudgeErrorCode.LLM_RESPONSE_INVALID,
            "Parsed LLM response JSON is not an object.",
            retryable=True,
        )
    return parsed


def validate_judge_result(result: JudgeResult, input_data: JudgeInput) -> JudgeResult:
    """Cross-validates the parsed JudgeResult against the JudgeInput contract.

    Raises JudgeStageError on any violation. Returns the (unmodified) result
    when valid, so callers can chain this in a functional style.
    """

    known_ids = {e.evidence_id for e in input_data.fused_evidence}

    referenced_ids: set[str] = set()
    referenced_ids.update(result.supporting_evidence_ids)
    referenced_ids.update(result.rejected_evidence_ids)
    referenced_ids.update(result.uncertain_evidence_ids)
    referenced_ids.update(a.evidence_id for a in result.evidence_assessments)
    referenced_ids.update(result.root_cause_analysis.supporting_evidence_ids)
    referenced_ids.update(result.conflict_resolution.conflicting_evidence_ids)
    referenced_ids.update(a.evidence_id for a in result.conflict_resolution.assessments)

    unknown_ids = referenced_ids - known_ids
    if unknown_ids:
        raise JudgeStageError(
            JudgeErrorCode.INVALID_EVIDENCE,
            f"Judge referenced unknown evidence_id(s): {sorted(unknown_ids)}",
            retryable=True,
            details={"unknown_ids": sorted(unknown_ids)},
        )

    assessed_ids = {a.evidence_id for a in result.evidence_assessments}
    missing_assessments = known_ids - assessed_ids
    if missing_assessments:
        raise JudgeStageError(
            JudgeErrorCode.INVALID_EVIDENCE,
            f"Judge did not assess all provided evidence: missing {sorted(missing_assessments)}",
            retryable=True,
            details={"missing_evidence_ids": sorted(missing_assessments)},
        )

    constraints = input_data.system_constraints

    if result.verdict not in constraints.allowed_verdicts:
        raise JudgeStageError(
            JudgeErrorCode.INVALID_VERDICT,
            f"Verdict {result.verdict.value} is not in allowed_verdicts "
            f"{[v.value for v in constraints.allowed_verdicts]}",
            retryable=True,
        )

    if constraints.require_evidence_for_fraud_claim and result.fraud_probability > 50:
        supported_significant = [
            a
            for a in result.evidence_assessments
            if a.decision == EvidenceDecision.SUPPORTED and a.weight > 0.0
        ]
        supported_ids = {a.evidence_id for a in supported_significant}
        significant_severity_ids = {
            e.evidence_id
            for e in input_data.fused_evidence
            if e.severity in (EvidenceSeverity.MEDIUM, EvidenceSeverity.HIGH, EvidenceSeverity.CRITICAL)
        }
        if not (supported_ids & significant_severity_ids):
            raise JudgeStageError(
                JudgeErrorCode.UNSUPPORTED_FRAUD_CLAIM,
                "fraud_probability > 50 requires at least one SUPPORTED evidence "
                "assessment tied to a MEDIUM+ severity finding.",
                retryable=True,
                details={"fraud_probability": result.fraud_probability},
            )

    if result.fraud_probability < 0 or result.fraud_probability > 100:
        raise JudgeStageError(
            JudgeErrorCode.INVALID_FRAUD_PROBABILITY,
            f"fraud_probability out of range: {result.fraud_probability}",
            retryable=True,
        )

    if result.confidence < 0 or result.confidence > 100:
        raise JudgeStageError(
            JudgeErrorCode.INVALID_CONFIDENCE,
            f"confidence out of range: {result.confidence}",
            retryable=True,
        )

    if (
        result.verdict in (Verdict.ACCEPT, Verdict.REJECT)
        and result.confidence < constraints.min_confidence_for_definitive_verdict
    ):
        logger.warning(
            "Judge issued definitive verdict %s with confidence %.1f below "
            "min_confidence_for_definitive_verdict=%.1f for inspection %s; "
            "downstream Policy Engine should treat conservatively.",
            result.verdict.value,
            result.confidence,
            constraints.min_confidence_for_definitive_verdict,
            input_data.inspection.inspection_id,
        )

    return result


def resolve_judge_error(error: Exception) -> JudgeError:
    """Normalizes any exception raised during Judge execution into the
    structured JudgeError contract."""

    if isinstance(error, JudgeStageError):
        return JudgeError(
            code=error.code,
            message=error.message,
            retryable=error.retryable,
            provider=error.provider,
            details=error.details,
        )

    if isinstance(error, ValidationError):
        return JudgeError(
            code=JudgeErrorCode.LLM_RESPONSE_INVALID,
            message=f"Judge output failed schema validation: {error}",
            retryable=True,
            provider=None,
            details={"validation_errors": error.errors()},
        )

    return JudgeError(
        code=JudgeErrorCode.JUDGE_EXECUTION_FAILED,
        message=f"Unhandled error during Judge execution: {error}",
        retryable=False,
        provider=None,
        details={"exception_type": type(error).__name__},
    )


# ---------------------------------------------------------------------------
# Core LLM invocation with primary -> fallback failover
# ---------------------------------------------------------------------------

async def _invoke_judge_llm(
    llm_client: LLMClient,
    system_prompt: str,
    user_prompt: str,
) -> tuple[dict[str, Any], ModelProvider, str, int]:
    """Calls the shared LLM client. Failover between Groq primary and Gemini
    fallback is owned by llm_client.py; this function only surfaces a clean
    JudgeStageError if the shared client ultimately fails."""

    request = JudgeLLMRequest(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_format="json",
        temperature=0.1,
        max_tokens=3000,
        model_preference="GROQ_PRIMARY_GEMINI_FALLBACK",
    )

    try:
        llm_result = await llm_client.generate_structured(request)
    except Exception as exc:  # noqa: BLE001 - normalized below
        raise JudgeStageError(
            JudgeErrorCode.LLM_REQUEST_FAILED,
            f"LLM client failed to produce a response (both primary and "
            f"fallback exhausted): {exc}",
            retryable=True,
            details={"exception_type": type(exc).__name__},
        ) from exc

    if not isinstance(llm_result.data, dict):
        raise JudgeStageError(
            JudgeErrorCode.LLM_RESPONSE_INVALID,
            "LLM client returned non-object structured data.",
            retryable=True,
            provider=llm_result.provider,
        )

    return llm_result.data, llm_result.provider, llm_result.model, llm_result.latency_ms


def _parse_llm_payload_to_result(
    payload: dict[str, Any],
    provider: ModelProvider,
    model: str,
    processing_time_ms: int,
) -> JudgeResult:
    """Maps a raw parsed LLM JSON payload onto the strict JudgeResult schema."""

    try:
        return JudgeResult(
            verdict=Verdict(payload["verdict"]),
            fraud_probability=float(payload["fraud_probability"]),
            confidence=float(payload["confidence"]),
            category=FraudCategory(payload["category"]),
            root_cause_analysis=RootCauseAnalysis.model_validate(payload["root_cause_analysis"]),
            conflict_resolution=ConflictResolution.model_validate(payload["conflict_resolution"]),
            evidence_assessments=[
                EvidenceAssessment.model_validate(a) for a in payload["evidence_assessments"]
            ],
            supporting_evidence_ids=list(payload.get("supporting_evidence_ids", [])),
            rejected_evidence_ids=list(payload.get("rejected_evidence_ids", [])),
            uncertain_evidence_ids=list(payload.get("uncertain_evidence_ids", [])),
            reasoning=str(payload["reasoning"]),
            model_provider=provider,
            model_name=model,
            processing_time_ms=processing_time_ms,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise JudgeStageError(
            JudgeErrorCode.LLM_RESPONSE_INVALID,
            f"LLM JSON payload missing/invalid required field: {exc}",
            retryable=True,
            provider=provider,
            details={"payload_keys": list(payload.keys())},
        ) from exc
    except ValidationError as exc:
        raise JudgeStageError(
            JudgeErrorCode.LLM_RESPONSE_INVALID,
            f"LLM JSON payload failed schema validation: {exc}",
            retryable=True,
            provider=provider,
            details={"validation_errors": exc.errors()},
        ) from exc


# ---------------------------------------------------------------------------
# 13. Public entry point
# ---------------------------------------------------------------------------

async def run_judge(
    input_data: JudgeInput,
    *,
    llm_client: LLMClient,
    working_memory: WorkingMemory,
) -> JudgeStageResult:
    """Executes Stage 7 — AI Judge.

    Reads fused evidence, invokes the shared LLM client (Groq primary,
    Gemini fallback), validates and cross-checks the structured result
    against the evidence contract, persists it to Working Memory, and
    returns a JudgeStageResult consumed by Stage 8 (Policy Engine) and
    the reporting layer.

    Never raises for expected failure modes — all such failures are
    captured in the returned JudgeStageResult.error field, with
    status="failed". Only truly unexpected exceptions during timestamp
    bookkeeping would propagate, which should not occur in practice.
    """

    started_at = datetime.now(timezone.utc)
    start_perf = time.perf_counter()
    inspection_id = input_data.inspection.inspection_id

    try:
        if not input_data.fused_evidence:
            raise JudgeStageError(
                JudgeErrorCode.NO_FUSED_EVIDENCE,
                "Judge received no fused evidence to reason over.",
                retryable=False,
            )

        system_prompt, user_prompt = build_judge_prompt(input_data)

        payload, provider, model, llm_latency_ms = await _invoke_judge_llm(
            llm_client, system_prompt, user_prompt
        )

        processing_time_ms = int((time.perf_counter() - start_perf) * 1000)

        result = _parse_llm_payload_to_result(
            payload, provider, model, processing_time_ms or llm_latency_ms
        )
        result = validate_judge_result(result, input_data)

        try:
            await working_memory.set(inspection_id, JUDGE_RESULT_KEY, result.model_dump(mode="json"))
        except Exception as exc:  # noqa: BLE001
            # Persistence failure must not silently discard a valid verdict,
            # but it also must not be reported as fabricated success.
            logger.error(
                "Judge produced a valid result but failed to persist to "
                "Working Memory for inspection %s: %s",
                inspection_id,
                exc,
            )
            raise JudgeStageError(
                JudgeErrorCode.JUDGE_EXECUTION_FAILED,
                f"Failed to persist Judge result to Working Memory: {exc}",
                retryable=True,
                provider=provider,
                details={"inspection_id": inspection_id},
            ) from exc

        completed_at = datetime.now(timezone.utc)
        final_processing_time_ms = int((time.perf_counter() - start_perf) * 1000)

        logger.info(
            "Judge completed for inspection %s: verdict=%s fraud_probability=%.1f "
            "confidence=%.1f category=%s provider=%s model=%s (%dms)",
            inspection_id,
            result.verdict.value,
            result.fraud_probability,
            result.confidence,
            result.category.value,
            provider.value,
            model,
            final_processing_time_ms,
        )

        return JudgeStageResult(
            result=result,
            stage_name="judge",
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            processing_time_ms=final_processing_time_ms,
            error=None,
        )

    except Exception as exc:  # noqa: BLE001 - single controlled boundary
        judge_error = resolve_judge_error(exc)
        completed_at = datetime.now(timezone.utc)
        processing_time_ms = int((time.perf_counter() - start_perf) * 1000)

        logger.error(
            "Judge stage failed for inspection %s: code=%s message=%s retryable=%s",
            inspection_id,
            judge_error.code.value,
            judge_error.message,
            judge_error.retryable,
        )

        try:
            await working_memory.set(
                inspection_id,
                f"{JUDGE_RESULT_KEY}_error",
                judge_error.model_dump(mode="json"),
            )
        except Exception:  # noqa: BLE001
            logger.error(
                "Judge also failed to persist error state to Working Memory "
                "for inspection %s; continuing with in-memory error only.",
                inspection_id,
            )

        return JudgeStageResult(
            result=None,
            stage_name="judge",
            status="failed",
            started_at=started_at,
            completed_at=completed_at,
            processing_time_ms=processing_time_ms,
            error=judge_error,
        )


class JudgeStage:
    """Thin class wrapper matching the `JudgeStage.run()` contract, for
    callers (e.g. the LangGraph node in `pipeline/workflow.py`) that prefer
    an object with a bound `run` method over the free function."""

    async def run(self, input: JudgeInput, dependencies: JudgeDependencies) -> JudgeStageResult:
        return await run_judge(
            input,
            llm_client=dependencies.llm_client,
            working_memory=dependencies.working_memory,
        )