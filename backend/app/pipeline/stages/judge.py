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
            missing_names = []
            for m in missing:
                missing_names.append(str(m.get("class_name", m)) if isinstance(m, dict) else str(m))
            extra_names = []
            for e in extra:
                extra_names.append(str(e.get("class_name", e)) if isinstance(e, dict) else str(e))
            if missing_names:
                names = ", ".join(missing_names[:4])
                structural_findings.append(
                    f"{len(missing_names)} component(s) are missing from the board ({names})."
                )
            if extra_names:
                names = ", ".join(extra_names[:4])
                structural_findings.append(
                    f"{len(extra_names)} unexpected component(s) were found that should not be present ({names})."
                )
            if isinstance(comp_findings, list):
                for c in comp_findings:
                    if isinstance(c, dict) and c.get("status") in ("missing", "extra", "mismatch"):
                        cls = c.get("class_name", "component")
                        st = c.get("status")
                        if st == "missing":
                            structural_findings.append(f"A {cls} component is missing.")
                        elif st == "extra":
                            structural_findings.append(f"An extra {cls} component was found.")
                        else:
                            structural_findings.append(f"The {cls} component does not match the reference.")
            if ssim is not None and ssim < 0.85:
                structural_findings.append(
                    f"The board surface shows a significant difference from the golden reference "
                    f"(similarity {float(ssim):.2f})."
                )

        elif r.agent_type.value == "ocr":
            has_defect = ev.get("has_defect", False)
            similarity = ev.get("similarity", 1.0)
            threshold = ev.get("threshold", 0.85)
            if has_defect or (similarity is not None and similarity < threshold):
                mismatches = ev.get("mismatches", [])
                if mismatches:
                    ocr_findings.append(
                        f"The serial or text on the label does not match the golden reference "
                        f"(similarity {float(similarity):.1%} below threshold {float(threshold):.1%})."
                    )
                else:
                    ocr_findings.append(
                        f"The OCR engine read the text with only {float(similarity):.0%} similarity to the reference.",
                    )

        elif r.agent_type.value == "vlm":
            if ev.get("has_defect") or ev.get("anomaly_detected"):
                dtype = str(ev.get("defect_type", "visual_anomaly")).replace("_", " ")
                sev = ev.get("severity", "medium")
                desc = (ev.get("description") or r.explanation or "")
                vlm_findings.append(
                    f"The vision analysis flagged a {dtype} issue at {sev} severity. {desc}".strip()
                )

        elif r.agent_type.value == "label":
            if not ev.get("match", True) or (ev.get("match_score", 1.0) < 0.70):
                score = ev.get("match_score", 0.0)
                label_findings.append(
                    f"The QC label template does not match the golden reference (correlation {float(score):.2f})."
                )

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
        "declared_product_type": getattr(mem, "declared_product_type", None) or mem.product_type,
        "hardware_category_mismatch": getattr(mem, "hardware_category_mismatch", False),
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
        "- 'review': Borderline anomaly, hardware category mismatch (e.g. declared motherboard but visual match is RAM), "
        "minor solder bridge risk, low template match, or unverified vendor.\n"
        "- 'accept': All components and identifiers match golden engineering reference within tolerance.\n"
        "- If hardware_category_mismatch is true, explain clearly that the operator declared one hardware type but visual intelligence "
        "matched another, and recommend 'review' to verify intake classification.\n"
        "Be extremely specific in root_cause_reasoning, citing exact component names, serial mismatches, "
        "or visual anomalies so quality engineers understand the exact defect.\n"
        "LANGUAGE RULES (very important):\n"
        "- Write root_cause_reasoning in clear, simple, plain English sentences that anyone can read. "
        "Imagine explaining the problem to a non-technical shop-floor worker.\n"
        "- Never copy raw machine tags or codes like 'missing_components:2' or 'tampered_serial_major:0_diffs' "
        "into your answer. Instead, describe them in words, for example: 'Two components were missing from the board.' "
        "or 'The serial number appears to have been tampered with.'\n"
        "- Use short paragraphs and natural sentences. No bullet-style log dumps, no colons-with-counts, "
        "no underscore identifiers. Every sentence must read like human speech.\n"
        "- Keep the analysis thorough but readable; prioritize clarity over jargon.\n\n"
        "OUTPUT FORMAT (MANDATORY):\n"
        "You must respond with ONLY a valid JSON object matching this schema. Do not output markdown backticks or text outside the JSON object:\n"
        "{\n"
        '  "verdict": "accept" | "reject" | "review",\n'
        '  "confidence": 0.95,\n'
        '  "fraud_category": "missing_components",\n'
        '  "root_cause_reasoning": "Plain English description of what was inspected and why this verdict was reached.",\n'
        '  "recommendations": ["Recommendation item 1", "Recommendation item 2"]\n'
        "}"
    )

    user_prompt = (
        "Please analyze the following inspection case evidence and determine the verdict:\n\n"
        f"```json\n{json.dumps(context_payload, indent=2)}\n```\n\n"
        "Provide your evaluation in structured JSON with: "
        "verdict ('accept', 'reject', or 'review'), confidence (0.0-1.0), "
        "fraud_category, root_cause_reasoning, and recommendations.\n"
        "Remember: root_cause_reasoning must be simple, plain English sentences with short paragraphs. "
        "Do not reproduce machine tags or technical codes."
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
        defect_details = ". ".join(all_findings[:3]) if all_findings else "Critical component or structural deviation"
        return JudgeVerdictResponse(
            verdict="reject",
            confidence=0.92,
            fraud_category=category,
            root_cause_reasoning=(
                f"This board does not meet the golden engineering specification. "
                f"{defect_details} "
                f"The overall fraud risk is {fraud_prob*100:.1f}%."
            ),
            recommendations=[
                "Quarantine affected batch immediately to prevent assembly integration",
                "Initiate vendor supply chain counterfeit/rework investigation",
            ],
        )

    if getattr(state.memory, "hardware_category_mismatch", False):
        declared = getattr(state.memory, "declared_product_type", "unknown")
        matched = state.memory.product_type
        return JudgeVerdictResponse(
            verdict="review",
            confidence=0.88,
            fraud_category="category_mismatch",
            root_cause_reasoning=(
                f"A hardware category mismatch was detected. The operator declared '{declared}', "
                f"but visual intelligence identified a '{matched}' module. "
                "Manual review is required to verify intake classification."
            ),
            recommendations=[
                "Confirm physical component part code on the intake tray",
                "Re-submit with the matching product type if the wrong category was selected",
            ],
        )

    if fraud_prob >= 0.30 or state.memory.authenticity_flagged:
        defect_details = ". ".join(all_findings[:3]) if all_findings else "Some variance was found in the board"
        return JudgeVerdictResponse(
            verdict="review",
            confidence=0.78,
            fraud_category=category,
            root_cause_reasoning=(
                f"Minor issue detected on this board. {defect_details}. "
                f"Fraud risk is {fraud_prob*100:.1f}%. A Quality Assurance Lead should verify this manually."
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
            "All inspected areas match the golden engineering specification. "
            "Every component is present and correctly placed, the serial markings and labels are genuine, "
            "and the surface quality is within the allowed tolerance."
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
