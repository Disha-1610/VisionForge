from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.product import GoldenReference
from app.models.user import User
from app.schemas.product import GoldenReferenceCreate, GoldenReferenceResponse

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("/", response_model=list[GoldenReferenceResponse])
async def list_golden_references(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(GoldenReference).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/{reference_id}", response_model=GoldenReferenceResponse)
async def get_golden_reference(
    reference_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(GoldenReference).where(GoldenReference.id == reference_id)
    )
    ref = result.scalar_one_or_none()
    if ref is None:
        raise HTTPException(status_code=404, detail="Golden reference not found")
    return ref


@router.post("/", response_model=GoldenReferenceResponse, status_code=status.HTTP_201_CREATED)
async def create_golden_reference(
    body: GoldenReferenceCreate,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    ref = GoldenReference(
        part_id=body.part_id,
        part_name=body.part_name,
        view_angle=body.view_angle,
        description=body.description,
        image_path="pending_upload",
    )
    db.add(ref)
    await db.flush()
    await db.refresh(ref)
    return ref


@router.delete("/{reference_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_golden_reference(
    reference_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(GoldenReference).where(GoldenReference.id == reference_id)
    )
    ref = result.scalar_one_or_none()
    if ref is None:
        raise HTTPException(status_code=404, detail="Golden reference not found")
    await db.delete(ref)
