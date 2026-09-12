# backend/app/pipeline/workflow.py
"""
LangGraph 8-Stage Pipeline Orchestrator (Anil, W4 D3).

Wires all 8 stages of the VisionForge AI inspection pipeline into a directed,
stateful, and observable execution graph:
1. Quality Check        (Intake validation, blur/lighting/resolution)
2. Authenticity         (ELA, noise analysis, copy-move detection)
3. Reference Match      (CLIP + FAISS golden reference alignment)
4. ROI Scheduler        (PCB / component region segmentation)
5. Evidence Execution   (Concurrent multi-agent inspection: OCR, Label, Structural, VLM)
6. Evidence Fusion      (Weighted anomaly synthesis, composite fraud score)
7. AI Judge             (LLM root-cause reasoning & forensic verdict)
8. Policy Engine        (Industrial governance action: ACCEPT / RETAKE / QUARANTINE / VERIFY)

Handles DB synchronization, evidence persistence, PDF generation, and error recovery.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional, TypedDict
from uuid import UUID

from langgraph.graph import END, StateGraph
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.evidence import AgentType as DBAgentType, Evidence
from app.models.inspection import (
    Inspection,
    InspectionStatus,
    InspectionVerdict,
    PolicyAction,
)
from app.pipeline.stages.authenticity import run_authenticity_stage
from app.pipeline.stages.evidence_execution import run_evidence_execution
from app.pipeline.stages.evidence_fusion import run_evidence_fusion
from app.pipeline.stages.judge import run_judge
from app.pipeline.stages.policy_engine import run_policy_engine
from app.pipeline.stages.quality_check import run_quality_check
from app.pipeline.stages.reference_match import run_reference_match
from app.pipeline.stages.roi_scheduler import run_roi_scheduler
from app.pipeline.state import InspectionState, inspection_state_registry
from app.services.reporting_service import reporting_service
from app.shared.memory import PipelineStageName

logger = logging.getLogger("app.pipeline.workflow")


class PipelineGraphState(TypedDict):
    inspection_id: str
    state: InspectionState
    error: Optional[str]


# ── LangGraph Node Callables ──────────────────────────────────────────────────

async def node_quality_check(graph_state: PipelineGraphState) -> PipelineGraphState:
    state = graph_state["state"]
    logger.info("[%s] Executing Stage 1: Quality Check", state.memory.inspection_id)
    await run_quality_check(state)
    return graph_state


async def node_authenticity(graph_state: PipelineGraphState) -> PipelineGraphState:
    state = graph_state["state"]
    logger.info("[%s] Executing Stage 2: Authenticity", state.memory.inspection_id)
    await run_authenticity_stage(state)
    return graph_state


async def node_reference_match(graph_state: PipelineGraphState) -> PipelineGraphState:
    state = graph_state["state"]
    logger.info("[%s] Executing Stage 3: Reference Match", state.memory.inspection_id)
    await run_reference_match(state)
    return graph_state


async def node_roi_scheduler(graph_state: PipelineGraphState) -> PipelineGraphState:
    state = graph_state["state"]
    logger.info("[%s] Executing Stage 4: ROI Scheduler", state.memory.inspection_id)
    await run_roi_scheduler(state)
    return graph_state


async def node_evidence_execution(graph_state: PipelineGraphState) -> PipelineGraphState:
    state = graph_state["state"]
    logger.info("[%s] Executing Stage 5: Evidence Execution", state.memory.inspection_id)
    await run_evidence_execution(state)
    return graph_state


async def node_evidence_fusion(graph_state: PipelineGraphState) -> PipelineGraphState:
    state = graph_state["state"]
    logger.info("[%s] Executing Stage 6: Evidence Fusion", state.memory.inspection_id)
    await run_evidence_fusion(state)
    return graph_state


async def node_judge(graph_state: PipelineGraphState) -> PipelineGraphState:
    state = graph_state["state"]
    logger.info("[%s] Executing Stage 7: AI Judge", state.memory.inspection_id)
    await run_judge(state)
    return graph_state


async def node_policy_engine(graph_state: PipelineGraphState) -> PipelineGraphState:
    state = graph_state["state"]
    logger.info("[%s] Executing Stage 8: Policy Engine", state.memory.inspection_id)
    await run_policy_engine(state)
    return graph_state


# ── Conditional Routing ───────────────────────────────────────────────────────

def route_after_quality_check(graph_state: PipelineGraphState) -> str:
    """If quality check failed, bypass intermediate stages and jump straight to Policy Engine."""
    state = graph_state["state"]
    if state.memory.quality_passed is False:
        logger.warning(
            "[%s] Quality check failed. Bypassing stages 2-7 to Policy Engine (RETAKE action).",
            state.memory.inspection_id,
        )
        return "policy_engine"
    return "authenticity"


# ── Build Graph ───────────────────────────────────────────────────────────────

def build_inspection_graph():
    builder = StateGraph(PipelineGraphState)

    builder.add_node("quality_check", node_quality_check)
    builder.add_node("authenticity", node_authenticity)
    builder.add_node("reference_match", node_reference_match)
    builder.add_node("roi_scheduler", node_roi_scheduler)
    builder.add_node("evidence_execution", node_evidence_execution)
    builder.add_node("evidence_fusion", node_evidence_fusion)
    builder.add_node("judge", node_judge)
    builder.add_node("policy_engine", node_policy_engine)

    builder.set_entry_point("quality_check")

    builder.add_conditional_edges(
        "quality_check",
        route_after_quality_check,
        {
            "authenticity": "authenticity",
            "policy_engine": "policy_engine",
        },
    )

    builder.add_edge("authenticity", "reference_match")
    builder.add_edge("reference_match", "roi_scheduler")
    builder.add_edge("roi_scheduler", "evidence_execution")
    builder.add_edge("evidence_execution", "evidence_fusion")
    builder.add_edge("evidence_fusion", "judge")
    builder.add_edge("judge", "policy_engine")
    builder.add_edge("policy_engine", END)

    return builder.compile()


pipeline_graph = build_inspection_graph()


# ── Top-Level Pipeline Runner ─────────────────────────────────────────────────

async def run_inspection_pipeline(inspection_id: UUID, db: AsyncSession) -> None:
    """
    Execute the full 8-stage LangGraph inspection pipeline for a given inspection.
    Persists evidence records, updates database models, and generates audit PDF.
    """
    logger.info("Executing 8-stage pipeline for inspection %s", inspection_id)

    # 1. Fetch inspection with relations
    query = (
        select(Inspection)
        .options(
            selectinload(Inspection.vendor),
            selectinload(Inspection.golden_reference),
        )
        .where(Inspection.id == inspection_id)
    )
    result = await db.execute(query)
    inspection = result.scalar_one_or_none()

    if inspection is None:
        raise ValueError(f"Inspection {inspection_id} not found in database")

    # Mark as PROCESSING
    inspection.status = InspectionStatus.PROCESSING
    inspection.updated_at = datetime.now(timezone.utc)
    await db.commit()

    # 2. Get or create InspectionState in memory
    state = await inspection_state_registry.get_or_create(
        inspection_id=inspection.id,
        vendor_id=inspection.vendor_id,
        location=inspection.location,
    )

    # Populate state memory from DB record
    await state.memory.update(
        image_paths=list(inspection.image_paths or []),
        golden_reference_id=inspection.golden_reference_id,
        golden_image_path=inspection.golden_reference.image_path if inspection.golden_reference else None,
        part_code=inspection.golden_reference.part_code if inspection.golden_reference else None,
        product_type=inspection.golden_reference.product_type if inspection.golden_reference else None,
    )

    try:
        # 3. Execute LangGraph workflow
        initial_payload: PipelineGraphState = {
            "inspection_id": str(inspection.id),
            "state": state,
            "error": None,
        }
        await pipeline_graph.ainvoke(initial_payload)

        # 4. Persist in-memory EvidenceRecords to database
        records = state.evidence.get_all_for_inspection(inspection.id)
        for rec in records:
            # Map agent_type to DB Enum
            agent_type_val = DBAgentType(rec.agent_type.value)
            ev_data = rec.evidence or {}
            findings = ev_data.get("component_findings")
            bbox_dict = {}
            if rec.bounding_box and len(rec.bounding_box) >= 4:
                bbox_dict = {
                    "x": rec.bounding_box[0],
                    "y": rec.bounding_box[1],
                    "w": rec.bounding_box[2],
                    "h": rec.bounding_box[3],
                }

            db_evidence = Evidence(
                id=rec.evidence_id,
                inspection_id=inspection.id,
                agent_type=agent_type_val,
                detector_name=rec.agent_type.value,
                confidence=rec.confidence,
                roi_id=rec.roi_id,
                roi_type="roi",
                bounding_box=bbox_dict,
                detected_count=ev_data.get("detected_count"),
                expected_count=ev_data.get("expected_count"),
                component_findings=findings,
                evidence_summary=rec.explanation[:2000],
                explanation=rec.explanation[:2000],
                raw_output=rec.evidence,
                processing_time_ms=int(rec.processing_time_ms),
                failed=rec.failed,
                failure_reason=rec.failure_reason,
            )
            db.add(db_evidence)

        # 5. Update DB Inspection fields
        mem = state.memory
        inspection.quality_passed = bool(mem.quality_passed)
        qc_res = mem.last_stage_result(PipelineStageName.QUALITY_CHECK)
        if qc_res and qc_res.error:
            inspection.quality_failure_reason = qc_res.error[:500]

        inspection.authenticity_score = mem.authenticity_score
        inspection.authenticity_flagged = bool(mem.authenticity_flagged)
        inspection.reference_similarity = mem.similarity_score
        inspection.fraud_probability = mem.fraud_probability
        inspection.judge_confidence = mem.judge_confidence
        inspection.fraud_category = mem.fraud_category
        inspection.root_cause = mem.root_cause

        # Map PolicyAction
        if mem.policy_action:
            try:
                inspection.policy_action = PolicyAction(mem.policy_action)
            except ValueError:
                inspection.policy_action = PolicyAction.ACCEPT

        # Map Verdict
        if inspection.policy_action == PolicyAction.ACCEPT:
            inspection.verdict = InspectionVerdict.ACCEPT
        elif inspection.policy_action == PolicyAction.QUARANTINE:
            inspection.verdict = InspectionVerdict.REJECT
        elif inspection.policy_action == PolicyAction.VENDOR_VERIFICATION:
            inspection.verdict = InspectionVerdict.REVIEW
        elif inspection.policy_action == PolicyAction.RETAKE:
            inspection.verdict = InspectionVerdict.REJECT
        else:
            inspection.verdict = InspectionVerdict.PENDING

        inspection.working_memory = mem.to_dict()
        inspection.status = InspectionStatus.COMPLETED
        inspection.updated_at = datetime.now(timezone.utc)

        # 6. Generate audit PDF report
        vendor_name = inspection.vendor.name if inspection.vendor else "Unknown Vendor"
        part_code = inspection.golden_reference.part_code if inspection.golden_reference else "GEN-PART"
        prod_type = inspection.golden_reference.product_type if inspection.golden_reference else "Electronics"
        evidence_items = [
            {
                "agent_type": r.agent_type.value,
                "roi_id": r.roi_id,
                "confidence": r.confidence,
                "has_defect": not r.failed and r.confidence < 0.70,
                "failed": r.failed,
                "explanation": r.explanation,
            }
            for r in records
        ]

        pdf_path = reporting_service.generate_pdf_report(
            case_number=inspection.case_number,
            inspection_id=inspection.id,
            vendor_name=vendor_name,
            location=inspection.location,
            part_code=part_code,
            product_type=prod_type,
            verdict=inspection.verdict.value,
            policy_action=inspection.policy_action.value if inspection.policy_action else "accept",
            fraud_score=float((inspection.fraud_probability or 0.0) * 100.0),
            confidence=float((inspection.judge_confidence or 0.95) * 100.0),
            fraud_category=inspection.fraud_category or "clean",
            root_cause=inspection.root_cause or "Conforms to certified tolerances.",
            authenticity_score=inspection.authenticity_score,
            reference_similarity=inspection.reference_similarity,
            evidence_items=evidence_items,
            created_at=inspection.created_at,
        )
        inspection.report_path = pdf_path

        await db.commit()
        logger.info(
            "Inspection %s successfully completed. Verdict=%s, PolicyAction=%s, PDF=%s",
            inspection.case_number,
            inspection.verdict.value,
            inspection.policy_action.value if inspection.policy_action else None,
            pdf_path,
        )

    except Exception as exc:
        logger.exception("Pipeline execution failed for inspection %s: %s", inspection_id, exc)
        inspection.status = InspectionStatus.FAILED
        inspection.error_message = str(exc)[:2000]
        inspection.updated_at = datetime.now(timezone.utc)
        await db.commit()
        raise
