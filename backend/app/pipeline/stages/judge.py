# backend/app/pipeline/stages/judge.py
"""
Stage 7 — AI Judge & Root-Cause Analysis (Disha, W4 D1).

Multimodal / text LLM-driven verdict engine. Synthesizes evidence gathered
across Stages 1 through 6 to deliver:
1. Executive Verdict (accept | reject | review)
2. Confidence Score (0.0 to 1.0)
3. Primary Fraud Category
4. Detailed Technical Root-Cause Explanation

Routing & Failover:
  Primary: Groq LLaMA / GPT-OSS
  Fallback: Google Gemini 3.5 Flash
  Offline Fallback: Deterministic forensic rule evaluator
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.pipeline.state import InspectionState
from app.shared.llm_client import (
    LLMCapability,
    LLMClientError,
    LLMMessage,
    LLMRequest,
    LLMTask,
    ResponseFormat,
    get_llm_client,
)
from app.shared.memory import PipelineStageName, StageResult

logger = logging.getLogger("app.pipeline.judge")


class JudgeVerdictResponse(BaseModel):
    verdict: str = Field(..., description="accept | reject | review")
    confidence: float = Field(..., ge=0.0, le=1.0)
    fraud_category: str = Field(..., description="Classification of the defect/authenticity")
    root_cause_reasoning: str = Field(..., description="Detailed technical justification")
    recommendations: list[str] = Field(default_factory=list)

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, v: Any) -> float:
        try:
            val = float(v)
            if val > 1.0 and val <= 100.0:
                return val / 100.0
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 0.90

    @field_validator("verdict", mode="before")
    @classmethod
    def normalize_verdict(cls, v: Any) -> str:
        s = str(v).strip().lower()
        if "reject" in s or "quarantine" in s or "fail" in s:
            return "reject"
        if "review" in s or "verify" in s or "borderline" in s or "warn" in s:
            return "review"
        return "accept"

    @field_validator("recommendations", mode="before")
    @classmethod
    def normalize_recommendations(cls, v: Any) -> list[str]:
        if isinstance(v, list):
            return [str(x) for x in v]
        if isinstance(v, str):
            return [v]
        return []


def _build_judge_prompt(state: InspectionState) -> list[LLMMessage]:
    """Constructs forensic analysis prompt with structured inspection context."""
    mem = state.memory
    fused = mem.fused_evidence or {}

    context_payload = {
        "part_code": mem.part_code or "UNKNOWN-PART",
        "product_type": mem.product_type or "Electronics",
        "location": mem.location or "Facility Floor",
        "authenticity_score": mem.authenticity_score,
        "authenticity_flagged": mem.authenticity_flagged,
        "reference_similarity": mem.similarity_score,
        "fraud_score": fused.get("fraud_score", 0.0),
        "primary_category": fused.get("primary_category", "clean"),
        "detected_issues": fused.get("detected_issues", []),
        "roi_summaries": fused.get("roi_summaries", []),
    }

    system_instruction = (
        "You are VisionForge AI's Lead Forensic Electronics Quality Inspector. "
        "Your task is to analyze hardware inspection evidence from optical, OCR, structural (YOLO/SSIM), "
        "and authenticity analysis modules, and render a final verdict.\n\n"
        "Guidelines:\n"
        "- 'reject': Confirmed hardware counterfeit, missing/extra components, tampered serial number, "
        "or significant structural deviation.\n"
        "- 'review': Borderline anomaly, minor solder bridge risk, low template match, or unverified vendor.\n"
        "- 'accept': All components and identifiers match golden engineering reference within tolerance.\n"
        "Return valid JSON adhering to the JudgeVerdictResponse schema."
    )

    user_prompt = (
        "Please analyze the following inspection case evidence and determine the verdict:\n\n"
        f"```json\n{json.dumps(context_payload, indent=2)}\n```\n\n"
        "Provide your evaluation in structured JSON with: "
        "verdict ('accept', 'reject', or 'review'), confidence (0.0-1.0), "
        "fraud_category, root_cause_reasoning, and recommendations."
    )

    return [
        LLMMessage(role="system", content=system_instruction),
        LLMMessage(role="user", content=user_prompt),
    ]


def _rule_based_fallback_verdict(state: InspectionState) -> JudgeVerdictResponse:
    """Deterministic offline fallback when LLM providers are unavailable."""
    fused = state.memory.fused_evidence or {}
    fraud_prob = state.memory.fraud_probability or 0.0
    category = fused.get("primary_category", "clean")
    issues = fused.get("detected_issues", [])

    if fraud_prob >= 0.65 or "missing_components" in category or "counterfeit" in category:
        issues_summary = ", ".join(issues[:3]) if issues else "critical structural or component mismatch"
        return JudgeVerdictResponse(
            verdict="reject",
            confidence=0.92,
            fraud_category=category,
            root_cause_reasoning=(
                f"Defect threshold exceeded (fraud score: {fraud_prob*100:.1f}%). "
                f"Critical anomalies identified: {issues_summary}. Hardware fails golden reference tolerance."
            ),
            recommendations=[
                "Quarantine affected batch immediately",
                "Flag vendor supply chain for forensic audit",
            ],
        )

    if fraud_prob >= 0.30 or state.memory.authenticity_flagged:
        issues_summary = ", ".join(issues[:3]) if issues else "borderline statistical variance"
        return JudgeVerdictResponse(
            verdict="review",
            confidence=0.78,
            fraud_category=category,
            root_cause_reasoning=(
                f"Borderline anomaly detected (fraud score: {fraud_prob*100:.1f}%). "
                f"Findings ({issues_summary}) warrant secondary manual verification by a senior engineer."
            ),
            recommendations=[
                "Perform high-magnification manual optical inspection",
                "Verify component lot date code with vendor",
            ],
        )

    return JudgeVerdictResponse(
        verdict="accept",
        confidence=0.95,
        fraud_category="clean",
        root_cause_reasoning=(
            "All inspected regions and component counts match the golden engineering specification "
            "within certified industrial tolerance limits. No tampering or component deviations detected."
        ),
        recommendations=["Release batch to assembly / fulfillment"],
    )


async def run_judge(state: InspectionState) -> StageResult:
    """
    Stage 7 entrypoint. Invokes LLM Judge (or offline fallback), updates
    WorkingMemory root-cause and confidence, and returns StageResult.
    """
    started_at = datetime.now(timezone.utc)
    logger.info("Starting Stage 7 AI Judge for inspection %s", state.memory.inspection_id)

    llm_client = get_llm_client()
    messages = _build_judge_prompt(state)

    request = LLMRequest(
        task=LLMTask.JUDGE,
        capability=LLMCapability.TEXT,
        messages=messages,
        temperature=0.1,
        response_format=ResponseFormat.JSON,
        inspection_id=str(state.memory.inspection_id),
        stage_name="judge",
    )

    verdict_response: JudgeVerdictResponse
    used_offline_fallback = False

    try:
        _raw_resp, verdict_response = await llm_client.generate_json(
            request,
            JudgeVerdictResponse,
        )
    except (LLMClientError, Exception) as exc:
        logger.warning(
            "LLM Judge execution failed or unavailable (%s). Activating deterministic fallback.",
            exc,
        )
        verdict_response = _rule_based_fallback_verdict(state)
        used_offline_fallback = True

    # Update WorkingMemory
    await state.memory.update(
        root_cause=verdict_response.root_cause_reasoning,
        judge_confidence=verdict_response.confidence,
        fraud_category=verdict_response.fraud_category,
    )

    completed_at = datetime.now(timezone.utc)
    detail: dict[str, Any] = {
        "verdict": verdict_response.verdict,
        "confidence": verdict_response.confidence,
        "fraud_category": verdict_response.fraud_category,
        "root_cause_reasoning": verdict_response.root_cause_reasoning,
        "recommendations": verdict_response.recommendations,
        "used_offline_fallback": used_offline_fallback,
    }

    stage_status = "flagged" if verdict_response.verdict in ("reject", "review") else "passed"

    logger.info(
        "Stage 7 AI Judge verdict rendered: %s (confidence=%.2f, fallback=%s)",
        verdict_response.verdict,
        verdict_response.confidence,
        used_offline_fallback,
    )

    return await state.record_stage(
        StageResult(
            stage=PipelineStageName.JUDGE,
            status=stage_status,
            data=detail,
            started_at=started_at,
            completed_at=completed_at,
        )
    )
