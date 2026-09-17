# backend/app/pipeline/stages/policy_engine.py
"""
Stage 8 — Industrial Policy Engine (Anil, W4 D2).

Maps inspection evidence, fraud scores, judge verdicts, and quality metrics
to concrete industrial business governance actions:
- ACCEPT: Hardware is genuine and certified within tolerance.
- RETAKE: Optical image quality is insufficient (blurry, underexposed, corrupt).
- QUARANTINE: Hardware counterfeit or severe defect detected. Block inventory.
- VENDOR_VERIFICATION: Borderline anomaly requiring vendor confirmation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.models.inspection import PolicyAction
from app.pipeline.state import InspectionState
from app.shared.memory import PipelineStageName, StageResult

logger = logging.getLogger("app.pipeline.policy_engine")


def evaluate_policy_action(state: InspectionState) -> tuple[PolicyAction, str, dict[str, Any]]:
    """
    Applies deterministic business rules to calculate the final policy action.
    Returns: (PolicyAction, explanation, policy_metadata)
    """
    mem = state.memory
    fused = mem.fused_evidence or {}
    fraud_prob = mem.fraud_probability or 0.0
    authenticity_flagged = mem.authenticity_flagged
    quality_passed = mem.quality_passed

    # Find judge stage verdict if available
    judge_result = mem.last_stage_result(PipelineStageName.JUDGE)
    judge_verdict = None
    if judge_result and judge_result.data:
        judge_verdict = judge_result.data.get("verdict")

    # Rule 1: Intake Quality Failure -> RETAKE
    if quality_passed is False:
        qc_result = mem.last_stage_result(PipelineStageName.QUALITY_CHECK)
        qc_err = qc_result.error if qc_result else "Image quality below operational standards"
        return (
            PolicyAction.RETAKE,
            f"Image quality check failed ({qc_err}). Requesting high-resolution retake from operator.",
            {"rule_triggered": "QUALITY_CHECK_FAILED", "quality_passed": False},
        )

    # Rule 2: Confirmed Defect / Counterfeit -> QUARANTINE
    critical_categories = {"missing_components", "counterfeit_rework", "tampered_serial"}
    category = mem.fraud_category or fused.get("primary_category", "clean")

    if (
        judge_verdict == "reject"
        or fraud_prob >= 0.70
        or category in critical_categories
        or fused.get("fraud_score", 0.0) >= 70.0
    ):
        return (
            PolicyAction.QUARANTINE,
            (
                f"Severe anomaly detected (fraud probability: {fraud_prob*100:.1f}%, category: {category}). "
                "Hardware blocked. Mandatory quarantine applied to prevent assembly contamination."
            ),
            {
                "rule_triggered": "CONFIRMED_ANOMALY_OR_REJECT",
                "fraud_probability": fraud_prob,
                "fraud_category": category,
            },
        )

    # Rule 3: Borderline Anomaly / Verification -> VENDOR_VERIFICATION
    category_mismatch = getattr(mem, "hardware_category_mismatch", False)
    if (
        judge_verdict == "review"
        or category_mismatch
        or fraud_prob >= 0.30
        or authenticity_flagged
        or fused.get("fraud_score", 0.0) >= 30.0
    ):
        explanation = (
            f"Hardware category mismatch detected (declared '{getattr(mem, 'declared_product_type', 'unknown')}' "
            f"vs visual match '{mem.product_type}'). Part held for secondary verification."
            if category_mismatch
            else f"Borderline anomaly detected (fraud probability: {fraud_prob*100:.1f}%). Part held for secondary inspection and vendor lot verification."
        )
        return (
            PolicyAction.VENDOR_VERIFICATION,
            explanation,
            {
                "rule_triggered": "BORDERLINE_REVIEW_REQUIRED",
                "fraud_probability": fraud_prob,
                "authenticity_flagged": authenticity_flagged,
                "hardware_category_mismatch": category_mismatch,
            },
        )

    # Rule 4: All Clear -> ACCEPT
    return (
        PolicyAction.ACCEPT,
        "All optical, structural, and authenticity specifications conform to certified golden standards. Released for inventory.",
        {"rule_triggered": "STANDARD_PASS", "fraud_probability": fraud_prob},
    )


async def run_policy_engine(state: InspectionState) -> StageResult:
    """
    Stage 8 entrypoint. Evaluates policy action, updates WorkingMemory,
    and returns StageResult.
    """
    started_at = datetime.now(timezone.utc)
    logger.info("Starting Stage 8 Policy Engine for inspection %s", state.memory.inspection_id)

    action, explanation, meta = evaluate_policy_action(state)

    # Update WorkingMemory
    await state.memory.update(policy_action=action.value)

    completed_at = datetime.now(timezone.utc)
    detail: dict[str, Any] = {
        "policy_action": action.value,
        "explanation": explanation,
        "metadata": meta,
    }

    stage_status = "flagged" if action in (PolicyAction.QUARANTINE, PolicyAction.RETAKE) else "passed"

    logger.info(
        "Stage 8 Policy Engine determined action: %s (%s)",
        action.value,
        explanation[:100],
    )

    return await state.record_stage(
        StageResult(
            stage=PipelineStageName.POLICY_ENGINE,
            status=stage_status,
            data=detail,
            started_at=started_at,
            completed_at=completed_at,
        )
    )
