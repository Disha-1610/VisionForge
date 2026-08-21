from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class VendorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    site_name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=50)


class VendorUpdate(BaseModel):
    name: str | None = None
    site_name: str | None = None
    code: str | None = None


class VendorResponse(BaseModel):
    id: uuid.UUID
    name: str
    site_name: str
    code: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VendorDropdown(BaseModel):
    id: uuid.UUID
    name: str
    site_name: str
    code: str

    model_config = {"from_attributes": True}
