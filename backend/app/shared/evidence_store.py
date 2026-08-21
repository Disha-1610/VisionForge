# backend/app/shared/evidence_store.py
from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentType(str, Enum):
    OCR = "ocr"
    LABEL = "label"
    STRUCTURAL = "structural"
    VLM = "vlm"


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    inspection_id: uuid.UUID
    agent_type: AgentType
    roi_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: dict[str, Any]
    explanation: str
    processing_time_ms: float
    bounding_box: list[float] | None = None
    failed: bool = False
    failure_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    sequence: int


class EvidenceStoreError(Exception):
    pass


class EvidenceImmutableError(EvidenceStoreError):
    pass


class EvidenceNotFoundError(EvidenceStoreError):
    pass


class EvidenceStore:
    """
    Append-only evidence store, keyed by inspection_id.
    No update/delete API exists — evidence records are immutable once written.
    In-memory now; swap _persist() for a DB write later without changing the public API.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._by_inspection: dict[uuid.UUID, list[EvidenceRecord]] = defaultdict(list)
        self._by_id: dict[uuid.UUID, EvidenceRecord] = {}
        self._sequence_counter: dict[uuid.UUID, int] = defaultdict(int)

    def append(
        self,
        *,
        inspection_id: uuid.UUID,
        agent_type: AgentType,
        roi_id: str,
        confidence: float,
        evidence: dict[str, Any],
        explanation: str,
        processing_time_ms: float,
        bounding_box: list[float] | None = None,
        failed: bool = False,
        failure_reason: str | None = None,
    ) -> EvidenceRecord:
        if failed and not failure_reason:
            raise EvidenceStoreError("failure_reason required when failed=True")

        with self._lock:
            seq = self._sequence_counter[inspection_id]
            self._sequence_counter[inspection_id] = seq + 1

            record = EvidenceRecord(
                inspection_id=inspection_id,
                agent_type=agent_type,
                roi_id=roi_id,
                confidence=confidence,
                evidence=evidence,
                explanation=explanation,
                processing_time_ms=processing_time_ms,
                bounding_box=bounding_box,
                failed=failed,
                failure_reason=failure_reason,
                sequence=seq,
            )

            self._by_inspection[inspection_id].append(record)
            self._by_id[record.evidence_id] = record
            self._persist(record)
            return record

    def get(self, evidence_id: uuid.UUID) -> EvidenceRecord:
        with self._lock:
            record = self._by_id.get(evidence_id)
            if record is None:
                raise EvidenceNotFoundError(f"evidence {evidence_id} not found")
            return record

    def get_all_for_inspection(self, inspection_id: uuid.UUID) -> list[EvidenceRecord]:
        with self._lock:
            return list(self._by_inspection.get(inspection_id, []))

    def get_by_agent(
        self, inspection_id: uuid.UUID, agent_type: AgentType
    ) -> list[EvidenceRecord]:
        with self._lock:
            return [
                r
                for r in self._by_inspection.get(inspection_id, [])
                if r.agent_type == agent_type
            ]

    def get_failed(self, inspection_id: uuid.UUID) -> list[EvidenceRecord]:
        with self._lock:
            return [
                r for r in self._by_inspection.get(inspection_id, []) if r.failed
            ]

    def count(self, inspection_id: uuid.UUID) -> int:
        with self._lock:
            return len(self._by_inspection.get(inspection_id, []))

    def clear_inspection(self, inspection_id: uuid.UUID) -> None:
        """Test/debug only. Never call from pipeline code — violates append-only guarantee."""
        raise EvidenceImmutableError(
            "evidence store is append-only; records cannot be cleared"
        )

    def _persist(self, record: EvidenceRecord) -> None:
        """Hook for future DB persistence (Day 2: async SQLAlchemy insert into evidence table)."""
        pass


evidence_store = EvidenceStore()