from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class GoldenReferenceCreate(BaseModel):
    part_id: str = Field(min_length=1, max_length=100)
    part_name: str = Field(min_length=1, max_length=255)
    view_angle: str = Field(default="front", max_length=50)
    description: Optional[str] = None


class GoldenReferenceResponse(BaseModel):
    id: uuid.UUID
    part_id: str
    part_name: str
    image_path: str
    thumbnail_path: Optional[str] = None
    embedding_id: Optional[str] = None
    roi_template_path: Optional[str] = None
    view_angle: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
