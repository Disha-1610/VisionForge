from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InspectionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class InspectionVerdict(str, enum.Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    REVIEW = "review"
    PENDING = "pending"


class PolicyAction(str, enum.Enum):
    ACCEPT = "accept"
    RETAKE = "retake"
    QUARANTINE = "quarantine"
    VENDOR_VERIFICATION = "vendor_verification"


class ReviewDecision(str, enum.Enum):
    APPROVED = "approved"
    OVERRIDDEN = "overridden"
    PENDING = "pending"


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    case_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)

    vendor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    location: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    golden_reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("golden_references.id", ondelete="SET NULL"), nullable=True
    )

    image_paths: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False)
    image_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Pipeline lifecycle status (separate from business verdict)
    status: Mapped[InspectionStatus] = mapped_column(
        Enum(InspectionStatus, name="inspection_status"),
        default=InspectionStatus.PENDING,
        nullable=False,
        index=True,
    )
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    # Stage 1-2 results
    quality_passed: Mapped[bool] = mapped_column(default=False, nullable=False)
    quality_failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    authenticity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    authenticity_flagged: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Stage 3 result
    reference_similarity: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Stage 6-7 fused output
    fraud_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    judge_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    fraud_category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    root_cause: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    verdict: Mapped[InspectionVerdict] = mapped_column(
        Enum(InspectionVerdict, name="inspection_verdict"),
        default=InspectionVerdict.PENDING,
        nullable=False,
        index=True,
    )

    # Stage 8 policy output
    policy_action: Mapped[PolicyAction | None] = mapped_column(
        Enum(PolicyAction, name="policy_action"), nullable=True, index=True
    )
    report_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Human review
    review_decision: Mapped[ReviewDecision] = mapped_column(
        Enum(ReviewDecision, name="review_decision"),
        default=ReviewDecision.PENDING,
        nullable=False,
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewer_comment: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    working_memory: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="inspections")
    golden_reference: Mapped["GoldenReference | None"] = relationship("GoldenReference")
    evidence_records: Mapped[list["Evidence"]] = relationship(
        "Evidence", back_populates="inspection", cascade="all, delete-orphan"
    )
    created_by_user: Mapped["User"] = relationship(
        "User", back_populates="inspections", foreign_keys=[created_by]
    )
    reviewed_by_user: Mapped["User | None"] = relationship(
        "User", back_populates="reviews", foreign_keys=[reviewed_by]
    )

    def __repr__(self) -> str:
        return f"<Inspection id={self.id} case={self.case_number} status={self.status} verdict={self.verdict}>"