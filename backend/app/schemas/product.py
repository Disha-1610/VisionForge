from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GoldenReferenceBase(BaseModel):
    part_id: str = Field(..., min_length=1, max_length=100)
    part_name: str = Field(..., min_length=1, max_length=255)
    vendor_id: Optional[UUID] = None
    view_angle: str = Field(..., min_length=1, max_length=50)
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
    thumbnail_path: Optional[str] = None
    roi_template_path: Optional[str] = None
    embedding_id: Optional[str] = Field(
        default=None,
        description="ID of this reference's embedding in the FAISS index",
    )
    part_code: Optional[str] = None
    product_type: Optional[str] = None
    meta: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="before")
    @classmethod
    def populate_aliases(cls, data: Any) -> Any:
        if hasattr(data, "__dict__"):
            part_id = getattr(data, "part_id", None)
            meta = getattr(data, "meta", None) or {}
            if not getattr(data, "part_code", None) and part_id:
                try:
                    setattr(data, "part_code", part_id)
                except Exception:
                    pass
            if not getattr(data, "product_type", None) and isinstance(meta, dict):
                try:
                    setattr(data, "product_type", meta.get("product_type", "hardware"))
                except Exception:
                    pass
        elif isinstance(data, dict):
            if "part_code" not in data and "part_id" in data:
                data["part_code"] = data["part_id"]
            if "product_type" not in data:
                meta = data.get("meta") or {}
                if isinstance(meta, dict):
                    data["product_type"] = meta.get("product_type", "hardware")
        return data


# Routers reference this name — same schema, kept as an alias.
GoldenReferenceResponse = ProductResponse


class ProductListResponse(BaseModel):
    total: int
    items: list[ProductResponse]