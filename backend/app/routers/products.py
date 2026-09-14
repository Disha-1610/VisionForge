from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.product import GoldenReference
from app.models.user import UserRole
from app.schemas.product import GoldenReferenceCreate, GoldenReferenceResponse
from app.services.embedding_service import embedding_service
from app.utils.file_utils import validate_image_extension

settings = get_settings()

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=list[GoldenReferenceResponse])
@router.get("/", response_model=list[GoldenReferenceResponse], include_in_schema=False)
async def list_golden_references(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    result = await db.execute(
        select(GoldenReference).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/{reference_id}", response_model=GoldenReferenceResponse)
async def get_golden_reference(
    reference_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(get_current_user),
):
    result = await db.execute(
        select(GoldenReference).where(GoldenReference.id == reference_id)
    )
    ref = result.scalar_one_or_none()
    if ref is None:
        raise HTTPException(status_code=404, detail="Golden reference not found")
    return ref


@router.post("/upload", response_model=GoldenReferenceResponse, status_code=status.HTTP_201_CREATED)
async def upload_golden_reference(
    image: UploadFile = File(...),
    product_type: str = Form(...),
    part_name: str = Form(...),
    part_code: str = Form(...),
    view_angle: str = Form("front"),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_roles(UserRole.ADMIN)),
):
    """Upload and index a golden reference image into FAISS and database."""
    allowed_exts = {".jpg", ".jpeg", ".png", ".webp"}
    if not validate_image_extension(image.filename, allowed_exts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported image file: {image.filename}. Allowed: {allowed_exts}",
        )

    ref_id = uuid.uuid4()
    golden_dir = Path(settings.GOLDEN_IMAGE_DIR)
    golden_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(image.filename).suffix.lower() or ".jpg"
    clean_code = part_code.strip().upper()
    dest_filename = f"{clean_code.lower().replace('-', '_')}_{ref_id.hex[:8]}{ext}"
    dest_path = golden_dir / dest_filename

    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    # Compute embedding and insert into FAISS index
    try:
        pil_img = Image.open(dest_path).convert("RGB")
        embedding, provider = embedding_service.generate_embedding_for_index(pil_img)
        embedding_service.add_to_index(embedding, str(ref_id), provider=provider)
        embedding_service.save_index(settings.FAISS_INDEX_PATH)
    except Exception as exc:
        if dest_path.exists():
            dest_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate embedding or index image: {exc}",
        )

    # Check for matching ROI template
    template_name = f"{product_type.strip().lower()}_{clean_code.lower().replace('-', '_')}.json"
    template_file = Path(settings.ROI_TEMPLATE_DIR) / template_name
    roi_path = str(template_file) if template_file.exists() else None

    ref = GoldenReference(
        id=ref_id,
        part_id=clean_code,
        part_name=part_name.strip(),
        image_path=str(dest_path),
        view_angle=view_angle,
        description=description or f"{product_type.capitalize()} standard reference",
        embedding_id=str(ref_id),
        roi_template_path=roi_path,
        meta={"product_type": product_type.strip().lower()},
    )
    db.add(ref)
    await db.commit()
    await db.refresh(ref)
    return ref


@router.post("", response_model=GoldenReferenceResponse, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=GoldenReferenceResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_golden_reference(
    body: GoldenReferenceCreate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_roles(UserRole.ADMIN)),
):
    ref = GoldenReference(
        part_id=body.part_id,
        part_name=body.part_name,
        view_angle=body.view_angle,
        description=body.description,
        image_path=body.image_path,
    )
    db.add(ref)
    await db.commit()
    await db.refresh(ref)
    return ref


@router.delete("/{reference_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_golden_reference(
    reference_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_roles(UserRole.ADMIN)),
):
    result = await db.execute(
        select(GoldenReference).where(GoldenReference.id == reference_id)
    )
    ref = result.scalar_one_or_none()
    if ref is None:
        raise HTTPException(status_code=404, detail="Golden reference not found")

    # Remove from FAISS index if present
    try:
        embedding_service.remove_from_index(str(reference_id))
        embedding_service.save_index(settings.FAISS_INDEX_PATH)
    except Exception:
        pass

    await db.delete(ref)
    await db.commit()
