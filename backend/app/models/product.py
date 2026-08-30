# backend/app/models/product.py
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class GoldenReference(Base):
    __tablename__ = "golden_references"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    part_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    part_name: Mapped[str] = mapped_column(String(255), nullable=False)
    image_path: Mapped[str] = mapped_column(String(512), nullable=False)
    thumbnail_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    embedding_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    roi_template_path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    view_angle: Mapped[str] = mapped_column(String(50), nullable=False, default="front")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<GoldenReference id={self.id} part_id={self.part_id}>"