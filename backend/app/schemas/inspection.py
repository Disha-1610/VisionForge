from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Evidence Schemas ──────────────────────────────────────────────────────────

class EvidenceResponse(BaseModel):
    id: uuid.UUID
    agent_type: str
    detector_name: str
    confidence: float
    roi_id: str
    roi_type: str
    bounding_box: dict
    detected_count: Optional[int] = None
    expected_count: Optional[int] = None
    component_findings: Optional[dict] = None
    evidence_summary: str
    explanation: str
    processing_time_ms: int
    failed: bool
    failure_reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Request Schemas ───────────────────────────────────────────────────────────

class InspectionCreate(BaseModel):
    vendor_id: uuid.UUID
    location: str = Field(min_length=1, max_length=255)


class InspectionUpdate(BaseModel):
    review_decision: Optional[str] = None
    reviewer_comment: Optional[str] = None


# ── Response Schemas ──────────────────────────────────────────────────────────

class InspectionResponse(BaseModel):
    id: uuid.UUID
    case_number: str
    vendor_id: uuid.UUID
    location: str
    golden_reference_id: Optional[uuid.UUID] = None
    image_paths: list[str]
    image_count: int
    quality_passed: bool
    quality_failure_reason: Optional[str] = None
    authenticity_score: Optional[float] = None
    authenticity_flagged: bool
    reference_similarity: Optional[float] = None
    fraud_probability: Optional[float] = None
    judge_confidence: Optional[float] = None
    fraud_category: Optional[str] = None
    root_cause: Optional[str] = None
    verdict: str
    policy_action: Optional[str] = None
    report_path: Optional[str] = None
    review_decision: str
    reviewer_comment: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InspectionDetailResponse(InspectionResponse):
    evidence_records: list[EvidenceResponse] = []
