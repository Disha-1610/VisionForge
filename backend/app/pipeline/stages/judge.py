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


def _extract_forensic_agent_findings(state: InspectionState) -> dict[str, Any]:
    """Gathers discrete findings across all evidence agents for forensic explainability."""
    records = state.evidence.get_all_for_inspection(state.memory.inspection_id)
    structural_findings: list[str] = []
    ocr_findings: list[str] = []
    vlm_findings: list[str] = []
    label_findings: list[str] = []

    for r in records:
        ev = r.evidence or {}
        if r.agent_type.value == "structural":
            comp_findings = ev.get("component_findings")
            missing = ev.get("missing_components", [])
            extra = ev.get("extra_components", [])
            ssim = ev.get("ssim_score") or ev.get("ssim")
            if missing:
                structural_findings.append(f"Missing components ({len(missing)}): {missing}")
            if extra:
                structural_findings.append(f"Counterfeit/Extra components ({len(extra)}): {extra}")
            if isinstance(comp_findings, list):
                for c in comp_findings:
                    if isinstance(c, dict) and c.get("status") in ("missing", "extra", "mismatch"):
                        structural_findings.append(f"{c.get('class_name', 'component')}: {c.get('status')}")
            if ssim is not None and ssim < 0.85:
                structural_findings.append(f"SSIM similarity drift: {float(ssim):.2f}")

        elif r.agent_type.value == "ocr":
            mismatches = ev.get("mismatches", [])
            similarity = ev.get("similarity")
            if mismatches:
                structural_findings.append(f"OCR Serial/Text mismatch: {mismatches}")
            elif similarity is not None and similarity < 0.90:
                ocr_findings.append(f"OCR match similarity low: {float(similarity):.2f}")

        elif r.agent_type.value == "vlm":
            if ev.get("has_defect") or ev.get("anomaly_detected"):
                dtype = ev.get("defect_type", "visual_anomaly")
                sev = ev.get("severity", "medium")
                desc = ev.get("description") or r.explanation
                vlm_findings.append(f"VLM Flag [{sev.upper()}]: {dtype} - {desc}")

        elif r.agent_type.value == "label":
            if not ev.get("match", True) or (ev.get("match_score", 1.0) < 0.70):
                score = ev.get("match_score", 0.0)
                label_findings.append(f"Label template deviation: correlation score {float(score):.2f}")

    return {
        "structural": structural_findings,
        "ocr": ocr_findings,
        "vlm": vlm_findings,
        "label": label_findings,
    }


def _build_judge_prompt(state: InspectionState) -> list[LLMMessage]:
    """Constructs forensic analysis prompt with structured inspection context."""
    mem = state.memory
    fused = mem.fused_evidence or {}
    agent_findings = _extract_forensic_agent_findings(state)

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
        "agent_findings": agent_findings,
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
        "Be extremely specific in root_cause_reasoning, citing exact component names, serial mismatches, "
        "or visual anomalies so quality engineers understand the exact defect.\n"
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
    agent_findings = _extract_forensic_agent_findings(state)
    all_findings: list[str] = (
        agent_findings.get("structural", [])
        + agent_findings.get("ocr", [])
        + agent_findings.get("vlm", [])
        + agent_findings.get("label", [])
    )

    if fraud_prob >= 0.65 or "missing_components" in category or "counterfeit" in category:
        defect_details = "; ".join(all_findings[:3]) if all_findings else "Critical component or structural deviation"
        return JudgeVerdictResponse(
            verdict="reject",
            confidence=0.92,
            fraud_category=category,
            root_cause_reasoning=(
                f"Hardware anomaly threshold exceeded (fraud risk: {fraud_prob*100:.1f}%). "
                f"Primary root cause: {defect_details}. Physical sample fails golden engineering specification."
            ),
            recommendations=[
                "Quarantine affected batch immediately to prevent assembly integration",
                "Initiate vendor supply chain counterfeit/rework investigation",
            ],
        )

    if fraud_prob >= 0.30 or state.memory.authenticity_flagged:
        defect_details = "; ".join(all_findings[:3]) if all_findings else "Statistical variance or unverified lot marking"
        return JudgeVerdictResponse(
            verdict="review",
            confidence=0.78,
            fraud_category=category,
            root_cause_reasoning=(
                f"Secondary anomaly detected (fraud risk: {fraud_prob*100:.1f}%). "
                f"Findings: {defect_details}. Requires manual verification by Quality Assurance Lead."
            ),
            recommendations=[
                "Perform high-magnification optical inspection on target ROIs",
                "Verify component lot date code with authorized distributor",
            ],
        )

    return JudgeVerdictResponse(
        verdict="accept",
        confidence=0.95,
        fraud_category="clean",
        root_cause_reasoning=(
            "All inspected hardware regions, discrete YOLO component counts, OCR markings, "
            "and optical textures strictly conform to the golden reference specification within certified tolerance limits."
        ),
        recommendations=["Release batch to production assembly / fulfillment"],
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
