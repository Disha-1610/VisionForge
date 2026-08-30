from __future__ import annotations

from typing import TYPE_CHECKING

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.inspection import Inspection


class AgentType(str, enum.Enum):
    OCR = "ocr"
    LABEL = "label"
    STRUCTURAL = "structural"
    VLM = "vlm"


class Evidence(Base):
    """Append-only evidence record. Never update — insert new rows only."""

    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inspections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_type: Mapped[AgentType] = mapped_column(
        Enum(AgentType, name="agent_type"), nullable=False, index=True
    )
    detector_name: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    roi_id: Mapped[str] = mapped_column(String(100), nullable=False)
    roi_type: Mapped[str] = mapped_column(String(50), nullable=False)
    bounding_box: Mapped[dict] = mapped_column(JSONB, nullable=False)  # {x, y, w, h}

    # YOLO-specific structured findings (null for non-structural agents)
    detected_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    component_findings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    evidence_summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    explanation: Mapped[str] = mapped_column(String(2000), nullable=False)
    raw_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    processing_time_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    failed: Mapped[bool] = mapped_column(default=False, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    inspection: Mapped["Inspection"] = relationship("Inspection", back_populates="evidence_records")

    def __repr__(self) -> str:
        return f"<Evidence id={self.id} agent={self.agent_type} conf={self.confidence}>"