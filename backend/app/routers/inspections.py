import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status as http_status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal, get_db
from app.core.security import get_current_user, require_roles
from app.models.evidence import Evidence
from app.models.inspection import Inspection, InspectionStatus, InspectionVerdict, ReviewDecision
from app.models.user import User, UserRole
from app.models.vendor import Vendor
from app.pipeline.state import inspection_state_registry
from app.pipeline.workflow import run_inspection_workflow, WorkflowRunConfig
from app.schemas.inspection import (
    AgentTypeEnum,
    EvidenceItem,
    InspectionCreateResponse,
    InspectionImage,
    InspectionListItem,
    InspectionListResponse,
    InspectionResponse,
    InspectionReview,
    InspectionVerdict as VerdictSchema,
    InspectionVerdictEnum,
    PipelineStageEvent,
    PipelineStageStatusEnum,
    PipelineStatusEnum,
    PipelineStatusResponse,
    PipelineVerdictEvent,
    ProductType,
    ReviewActionEnum,
    ReviewRecord,
)
from app.shared.evidence_store import evidence_store
from app.shared.memory import working_memory_registry
from app.utils.file_utils import save_upload_file, validate_image_extension

logger = logging.getLogger("visionforge.routers.inspections")

router = APIRouter(prefix="/inspections", tags=["inspections"])

UPLOAD_DIR = "data/inspection_uploads"
MAX_IMAGES_PER_INSPECTION = 6
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}

STAGE_NAME_MAP = {
    1: "quality_check",
    2: "authenticity",
    3: "reference_match",
    4: "roi_scheduler",
    5: "evidence_execution",
    6: "evidence_fusion",
    7: "judge",
    8: "policy_engine",
}


def _generate_case_number() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"CASE-{stamp}-{uuid.uuid4().hex[:6].upper()}"


async def _run_pipeline_background(
    inspection_id: UUID, vendor_id: UUID, location: str, product_type: ProductType, image_paths: list[str]
) -> None:
    """
    Background worker task executing the 8-stage pipeline.
    Uses its own DB session and initializes WorkingMemory & EvidenceStore via InspectionStateRegistry.
    """
    async with AsyncSessionLocal() as session:
        try:
            state = await inspection_state_registry.get_or_create(
                inspection_id=inspection_id, vendor_id=vendor_id, location=location
            )
            await state.memory.update(
                image_paths=image_paths,
                product_type=product_type.value,
            )

            config: WorkflowRunConfig = {
                "inspection_id": str(inspection_id),
                "product_type": product_type.value,
                "image_paths": image_paths,
            }
            await run_inspection_workflow(
                state=state.memory.to_dict() if hasattr(state.memory, "to_dict") else {},  # type: ignore
                config=config,
                working_memory=state.memory,
                evidence_store=state.evidence,
            )

            # Update DB with pipeline output snapshot
            result = await session.execute(select(Inspection).where(Inspection.id == inspection_id))
            inspection = result.scalar_one_or_none()
            if inspection:
                inspection.status = InspectionStatus.COMPLETED
                if state.memory.fraud_probability is not None:
                    inspection.fraud_probability = state.memory.fraud_probability
                if state.memory.judge_confidence is not None:
                    inspection.judge_confidence = state.memory.judge_confidence
                if state.memory.fraud_category is not None:
                    inspection.fraud_category = state.memory.fraud_category
                if state.memory.root_cause is not None:
                    inspection.root_cause = state.memory.root_cause

                # Map memory verdict to DB verdict
                last_verdict = getattr(state.memory, "verdict", None) or getattr(state.memory, "fused_verdict", None)
                if last_verdict:
                    try:
                        inspection.verdict = InspectionVerdict(str(last_verdict).lower())
                    except ValueError:
                        inspection.verdict = InspectionVerdict.REVIEW
                else:
                    inspection.verdict = InspectionVerdict.REVIEW

                inspection.updated_at = datetime.now(timezone.utc)
                await session.commit()

        except Exception as exc:
            logger.exception("Pipeline background execution failed for inspection %s", inspection_id)
            result = await session.execute(select(Inspection).where(Inspection.id == inspection_id))
            inspection = result.scalar_one_or_none()
            if inspection is not None:
                inspection.status = InspectionStatus.FAILED
                inspection.error_message = str(exc)[:2000]
                inspection.updated_at = datetime.now(timezone.utc)
                await session.commit()


def _format_inspection_response(inspection: Inspection) -> InspectionResponse:
    """Helper to convert Inspection SQLAlchemy model into InspectionResponse schema."""
    verdict_schema = None
    if inspection.verdict and inspection.verdict != InspectionVerdict.PENDING:
        try:
            verdict_enum = InspectionVerdictEnum[inspection.verdict.value.upper()]
        except KeyError:
            verdict_enum = InspectionVerdictEnum.REVIEW
        verdict_schema = VerdictSchema(
            verdict=verdict_enum,
            fraud_probability=inspection.fraud_probability or 0.0,
            confidence=inspection.judge_confidence or 0.0,
            category=inspection.fraud_category,
            root_cause=inspection.root_cause,
            recommended_action=inspection.policy_action.value if inspection.policy_action else None,
        )

    images: list[InspectionImage] = []
    if inspection.image_paths:
        for idx, path in enumerate(inspection.image_paths):
            images.append(
                InspectionImage(
                    id=uuid.uuid5(inspection.id, path),
                    image_path=path,
                    original_filename=os.path.basename(path),
                    angle=None,
                    created_at=inspection.created_at.isoformat(),
                )
            )

    evidence_items: list[EvidenceItem] = []
    if hasattr(inspection, "evidence_records") and inspection.evidence_records:
        for e in inspection.evidence_records:
            try:
                agent_enum = AgentTypeEnum[e.agent_type.value.upper()]
            except (KeyError, AttributeError):
                agent_enum = AgentTypeEnum.OCR
            evidence_items.append(
                EvidenceItem(
                    id=e.id,
                    agent_type=agent_enum,
                    roi_id=e.roi_id,
                    evidence=e.raw_output or {},
                    confidence=e.confidence,
                    explanation=e.explanation,
                    processing_time_ms=e.processing_time_ms,
                )
            )

    review_record = None
    if inspection.review_decision and inspection.review_decision != ReviewDecision.PENDING:
        action = (
            ReviewActionEnum.APPROVE
            if inspection.review_decision == ReviewDecision.APPROVED
            else ReviewActionEnum.OVERRIDE
        )
        if inspection.reviewed_by and inspection.reviewed_at:
            review_record = ReviewRecord(
                action=action,
                comment=inspection.reviewer_comment,
                reviewed_by=inspection.reviewed_by,
                reviewed_at=inspection.reviewed_at.isoformat(),
            )

    try:
        pipeline_status = PipelineStatusEnum[inspection.status.value.upper()]
    except KeyError:
        pipeline_status = PipelineStatusEnum.PENDING

    # Attempt to pull product_type from working memory or fallback to MOTHERBOARD
    p_type = ProductType.MOTHERBOARD
    if inspection.working_memory and "product_type" in inspection.working_memory:
        try:
            p_type = ProductType(inspection.working_memory["product_type"])
        except ValueError:
            pass

    return InspectionResponse(
        id=inspection.id,
        case_number=inspection.case_number,
        vendor_id=inspection.vendor_id,
        location=inspection.location,
        product_type=p_type,
        status=pipeline_status,
        verdict=verdict_schema,
        images=images,
        evidence=evidence_items,
        review=review_record,
        created_by=inspection.created_by,
        created_at=inspection.created_at.isoformat(),
        updated_at=inspection.updated_at.isoformat(),
    )


@router.post("", response_model=InspectionCreateResponse, status_code=http_status.HTTP_201_CREATED)
async def create_inspection(
    background_tasks: BackgroundTasks,
    vendor_id: UUID = Form(...),
    location: str = Form(...),
    product_type: ProductType = Form(...),
    images: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR)),
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
        working_memory={"product_type": product_type.value},
    )
    db.add(inspection)
    await db.commit()
    await db.refresh(inspection)

    background_tasks.add_task(
        _run_pipeline_background,
        inspection.id,
        vendor_id,
        location,
        product_type,
        saved_paths,
    )

    return InspectionCreateResponse(
        id=inspection.id,
        case_number=inspection.case_number,
        status=PipelineStatusEnum.PENDING,
        message="Inspection created. Pipeline running in background.",
    )


@router.get("", response_model=InspectionListResponse)
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

    base_query = select(Inspection)
    count_query = select(func.count()).select_from(Inspection)

    if vendor_id is not None:
        base_query = base_query.where(Inspection.vendor_id == vendor_id)
        count_query = count_query.where(Inspection.vendor_id == vendor_id)
    if status_filter is not None:
        base_query = base_query.where(Inspection.status == status_filter)
        count_query = count_query.where(Inspection.status == status_filter)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    query = base_query.order_by(Inspection.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    inspections = result.scalars().all()

    items: list[InspectionListItem] = []
    for i in inspections:
        try:
            status_enum = PipelineStatusEnum[i.status.value.upper()]
        except KeyError:
            status_enum = PipelineStatusEnum.PENDING

        verdict_enum = None
        if i.verdict and i.verdict != InspectionVerdict.PENDING:
            try:
                verdict_enum = InspectionVerdictEnum[i.verdict.value.upper()]
            except KeyError:
                verdict_enum = InspectionVerdictEnum.REVIEW

        p_type = ProductType.MOTHERBOARD
        if i.working_memory and "product_type" in i.working_memory:
            try:
                p_type = ProductType(i.working_memory["product_type"])
            except ValueError:
                pass

        items.append(
            InspectionListItem(
                id=i.id,
                case_number=i.case_number,
                vendor_id=i.vendor_id,
                location=i.location,
                product_type=p_type,
                status=status_enum,
                verdict=verdict_enum,
                fraud_probability=i.fraud_probability,
                created_at=i.created_at.isoformat(),
            )
        )

    return InspectionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{inspection_id}", response_model=InspectionResponse)
async def get_inspection(
    inspection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InspectionResponse:
    result = await db.execute(
        select(Inspection)
        .options(selectinload(Inspection.evidence_records))
        .where(Inspection.id == inspection_id)
    )
    inspection = result.scalar_one_or_none()
    if inspection is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Inspection not found")
    return _format_inspection_response(inspection)


@router.get("/{inspection_id}/status", response_model=PipelineStatusResponse)
async def get_inspection_status(
    inspection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PipelineStatusResponse:
    result = await db.execute(select(Inspection).where(Inspection.id == inspection_id))
    inspection = result.scalar_one_or_none()
    if inspection is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Inspection not found")

    state = await inspection_state_registry.get(inspection_id)
    if state is not None:
        prog = state.progress()
        verdict_schema = None
        if state.memory.fraud_probability is not None or state.memory.fraud_category is not None:
            verdict_val = InspectionVerdictEnum.REVIEW
            if inspection.verdict and inspection.verdict != InspectionVerdict.PENDING:
                try:
                    verdict_val = InspectionVerdictEnum[inspection.verdict.value.upper()]
                except KeyError:
                    pass
            verdict_schema = VerdictSchema(
                verdict=verdict_val,
                fraud_probability=state.memory.fraud_probability or 0.0,
                confidence=state.memory.judge_confidence or 0.0,
                category=state.memory.fraud_category,
                root_cause=state.memory.root_cause,
                recommended_action=state.memory.policy_action,
            )
        try:
            status_enum = PipelineStatusEnum[prog["status"].upper()]
        except KeyError:
            status_enum = PipelineStatusEnum.PROCESSING

        return PipelineStatusResponse(
            inspection_id=inspection_id,
            status=status_enum,
            current_stage=prog.get("stage"),
            current_stage_name=prog.get("stage_name"),
            progress=prog.get("progress", 0),
            detail=json.dumps(prog.get("detail")) if prog.get("detail") is not None else None,
            verdict=verdict_schema,
        )

    # Fallback to DB state if memory state is unavailable
    verdict_schema = None
    if inspection.verdict and inspection.verdict != InspectionVerdict.PENDING:
        try:
            verdict_enum = InspectionVerdictEnum[inspection.verdict.value.upper()]
        except KeyError:
            verdict_enum = InspectionVerdictEnum.REVIEW
        verdict_schema = VerdictSchema(
            verdict=verdict_enum,
            fraud_probability=inspection.fraud_probability or 0.0,
            confidence=inspection.judge_confidence or 0.0,
            category=inspection.fraud_category,
            root_cause=inspection.root_cause,
            recommended_action=inspection.policy_action.value if inspection.policy_action else None,
        )

    try:
        status_enum = PipelineStatusEnum[inspection.status.value.upper()]
    except KeyError:
        status_enum = PipelineStatusEnum.COMPLETED

    return PipelineStatusResponse(
        inspection_id=inspection_id,
        status=status_enum,
        current_stage=8 if inspection.status == InspectionStatus.COMPLETED else None,
        current_stage_name="policy_engine" if inspection.status == InspectionStatus.COMPLETED else None,
        progress=8 if inspection.status == InspectionStatus.COMPLETED else 0,
        detail=inspection.error_message,
        verdict=verdict_schema,
    )


@router.get("/{inspection_id}/events")
async def stream_inspection_events(
    inspection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    result = await db.execute(select(Inspection).where(Inspection.id == inspection_id))
    inspection = result.scalar_one_or_none()
    if inspection is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Inspection not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        state = await inspection_state_registry.get(inspection_id)
        if state is None:
            # Yield final event if already completed
            if inspection.status == InspectionStatus.COMPLETED:
                verdict_val = InspectionVerdictEnum.ACCEPT
                if inspection.verdict and inspection.verdict != InspectionVerdict.PENDING:
                    try:
                        verdict_val = InspectionVerdictEnum[inspection.verdict.value.upper()]
                    except KeyError:
                        verdict_val = InspectionVerdictEnum.REVIEW

                v_event = PipelineVerdictEvent(
                    verdict=verdict_val,
                    fraud_probability=inspection.fraud_probability or 0.0,
                    confidence=inspection.judge_confidence or 0.0,
                    category=inspection.fraud_category or "NONE",
                )
                yield f"event: verdict\ndata: {v_event.model_dump_json()}\n\n"
            return

        last_stage = 0
        while True:
            prog = state.progress()
            stage_num = prog.get("stage", 1)
            stage_name = prog.get("stage_name", STAGE_NAME_MAP.get(stage_num, "quality_check"))
            prog_status = prog.get("status", "in_progress")

            try:
                stage_status_enum = PipelineStageStatusEnum[prog_status.upper()]
            except KeyError:
                stage_status_enum = PipelineStageStatusEnum.STARTED

            detail_str = json.dumps(prog.get("detail")) if prog.get("detail") is not None else ""

            if stage_num != last_stage or prog_status in ("completed", "failed"):
                event_data = PipelineStageEvent(
                    stage=stage_num,
                    stage_name=stage_name,
                    status=stage_status_enum,
                    progress=prog.get("progress", stage_num),
                    detail=detail_str,
                )
                yield f"event: stage_progress\ndata: {event_data.model_dump_json()}\n\n"
                last_stage = stage_num

            if prog_status in ("completed", "failed"):
                if state.memory.fraud_probability is not None:
                    verdict_val = InspectionVerdictEnum.ACCEPT
                    if inspection.verdict and inspection.verdict != InspectionVerdict.PENDING:
                        try:
                            verdict_val = InspectionVerdictEnum[inspection.verdict.value.upper()]
                        except KeyError:
                            verdict_val = InspectionVerdictEnum.REVIEW

                    v_event = PipelineVerdictEvent(
                        verdict=verdict_val,
                        fraud_probability=state.memory.fraud_probability or 0.0,
                        confidence=state.memory.judge_confidence or 0.0,
                        category=state.memory.fraud_category or "NONE",
                    )
                    yield f"event: verdict\ndata: {v_event.model_dump_json()}\n\n"
                break

            import asyncio
            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{inspection_id}/review", response_model=InspectionResponse)
async def review_inspection(
    inspection_id: UUID,
    review: InspectionReview,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR)),
) -> InspectionResponse:
    result = await db.execute(
        select(Inspection)
        .options(selectinload(Inspection.evidence_records))
        .where(Inspection.id == inspection_id)
    )
    inspection = result.scalar_one_or_none()
    if inspection is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Inspection not found")
    if inspection.status != InspectionStatus.COMPLETED:
        raise HTTPException(
            http_status.HTTP_409_CONFLICT,
            f"Inspection not reviewable, status={inspection.status.value}",
        )

    if review.action == ReviewActionEnum.OVERRIDE:
        if not review.comment or not review.comment.strip():
            raise HTTPException(
                http_status.HTTP_400_BAD_REQUEST,
                "Override requires a reviewer comment",
            )
        inspection.review_decision = ReviewDecision.OVERRIDDEN
    else:
        inspection.review_decision = ReviewDecision.APPROVED

    inspection.reviewed_by = current_user.id
    inspection.reviewer_comment = review.comment
    inspection.reviewed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(inspection)
    return _format_inspection_response(inspection)