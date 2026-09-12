# backend/app/routers/reports.py
"""
Reports Router — Inspection Reports API & PDF Downloads (Disha, W4 D3).

Endpoints:
  GET /api/v1/reports               - List/filter inspection audit reports
  GET /api/v1/reports/{id}          - Fetch detailed report JSON
  GET /api/v1/reports/{id}/pdf      - Download generated PDF audit report
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.evidence import Evidence
from app.models.inspection import Inspection, InspectionStatus
from app.models.product import GoldenReference
from app.models.user import User
from app.models.vendor import Vendor
from app.schemas.report import (
    AgentEvidenceItem,
    BoundingBox,
    PolicyActionEnum,
    ReportListResponse,
    ReportResponse,
    VerdictEnum,
)
from app.services.reporting_service import reporting_service

router = APIRouter(prefix="/reports", tags=["reports"])


def _map_inspection_to_report_response(
    inspection: Inspection,
    vendor_name: str,
    part_code: str,
    golden_img: str,
    evidence_records: list[Evidence],
) -> ReportResponse:
    """Helper to transform Inspection ORM model into ReportResponse schema."""
    evidence_items: list[AgentEvidenceItem] = []
    for ev in evidence_records:
        bbox_data = ev.bounding_box or {}
        bboxes: list[BoundingBox] = []
        if isinstance(bbox_data, dict) and "x" in bbox_data:
            bboxes.append(
                BoundingBox(
                    x=float(bbox_data.get("x", 0)),
                    y=float(bbox_data.get("y", 0)),
                    width=float(bbox_data.get("w", bbox_data.get("width", 0))),
                    height=float(bbox_data.get("h", bbox_data.get("height", 0))),
                    label=bbox_data.get("label"),
                )
            )

        evidence_items.append(
            AgentEvidenceItem(
                agent_name=ev.agent_type.value if hasattr(ev.agent_type, "value") else str(ev.agent_type),
                confidence=float(ev.confidence),
                roi=ev.roi_id,
                explanation=ev.explanation or ev.evidence_summary,
                processing_time_ms=float(ev.processing_time_ms),
                bounding_boxes=bboxes,
                expected_component_count=ev.expected_count,
                detected_component_count=ev.detected_count,
            )
        )

    # Convert verdict and policy action
    v_val = inspection.verdict.value if hasattr(inspection.verdict, "value") else str(inspection.verdict)
    if v_val not in [e.value for e in VerdictEnum]:
        v_val = VerdictEnum.ACCEPT.value
    verdict_enum = VerdictEnum(v_val)

    p_val = (
        inspection.policy_action.value
        if inspection.policy_action and hasattr(inspection.policy_action, "value")
        else (inspection.policy_action or "accept")
    )
    if p_val not in [e.value for e in PolicyActionEnum]:
        p_val = PolicyActionEnum.ACCEPT.value
    policy_enum = PolicyActionEnum(p_val)

    return ReportResponse(
        id=inspection.id,
        case_id=inspection.case_number,
        inspection_id=inspection.id,
        vendor_id=inspection.vendor_id,
        vendor_name=vendor_name,
        location=inspection.location,
        part_id=part_code,
        golden_image_path=golden_img,
        inspection_image_paths=inspection.image_paths or [],
        authenticity_score=float(inspection.authenticity_score or 1.0),
        authenticity_flagged=bool(inspection.authenticity_flagged),
        fraud_score=float((inspection.fraud_probability or 0.0) * 100.0),
        confidence_score=float((inspection.judge_confidence or 0.95) * 100.0),
        fraud_category=inspection.fraud_category,
        verdict=verdict_enum,
        root_cause_explanation=inspection.root_cause or "No root cause explanation provided.",
        policy_action=policy_enum,
        evidence=evidence_items,
        reviewer_id=inspection.reviewed_by,
        reviewer_comment=inspection.reviewer_comment,
        is_overridden=inspection.review_decision.value == "overridden" if inspection.review_decision else False,
        report_pdf_path=inspection.report_path,
        created_at=inspection.created_at,
        updated_at=inspection.updated_at,
    )


@router.get("", response_model=ReportListResponse)
async def list_reports(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    vendor_id: Optional[UUID] = None,
    verdict: Optional[str] = None,
    policy_action: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> ReportListResponse:
    """List inspection reports with optional filtering."""
    if page < 1 or page_size < 1 or page_size > 100:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Invalid pagination parameters")

    query = (
        select(Inspection)
        .options(
            selectinload(Inspection.vendor),
            selectinload(Inspection.golden_reference),
            selectinload(Inspection.evidence_records),
        )
        .order_by(Inspection.created_at.desc())
    )

    if vendor_id:
        query = query.where(Inspection.vendor_id == vendor_id)
    if verdict:
        query = query.where(Inspection.verdict == verdict)
    if policy_action:
        query = query.where(Inspection.policy_action == policy_action)

    result = await db.execute(query)
    all_inspections = result.scalars().all()
    total = len(all_inspections)

    start = (page - 1) * page_size
    paged_inspections = all_inspections[start : start + page_size]

    items: list[ReportResponse] = []
    for insp in paged_inspections:
        v_name = insp.vendor.name if insp.vendor else "Unknown Vendor"
        part_code = insp.golden_reference.part_code if insp.golden_reference else "N/A"
        golden_img = insp.golden_reference.image_path if insp.golden_reference else ""
        ev_records = insp.evidence_records or []
        items.append(
            _map_inspection_to_report_response(
                insp, v_name, part_code, golden_img, ev_records
            )
        )

    return ReportListResponse(total=total, items=items)


@router.get("/{inspection_id}", response_model=ReportResponse)
async def get_report(
    inspection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReportResponse:
    """Fetch structured JSON report for a specific inspection."""
    query = (
        select(Inspection)
        .options(
            selectinload(Inspection.vendor),
            selectinload(Inspection.golden_reference),
            selectinload(Inspection.evidence_records),
        )
        .where(Inspection.id == inspection_id)
    )
    result = await db.execute(query)
    inspection = result.scalar_one_or_none()

    if inspection is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Inspection report not found")

    v_name = inspection.vendor.name if inspection.vendor else "Unknown Vendor"
    part_code = inspection.golden_reference.part_code if inspection.golden_reference else "N/A"
    golden_img = inspection.golden_reference.image_path if inspection.golden_reference else ""
    ev_records = inspection.evidence_records or []

    return _map_inspection_to_report_response(
        inspection, v_name, part_code, golden_img, ev_records
    )


@router.get("/{inspection_id}/pdf")
async def download_report_pdf(
    inspection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Download PDF audit report for an inspection (generates if missing)."""
    query = (
        select(Inspection)
        .options(
            selectinload(Inspection.vendor),
            selectinload(Inspection.golden_reference),
            selectinload(Inspection.evidence_records),
        )
        .where(Inspection.id == inspection_id)
    )
    result = await db.execute(query)
    inspection = result.scalar_one_or_none()

    if inspection is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Inspection not found")

    pdf_path = inspection.report_path
    if not pdf_path or not os.path.exists(pdf_path):
        # Generate on the fly
        v_name = inspection.vendor.name if inspection.vendor else "Unknown Vendor"
        part_code = inspection.golden_reference.part_code if inspection.golden_reference else "GEN-PART"
        prod_type = inspection.golden_reference.product_type if inspection.golden_reference else "Electronics"
        ev_items = [
            {
                "agent_type": ev.agent_type.value if hasattr(ev.agent_type, "value") else str(ev.agent_type),
                "roi_id": ev.roi_id,
                "confidence": ev.confidence,
                "has_defect": not ev.failed and ev.confidence < 0.70,
                "failed": ev.failed,
                "explanation": ev.explanation or ev.evidence_summary,
            }
            for ev in (inspection.evidence_records or [])
        ]

        pdf_path = reporting_service.generate_pdf_report(
            case_number=inspection.case_number,
            inspection_id=inspection.id,
            vendor_name=v_name,
            location=inspection.location,
            part_code=part_code,
            product_type=prod_type,
            verdict=inspection.verdict.value if hasattr(inspection.verdict, "value") else str(inspection.verdict),
            policy_action=inspection.policy_action.value if inspection.policy_action and hasattr(inspection.policy_action, "value") else str(inspection.policy_action or "accept"),
            fraud_score=float((inspection.fraud_probability or 0.0) * 100.0),
            confidence=float((inspection.judge_confidence or 0.95) * 100.0),
            fraud_category=inspection.fraud_category or "clean",
            root_cause=inspection.root_cause or "Conforms to certified tolerances.",
            authenticity_score=inspection.authenticity_score,
            reference_similarity=inspection.reference_similarity,
            evidence_items=ev_items,
            created_at=inspection.created_at,
        )
        inspection.report_path = pdf_path
        await db.commit()

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"{inspection.case_number}.pdf",
    )
