from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GoldenReferenceBase(BaseModel):
    part_id: str = Field(..., min_length=1, max_length=100)
    part_name: str = Field(..., min_length=1, max_length=255)
    vendor_id: UUID
    viewing_angle: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("part_id")
    @classmethod
    def normalize_part_id(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("part_id cannot be empty")
        return v


class GoldenReferenceCreate(GoldenReferenceBase):
    image_path: str = Field(..., min_length=1, max_length=1024)
    roi_template_path: Optional[str] = Field(default=None, max_length=1024)


class GoldenReferenceUpdate(BaseModel):
    part_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    roi_template_path: Optional[str] = Field(default=None, max_length=1024)
    is_active: Optional[bool] = None


class ProductResponse(GoldenReferenceBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    image_path: str
    roi_template_path: Optional[str] = None
    faiss_index_id: Optional[int] = Field(
        default=None,
        description="Position of this reference's embedding in the FAISS index",
    )
    embedding_generated: bool = False
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    total: int
    items: list[ProductResponse]