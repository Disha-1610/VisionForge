from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VerdictEnum(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    REVIEW = "review"


class PolicyActionEnum(str, Enum):
    ACCEPT = "accept"
    RETAKE = "retake"
    QUARANTINE = "quarantine"
    VENDOR_VERIFICATION = "vendor_verification"


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float
    label: Optional[str] = None


class AgentEvidenceItem(BaseModel):
    agent_name: str = Field(..., description="ocr | label | structural | vlm")
    confidence: float = Field(..., ge=0.0, le=1.0)
    roi: str
    explanation: str
    processing_time_ms: float
    bounding_boxes: list[BoundingBox] = Field(default_factory=list)
    expected_component_count: Optional[int] = None
    detected_component_count: Optional[int] = None


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    case_id: str
    inspection_id: UUID

    vendor_id: UUID
    vendor_name: str
    location: str

    part_id: str
    golden_image_path: str
    inspection_image_paths: list[str]

    authenticity_score: float = Field(..., ge=0.0, le=1.0)
    authenticity_flagged: bool

    fraud_score: float = Field(..., ge=0.0, le=100.0)
    confidence_score: float = Field(..., ge=0.0, le=100.0)
    fraud_category: Optional[str] = None

    verdict: VerdictEnum
    root_cause_explanation: str
    policy_action: PolicyActionEnum

    evidence: list[AgentEvidenceItem]

    reviewer_id: Optional[UUID] = None
    reviewer_comment: Optional[str] = None
    is_overridden: bool = False

    report_pdf_path: Optional[str] = None

    created_at: datetime
    updated_at: datetime


class ReportListResponse(BaseModel):
    total: int
    items: list[ReportResponse]