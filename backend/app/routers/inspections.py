import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status as http_status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal, get_db
from app.core.security import get_current_user, require_roles
from app.models.inspection import Inspection, InspectionStatus, InspectionVerdict, ReviewDecision
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.pipeline.state import inspection_state_registry
from app.pipeline.workflow import run_inspection_pipeline
from app.schemas.inspection import (
    InspectionCreateResponse,
    InspectionDetailResponse,
    InspectionListResponse,
    InspectionResponse,
    InspectionReviewRequest,
)
from app.utils.file_utils import save_upload_file, validate_image_extension

router = APIRouter(prefix="/inspections", tags=["inspections"])

UPLOAD_DIR = "data/inspection_uploads"
MAX_IMAGES_PER_INSPECTION = 6
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def _generate_case_number() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"CASE-{stamp}-{uuid.uuid4().hex[:6].upper()}"


async def _run_pipeline_background(inspection_id: UUID) -> None:
    """
    Owns its own DB session. Request-scoped session is closed before
    background task runs — reusing it causes silent failures.
    """
    async with AsyncSessionLocal() as session:
        try:
            await run_inspection_pipeline(inspection_id=inspection_id, db=session)
        except Exception as exc:
            result = await session.execute(select(Inspection).where(Inspection.id == inspection_id))
            inspection = result.scalar_one_or_none()
            if inspection is not None:
                inspection.status = InspectionStatus.FAILED
                inspection.error_message = str(exc)[:2000]
                inspection.updated_at = datetime.now(timezone.utc)
                await session.commit()
            raise


@router.post("", response_model=InspectionCreateResponse, status_code=http_status.HTTP_201_CREATED)
@router.post("/", response_model=InspectionCreateResponse, status_code=http_status.HTTP_201_CREATED, include_in_schema=False)
async def create_inspection(
    background_tasks: BackgroundTasks,
    vendor_id: UUID = Form(...),
    location: str = Form(...),
    product_type: str = Form("motherboard"),
    part_code: Optional[str] = Form(None),
    images: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InspectionCreateResponse:
    if not images:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "At least one image required")
    if len(images) > MAX_IMAGES_PER_INSPECTION:
        raise HTTPException(
            http_status.HTTP_400_BAD_REQUEST,
            f"Max {MAX_IMAGES_PER_INSPECTION} images per inspection",
        )

    vendor_result = await db.execute(select(Vendor).where(Vendor.id == vendor_id))
    vendor = vendor_result.scalar_one_or_none()
    if vendor is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Vendor not found")

    for image in images:
        if not validate_image_extension(image.filename, ALLOWED_EXTENSIONS):
            raise HTTPException(
                http_status.HTTP_400_BAD_REQUEST,
                f"Unsupported file type: {image.filename}. Allowed: {ALLOWED_EXTENSIONS}",
            )

    inspection_id = uuid.uuid4()
    inspection_dir = os.path.join(UPLOAD_DIR, str(inspection_id))
    os.makedirs(inspection_dir, exist_ok=True)

    saved_paths: list[str] = []
    try:
        for image in images:
            saved_path = await save_upload_file(image, inspection_dir)
            saved_paths.append(saved_path)
    except Exception as exc:
        raise HTTPException(http_status.HTTP_500_INTERNAL_SERVER_ERROR, f"Image save failed: {exc}") from exc

    inspection = Inspection(
        id=inspection_id,
        case_number=_generate_case_number(),
        vendor_id=vendor_id,
        location=location,
        image_paths=saved_paths,
        image_count=len(saved_paths),
        status=InspectionStatus.PENDING,
        created_by=current_user.id,
        working_memory={
            "product_type": product_type.lower().strip(),
            "part_code": part_code.strip() if part_code else None,
        },
    )
    db.add(inspection)
    await db.commit()
    await db.refresh(inspection)

    background_tasks.add_task(_run_pipeline_background, inspection.id)

    return InspectionCreateResponse(
        id=inspection.id,
        case_number=inspection.case_number,
        status=inspection.status,
        message="Inspection created. Pipeline running in background.",
    )


@router.get("", response_model=InspectionListResponse)
@router.get("/", response_model=InspectionListResponse, include_in_schema=False)
async def list_inspections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    vendor_id: Optional[UUID] = None,
    status_filter: Optional[InspectionStatus] = None,
    page: int = 1,
    page_size: int = 20,
) -> InspectionListResponse:
    if page < 1 or page_size < 1 or page_size > 100:
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Invalid pagination params")

    query = select(Inspection).options(
        selectinload(Inspection.vendor),
        selectinload(Inspection.golden_reference),
    )
    if vendor_id is not None:
        query = query.where(Inspection.vendor_id == vendor_id)
    if status_filter is not None:
        query = query.where(Inspection.status == status_filter)

    query = query.order_by(Inspection.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    inspections = result.scalars().all()

    return InspectionListResponse(
        items=[InspectionResponse.model_validate(i) for i in inspections],
        page=page,
        page_size=page_size,
    )


@router.get("/{inspection_id}", response_model=InspectionDetailResponse)
async def get_inspection(
    inspection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InspectionDetailResponse:
    result = await db.execute(
        select(Inspection)
        .options(
            selectinload(Inspection.vendor),
            selectinload(Inspection.golden_reference),
            selectinload(Inspection.evidence_records),
        )
        .where(Inspection.id == inspection_id)
    )
    inspection = result.scalar_one_or_none()
    if inspection is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Inspection not found")
    return InspectionDetailResponse.model_validate(inspection)


@router.get("/{inspection_id}/status")
async def get_inspection_status(
    inspection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Lightweight polling endpoint returning real-time or completed stage progress."""
    state = await inspection_state_registry.get(inspection_id)
    if state is not None:
        return state.progress()

    result = await db.execute(select(Inspection).where(Inspection.id == inspection_id))
    inspection = result.scalar_one_or_none()
    if inspection is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Inspection not found")

    is_done = inspection.status == InspectionStatus.COMPLETED
    is_failed = inspection.status == InspectionStatus.FAILED
    return {
        "stage": 8 if is_done else (1 if is_failed else 1),
        "stage_name": "policy_engine" if is_done else ("failed" if is_failed else "in_progress"),
        "status": inspection.status.value,
        "progress": 8 if is_done else 0,
        "verdict": inspection.verdict.value if inspection.verdict else None,
        "policy_action": inspection.policy_action.value if inspection.policy_action else None,
        "detail": inspection.error_message if is_failed else (inspection.root_cause if is_done else None),
    }


@router.get("/{inspection_id}/events")
async def stream_inspection_events(
    inspection_id: UUID,
):
    """
    Real-time Server-Sent Events (SSE) endpoint streaming stage progress (1/8 -> 8/8).
    Closes automatically with a 'verdict' event when the inspection completes.
    Uses independent session context to avoid closed-session dependency termination.
    """
    async def event_generator():
        sent_verdict = False
        max_checks = 120  # ~60 seconds timeout
        checks = 0

        while checks < max_checks:
            checks += 1
            state = await inspection_state_registry.get(inspection_id)
            if state is not None:
                prog = state.progress()
                yield f"data: {json.dumps(prog)}\n\n"

                if prog.get("status") in ("completed", "failed"):
                    final_payload = {
                        "event": "verdict",
                        "status": prog.get("status"),
                        "inspection_id": str(inspection_id),
                        "detail": prog.get("detail"),
                    }
                    yield f"event: verdict\ndata: {json.dumps(final_payload)}\n\n"
                    sent_verdict = True
                    break
            else:
                if AsyncSessionLocal is not None:
                    async with AsyncSessionLocal() as session:
                        result = await session.execute(select(Inspection).where(Inspection.id == inspection_id))
                        insp = result.scalar_one_or_none()
                        if insp is not None:
                            if insp.status == InspectionStatus.COMPLETED:
                                prog = {
                                    "stage": 8,
                                    "stage_name": "policy_engine",
                                    "status": "completed",
                                    "progress": 8,
                                    "verdict": insp.verdict.value if insp.verdict else None,
                                    "policy_action": insp.policy_action.value if insp.policy_action else None,
                                }
                                yield f"data: {json.dumps(prog)}\n\n"
                                yield f"event: verdict\ndata: {json.dumps(prog)}\n\n"
                                sent_verdict = True
                                break
                            elif insp.status == InspectionStatus.FAILED:
                                prog = {
                                    "stage": 1,
                                    "stage_name": "failed",
                                    "status": "failed",
                                    "progress": 0,
                                    "error": insp.error_message,
                                }
                                yield f"data: {json.dumps(prog)}\n\n"
                                yield f"event: verdict\ndata: {json.dumps(prog)}\n\n"
                                sent_verdict = True
                                break

            # Periodic keepalive ping every ~5s
            if checks % 10 == 0:
                yield ": ping\n\n"

            await asyncio.sleep(0.5)

        if not sent_verdict:
            yield f"event: error\ndata: {json.dumps({'error': 'stream_timeout'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{inspection_id}/approve", response_model=InspectionResponse)
async def approve_inspection(
    inspection_id: UUID,
    payload: InspectionReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR)),
) -> InspectionResponse:
    inspection = await _get_completed_inspection_or_404(inspection_id, db)

    return await _record_review(
        inspection,
        ReviewDecision.APPROVED,
        payload.reviewer_comment,
        None,
        current_user,
        db,
    )


@router.post("/{inspection_id}/override", response_model=InspectionResponse)
async def override_inspection(
    inspection_id: UUID,
    payload: InspectionReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR)),
) -> InspectionResponse:
    inspection = await _get_completed_inspection_or_404(inspection_id, db)
    if not (payload.reviewer_comment or "").strip():
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Override requires a reviewer comment")

    return await _record_review(
        inspection,
        ReviewDecision.OVERRIDDEN,
        payload.reviewer_comment,
        None,
        current_user,
        db,
    )


async def _get_completed_inspection_or_404(inspection_id: UUID, db: AsyncSession) -> Inspection:
    result = await db.execute(select(Inspection).where(Inspection.id == inspection_id))
    inspection = result.scalar_one_or_none()
    if inspection is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Inspection not found")
    if inspection.status != InspectionStatus.COMPLETED:
        raise HTTPException(
            http_status.HTTP_409_CONFLICT,
            f"Inspection not reviewable, status={inspection.status.value}",
        )
    return inspection


_REVIEW_DECISION_ALIASES = {
    "approved": ReviewDecision.APPROVED,
    "approve": ReviewDecision.APPROVED,
    "accept": ReviewDecision.APPROVED,
    "overridden": ReviewDecision.OVERRIDDEN,
    "override": ReviewDecision.OVERRIDDEN,
    "rejected": ReviewDecision.OVERRIDDEN,
    "reject": ReviewDecision.OVERRIDDEN,
}

_OVERRIDDEN_VERDICT_ALIASES = {
    "accept": InspectionVerdict.ACCEPT,
    "accepted": InspectionVerdict.ACCEPT,
    "genuine": InspectionVerdict.ACCEPT,
    "pass": InspectionVerdict.ACCEPT,
    "reject": InspectionVerdict.REJECT,
    "rejected": InspectionVerdict.REJECT,
    "fraud": InspectionVerdict.REJECT,
    "fail": InspectionVerdict.REJECT,
    "review": InspectionVerdict.REVIEW,
    "manual": InspectionVerdict.REVIEW,
}


def _normalise_review_decision(raw: Optional[str]) -> Optional[ReviewDecision]:
    if raw is None:
        return None
    return _REVIEW_DECISION_ALIASES.get(str(raw).strip().lower())


def _normalise_overridden_verdict(raw: Optional[str]) -> Optional[InspectionVerdict]:
    if raw is None:
        return None
    return _OVERRIDDEN_VERDICT_ALIASES.get(str(raw).strip().lower())


async def _record_review(
    inspection: Inspection,
    decision: ReviewDecision,
    comment: Optional[str],
    verdict: Optional[InspectionVerdict],
    reviewer: User,
    db: AsyncSession,
) -> InspectionResponse:
    """Single write path for every human-review entry point."""
    inspection.review_decision = decision
    inspection.reviewed_by = reviewer.id
    inspection.reviewer_comment = comment
    inspection.reviewed_at = datetime.now(timezone.utc)
    if verdict is not None:
        inspection.verdict = verdict

    # Read the primary key before commit: expire_on_commit drops every attribute,
    # so touching inspection.id afterwards would lazy-refresh under async.
    inspection_id = inspection.id
    await db.commit()

    # Re-read with the relationships that InspectionResponse derives its display
    # fields from (vendor_name, product_type) eagerly loaded. After commit the
    # identity is expired, so validating the in-memory instance would trigger a
    # lazy load and raise MissingGreenlet under async.
    refreshed = await db.execute(
        select(Inspection)
        .where(Inspection.id == inspection_id)
        .options(
            selectinload(Inspection.vendor),
            selectinload(Inspection.golden_reference),
        )
    )
    reloaded = refreshed.scalar_one_or_none()
    if reloaded is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Inspection not found")

    return InspectionResponse.model_validate(reloaded)


@router.post("/{inspection_id}/review", response_model=InspectionResponse)
async def review_inspection(
    inspection_id: UUID,
    payload: InspectionReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR)),
) -> InspectionResponse:
    inspection = await _get_completed_inspection_or_404(inspection_id, db)

    decision = _normalise_review_decision(payload.review_decision)
    if decision is None:
        raise HTTPException(
            http_status.HTTP_400_BAD_REQUEST,
            "review_decision must be 'approved' or 'overridden'",
        )

    verdict: Optional[InspectionVerdict] = None
    if decision is ReviewDecision.OVERRIDDEN:
        verdict = _normalise_overridden_verdict(payload.overridden_verdict)
        if verdict is None:
            raise HTTPException(
                http_status.HTTP_400_BAD_REQUEST,
                "overridden_verdict must be 'accept' or 'reject' when overriding",
            )
        if not (payload.reviewer_comment or "").strip():
            raise HTTPException(
                http_status.HTTP_400_BAD_REQUEST,
                "Override requires a reviewer comment",
            )

    return await _record_review(
        inspection, decision, payload.reviewer_comment, verdict, current_user, db
    )