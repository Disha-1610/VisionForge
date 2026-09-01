# backend/app/models/report.py
"""SQLAlchemy model for PDF Inspection Reports persistence."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Float, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    case_id: Mapped[str] = mapped_column(String(255), nullable=False)
    pdf_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    verdict: Mapped[str] = mapped_column(String(64), nullable=False)
    fraud_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fraud_category: Mapped[str] = mapped_column(String(128), nullable=True)
    recommended_action: Mapped[str] = mapped_column(String(255), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
