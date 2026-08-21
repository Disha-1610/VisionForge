import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status as http_status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, get_db
from app.core.security import get_current_user
from app.models.inspection import Inspection, InspectionStatus, ReviewDecision
from app.models.user import User
from app.models.vendor import Vendor
from app.pipeline.workflow import run_inspection_pipeline
from app.schemas.inspection import (
    InspectionCreateResponse,
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
async def create_inspection(
    background_tasks: BackgroundTasks,
    vendor_id: UUID = Form(...),
    location: str = Form(...),
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

    query = select(Inspection)
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


@router.get("/{inspection_id}", response_model=InspectionResponse)
async def get_inspection(
    inspection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InspectionResponse:
    result = await db.execute(select(Inspection).where(Inspection.id == inspection_id))
    inspection = result.scalar_one_or_none()
    if inspection is None:
        raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Inspection not found")
    return InspectionResponse.model_validate(inspection)


@router.post("/{inspection_id}/approve", response_model=InspectionResponse)
async def approve_inspection(
    inspection_id: UUID,
    payload: InspectionReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InspectionResponse:
    inspection = await _get_completed_inspection_or_404(inspection_id, db)

    inspection.review_decision = ReviewDecision.APPROVED
    inspection.reviewed_by = current_user.id
    inspection.reviewer_comment = payload.comment
    inspection.reviewed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(inspection)
    return InspectionResponse.model_validate(inspection)


@router.post("/{inspection_id}/override", response_model=InspectionResponse)
async def override_inspection(
    inspection_id: UUID,
    payload: InspectionReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InspectionResponse:
    if current_user.role not in ("admin", "reviewer"):
        raise HTTPException(http_status.HTTP_403_FORBIDDEN, "Insufficient role for override")

    inspection = await _get_completed_inspection_or_404(inspection_id, db)
    if not payload.comment or not payload.comment.strip():
        raise HTTPException(http_status.HTTP_400_BAD_REQUEST, "Override requires a reviewer comment")

    inspection.review_decision = ReviewDecision.OVERRIDDEN
    inspection.reviewed_by = current_user.id
    inspection.reviewer_comment = payload.comment
    inspection.reviewed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(inspection)
    return InspectionResponse.model_validate(inspection)


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