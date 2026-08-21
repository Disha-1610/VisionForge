from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VendorBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    site_name: str = Field(..., min_length=1, max_length=255)
    code: str = Field(..., min_length=1, max_length=50)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("code cannot be empty")
        return v

    @field_validator("name", "site_name")
    @classmethod
    def strip_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("field cannot be empty")
        return v


class VendorCreate(VendorBase):
    pass


class VendorUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    site_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    is_active: Optional[bool] = None


class VendorResponse(VendorBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class VendorDropdown(BaseModel):
    """Minimal shape for GET /vendors dropdown consumption on New Inspection page."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    site_name: str
    code: str


class VendorListResponse(BaseModel):
    total: int
    items: list[VendorResponse]