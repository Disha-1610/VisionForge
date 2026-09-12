# backend/app/pipeline/stages/evidence_fusion.py
"""
Stage 6 — Evidence Fusion & Signal Weighting (Anil, W4 D1).

Aggregates and synthesizes evidence records collected from all Stage 5 agents
(OCR, Label, Structural+YOLO, VLM) as well as prior stage metrics (Authenticity,
Reference Match).

Key Responsibilities:
1. Deduplicate & group findings across ROIs and agents.
2. Signal weighting:
   - YOLO component mismatch (missing / extra counterfeit parts): High Weight (0.45)
   - OCR character diff on serial / part numbers: High Weight (0.40)
   - VLM visual anomaly flags & severity: Weight (0.35)
   - Label template correlation drops: Weight (0.30)
   - Structural SSIM pixel drift / difference heatmap: Weight (0.25)
3. Calculate composite fraud probability (0.0 - 1.0) and fraud score (0 - 100).
4. Classify primary fraud category.
5. Store fused payload into WorkingMemory and record StageResult.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.pipeline.state import InspectionState
from app.shared.evidence_store import AgentType, EvidenceRecord
from app.shared.memory import PipelineStageName, StageResult

logger = logging.getLogger("app.pipeline.evidence_fusion")


# Signal weights per agent type for anomaly contributions
AGENT_WEIGHTS: dict[AgentType, float] = {
    AgentType.STRUCTURAL: 0.45,
    AgentType.OCR: 0.40,
    AgentType.VLM: 0.35,
    AgentType.LABEL: 0.30,
}

VLM_SEVERITY_MULTIPLIER: dict[str, float] = {
    "critical": 1.0,
    "high": 0.85,
    "medium": 0.55,
    "low": 0.25,
}


def _extract_agent_anomaly_score(record: EvidenceRecord) -> tuple[float, str | None]:
    """
    Extracts an anomaly score (0.0 = clean, 1.0 = severe defect) and issue tag
    from a single EvidenceRecord.
    """
    if record.failed:
        # Agent execution failure is flagged as an operational risk
        return 0.20, f"agent_failure:{record.failure_reason or 'unknown'}"

    evidence_data = record.evidence or {}

    if record.agent_type == AgentType.STRUCTURAL:
        # 1. Check YOLO component count anomalies
        findings = evidence_data.get("component_findings") or {}
        missing = findings.get("missing", [])
        extra = findings.get("extra", [])
        mismatched = findings.get("mismatched", [])

        if missing:
            return 0.95, f"missing_components:{len(missing)}"
        if extra:
            return 0.90, f"counterfeit_extra_components:{len(extra)}"
        if mismatched:
            return 0.85, f"component_count_mismatch:{len(mismatched)}"

        # 2. Check SSIM
        ssim_val = evidence_data.get("ssim")
        if ssim_val is not None and isinstance(ssim_val, (int, float)):
            if ssim_val < 0.70:
                return 0.80, f"severe_ssim_drift:{ssim_val:.2f}"
            if ssim_val < 0.80:
                return 0.50, f"moderate_ssim_drift:{ssim_val:.2f}"
            if ssim_val < 0.90:
                return 0.20, f"minor_ssim_drift:{ssim_val:.2f}"

        # 3. Check generic defect flag
        if evidence_data.get("defect_detected") or not evidence_data.get("match", True):
            return 0.60, "structural_defect"

        return 0.0, None

    if record.agent_type == AgentType.OCR:
        mismatches = evidence_data.get("mismatches", [])
        similarity = evidence_data.get("similarity", 1.0)
        match = evidence_data.get("match", True)

        if not match or len(mismatches) > 0:
            if similarity < 0.5:
                return 0.95, f"tampered_serial_major:{len(mismatches)}_diffs"
            return 0.75, f"tampered_serial_minor:{len(mismatches)}_diffs"

        return 0.0, None

    if record.agent_type == AgentType.VLM:
        anomaly_detected = evidence_data.get("anomaly_detected", False)
        if anomaly_detected:
            severity = str(evidence_data.get("severity", "medium")).lower()
            mult = VLM_SEVERITY_MULTIPLIER.get(severity, 0.5)
            defect_type = evidence_data.get("defect_type", "visual_anomaly")
            return min(1.0, 0.75 * mult + 0.25), f"vlm_anomaly:{defect_type}:{severity}"

        return 0.0, None

    if record.agent_type == AgentType.LABEL:
        match = evidence_data.get("match", True)
        confidence = evidence_data.get("confidence", record.confidence)
        if not match or confidence < 0.65:
            return 0.75, f"label_mismatch_low_conf:{confidence:.2f}"

        return 0.0, None

    return 0.0, None


def determine_primary_fraud_category(issues: list[str]) -> str:
    """Classifies primary fraud category from aggregated issue tags."""
    if not issues:
        return "clean"

    issue_str = " ".join(issues).lower()
    if "missing_components" in issue_str:
        return "missing_components"
    if "counterfeit_extra" in issue_str or "rework" in issue_str:
        return "counterfeit_rework"
    if "tampered_serial" in issue_str or "serial" in issue_str:
        return "tampered_serial"
    if "vlm_anomaly" in issue_str:
        return "visual_anomaly"
    if "label_mismatch" in issue_str:
        return "label_fraud"
    if "ssim" in issue_str or "structural" in issue_str:
        return "structural_defect"
    if "authenticity" in issue_str:
        return "tampered_image_authenticity"

    return "general_anomaly"


async def run_evidence_fusion(state: InspectionState) -> StageResult:
    """
    Stage 6 entrypoint. Consumes evidence records from EvidenceStore,
    fuses multi-agent signals, calculates fraud probability & score,
    and updates WorkingMemory.
    """
    started_at = datetime.now(timezone.utc)
    logger.info("Starting Stage 6 Evidence Fusion for inspection %s", state.memory.inspection_id)

    records: list[EvidenceRecord] = state.evidence.get_all_for_inspection(state.memory.inspection_id)

    # Group records by ROI
    roi_groups: dict[str, list[EvidenceRecord]] = defaultdict(list)
    agent_groups: dict[AgentType, list[EvidenceRecord]] = defaultdict(list)

    for r in records:
        roi_groups[r.roi_id].append(r)
        agent_groups[r.agent_type].append(r)

    # Calculate weighted anomaly scores
    weighted_scores: list[float] = []
    weights: list[float] = []
    detected_issues: list[str] = []
    roi_summaries: list[dict[str, Any]] = []

    for roi_id, recs in roi_groups.items():
        roi_max_score = 0.0
        roi_issues: list[str] = []

        for r in recs:
            score, issue = _extract_agent_anomaly_score(r)
            agent_weight = AGENT_WEIGHTS.get(r.agent_type, 0.30)
            weighted_scores.append(score * agent_weight)
            weights.append(agent_weight)

            if issue:
                detected_issues.append(issue)
                roi_issues.append(issue)
            roi_max_score = max(roi_max_score, score)

        roi_summaries.append({
            "roi_id": roi_id,
            "record_count": len(recs),
            "max_anomaly_score": round(roi_max_score, 3),
            "issues": roi_issues,
            "has_defect": roi_max_score >= 0.40,
        })

    # Prior stage influences: Authenticity & Reference Match
    authenticity_flagged = state.memory.authenticity_flagged
    authenticity_score = state.memory.authenticity_score
    if authenticity_flagged:
        weighted_scores.append(0.85 * 0.40)
        weights.append(0.40)
        detected_issues.append("authenticity_flagged")

    ref_sim = state.memory.similarity_score
    if ref_sim is not None and ref_sim < 0.70:
        weighted_scores.append(0.70 * 0.30)
        weights.append(0.30)
        detected_issues.append(f"low_reference_similarity:{ref_sim:.2f}")

    # Compute composite fraud probability (0.0 to 1.0)
    if weights and sum(weights) > 0:
        avg_weighted = sum(weighted_scores) / sum(weights)
        max_single_score = max([_extract_agent_anomaly_score(r)[0] for r in records], default=0.0)
        composite_prob = round(min(1.0, 0.65 * avg_weighted + 0.35 * max_single_score), 4)
    else:
        composite_prob = 0.0

    fraud_score_pct = round(composite_prob * 100.0, 2)
    primary_category = determine_primary_fraud_category(detected_issues)

    # Composite confidence in this assessment
    if records:
        avg_agent_conf = sum(r.confidence for r in records) / len(records)
        composite_conf = round(avg_agent_conf * 100.0, 2)
    else:
        composite_conf = 85.0

    fused_payload: dict[str, Any] = {
        "total_evidence_records": len(records),
        "total_rois_evaluated": len(roi_groups),
        "roi_summaries": roi_summaries,
        "detected_issues": detected_issues,
        "fraud_score": fraud_score_pct,
        "fraud_probability": composite_prob,
        "confidence": composite_conf,
        "primary_category": primary_category,
        "authenticity_flagged": authenticity_flagged,
        "authenticity_score": authenticity_score,
        "reference_similarity": ref_sim,
    }

    await state.memory.update(
        fused_evidence=fused_payload,
        fraud_probability=composite_prob,
        fraud_category=primary_category,
    )

    stage_status = "flagged" if composite_prob >= 0.30 else "passed"
    completed_at = datetime.now(timezone.utc)

    logger.info(
        "Stage 6 Evidence Fusion completed: fraud_score=%.1f%%, category=%s, issues=%d",
        fraud_score_pct,
        primary_category,
        len(detected_issues),
    )

    return await state.record_stage(
        StageResult(
            stage=PipelineStageName.EVIDENCE_FUSION,
            status=stage_status,
            data=fused_payload,
            started_at=started_at,
            completed_at=completed_at,
        )
    )
