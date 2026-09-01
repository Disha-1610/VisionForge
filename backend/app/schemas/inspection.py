from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class ProductType(str, enum.Enum):
    MOTHERBOARD = "MOTHERBOARD"
    BATTERY = "BATTERY"
    RAM = "RAM"


class InspectionVerdictEnum(str, enum.Enum):
    ACCEPT = "ACCEPT"
    REJECT = "REJECT"
    REVIEW = "REVIEW"


class ReviewActionEnum(str, enum.Enum):
    APPROVE = "APPROVE"
    OVERRIDE = "OVERRIDE"


class PipelineStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PipelineStageStatusEnum(str, enum.Enum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgentTypeEnum(str, enum.Enum):
    OCR = "OCR"
    LABEL = "LABEL"
    STRUCTURAL = "STRUCTURAL"
    VLM = "VLM"


# ── Request Models ────────────────────────────────────────────────────────────

class InspectionUpdate(BaseModel):
    status: Optional[PipelineStatusEnum] = None


class InspectionReview(BaseModel):
    action: ReviewActionEnum
    comment: Optional[str] = None


# Legacy request schema alias for backwards compatibility if needed
class InspectionReviewRequest(BaseModel):
    action: Optional[ReviewActionEnum] = None
    review_decision: Optional[str] = None
    reviewer_comment: Optional[str] = None

    @property
    def parsed_action(self) -> ReviewActionEnum:
        if self.action:
            return self.action
        if self.review_decision:
            val = self.review_decision.upper()
            if val in ("APPROVED", "APPROVE"):
                return ReviewActionEnum.APPROVE
            if val in ("OVERRIDDEN", "OVERRIDE"):
                return ReviewActionEnum.OVERRIDE
        raise ValueError("Invalid review action")


# ── Response Data Models ──────────────────────────────────────────────────────

class InspectionImage(BaseModel):
    id: uuid.UUID
    image_path: str
    original_filename: str
    angle: Optional[str] = None
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class EvidenceItem(BaseModel):
    id: uuid.UUID
    agent_type: AgentTypeEnum
    roi_id: str
    evidence: dict[str, Any]
    confidence: float
    explanation: str
    processing_time_ms: int

    model_config = ConfigDict(from_attributes=True)


class InspectionVerdict(BaseModel):
    verdict: InspectionVerdictEnum
    fraud_probability: float
    confidence: float
    category: Optional[str] = None
    root_cause: Optional[str] = None
    recommended_action: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ReviewRecord(BaseModel):
    action: ReviewActionEnum
    comment: Optional[str] = None
    reviewed_by: uuid.UUID
    reviewed_at: str

    model_config = ConfigDict(from_attributes=True)


class InspectionResponse(BaseModel):
    id: uuid.UUID
    case_number: str
    vendor_id: uuid.UUID
    location: str
    product_type: ProductType
    status: PipelineStatusEnum
    verdict: Optional[InspectionVerdict] = None
    images: list[InspectionImage] = []
    evidence: list[EvidenceItem] = []
    review: Optional[ReviewRecord] = None
    created_by: uuid.UUID
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


class InspectionListItem(BaseModel):
    id: uuid.UUID
    case_number: str
    vendor_id: uuid.UUID
    location: str
    product_type: ProductType
    status: PipelineStatusEnum
    verdict: Optional[InspectionVerdictEnum] = None
    fraud_probability: Optional[float] = None
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class InspectionListResponse(BaseModel):
    items: list[InspectionListItem]
    total: int
    page: int
    page_size: int


class InspectionCreateResponse(BaseModel):
    id: uuid.UUID
    case_number: str
    status: PipelineStatusEnum
    message: str


# ── SSE / Pipeline-Progress Models ──────────────────────────────────────────

class PipelineStageEvent(BaseModel):
    stage: int  # 1-8
    stage_name: str
    status: PipelineStageStatusEnum
    progress: int  # 1-8
    detail: str


class PipelineVerdictEvent(BaseModel):
    verdict: InspectionVerdictEnum
    fraud_probability: float
    confidence: float
    category: str


class PipelineStatusResponse(BaseModel):
    inspection_id: uuid.UUID
    status: PipelineStatusEnum
    current_stage: Optional[int] = None
    current_stage_name: Optional[str] = None
    progress: int
    detail: Optional[str] = None
    verdict: Optional[InspectionVerdict] = None

