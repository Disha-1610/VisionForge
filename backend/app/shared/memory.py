from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID


class PipelineStageName(str, Enum):
    QUALITY_CHECK = "quality_check"
    AUTHENTICITY = "authenticity"
    REFERENCE_MATCH = "reference_match"
    ROI_SCHEDULER = "roi_scheduler"
    EVIDENCE_EXECUTION = "evidence_execution"
    EVIDENCE_FUSION = "evidence_fusion"
    JUDGE = "judge"
    POLICY_ENGINE = "policy_engine"


@dataclass(slots=True)
class StageResult:
    stage: PipelineStageName
    status: str  # "passed" | "failed" | "flagged"
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def duration_ms(self) -> float | None:
        if self.started_at is None or self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds() * 1000


@dataclass(slots=True)
class WorkingMemory:
    """
    Per-inspection scratchpad. One instance per inspection_id, shared
    by reference across all pipeline stages via WorkingMemoryRegistry.
    Not for cross-inspection state — Evidence Store handles persistence.
    """

    inspection_id: UUID
    vendor_id: UUID | None = None
    location: str | None = None

    image_paths: list[str] = field(default_factory=list)
    golden_reference_id: UUID | None = None
    golden_image_path: str | None = None
    roi_template: dict[str, Any] | None = None

    quality_passed: bool | None = None
    authenticity_score: float | None = None
    authenticity_flagged: bool = False

    similarity_score: float | None = None

    roi_execution_plan: list[dict[str, Any]] = field(default_factory=list)

    evidence_refs: list[UUID] = field(default_factory=list)
    fused_evidence: dict[str, Any] | None = None

    fraud_probability: float | None = None
    judge_confidence: float | None = None
    fraud_category: str | None = None
    root_cause: str | None = None

    policy_action: str | None = None

    stage_history: list[StageResult] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False, compare=False)

    async def record_stage(self, result: StageResult) -> None:
        async with self._lock:
            self.stage_history.append(result)
            self.updated_at = datetime.now(timezone.utc)

    async def update(self, **fields: Any) -> None:
        async with self._lock:
            for key, value in fields.items():
                if not hasattr(self, key):
                    raise AttributeError(f"WorkingMemory has no field '{key}'")
                setattr(self, key, value)
            self.updated_at = datetime.now(timezone.utc)

    async def get(self, key: str) -> Any:
        async with self._lock:
            return getattr(self, key)

    def last_stage_result(self, stage: PipelineStageName) -> StageResult | None:
        for result in reversed(self.stage_history):
            if result.stage == stage:
                return result
        return None

    def failed_stages(self) -> list[StageResult]:
        return [r for r in self.stage_history if r.status == "failed"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "inspection_id": str(self.inspection_id),
            "vendor_id": str(self.vendor_id) if self.vendor_id else None,
            "location": self.location,
            "image_paths": self.image_paths,
            "golden_reference_id": str(self.golden_reference_id) if self.golden_reference_id else None,
            "golden_image_path": self.golden_image_path,
            "roi_template": self.roi_template,
            "quality_passed": self.quality_passed,
            "authenticity_score": self.authenticity_score,
            "authenticity_flagged": self.authenticity_flagged,
            "similarity_score": self.similarity_score,
            "roi_execution_plan": self.roi_execution_plan,
            "evidence_refs": [str(e) for e in self.evidence_refs],
            "fused_evidence": self.fused_evidence,
            "fraud_probability": self.fraud_probability,
            "judge_confidence": self.judge_confidence,
            "fraud_category": self.fraud_category,
            "root_cause": self.root_cause,
            "policy_action": self.policy_action,
            "stage_history": [
                {
                    "stage": r.stage.value,
                    "status": r.status,
                    "data": r.data,
                    "error": r.error,
                    "duration_ms": r.duration_ms(),
                }
                for r in self.stage_history
            ],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class WorkingMemoryRegistry:
    """
    Process-local registry mapping inspection_id -> WorkingMemory.
    Stages fetch the same instance via get_or_create — no duplicated state.
    Not for multi-worker deployments; swap for Redis-backed store there.
    """

    def __init__(self) -> None:
        self._store: dict[UUID, WorkingMemory] = {}
        self._registry_lock = asyncio.Lock()

    async def get_or_create(
        self,
        inspection_id: UUID,
        vendor_id: UUID | None = None,
        location: str | None = None,
    ) -> WorkingMemory:
        async with self._registry_lock:
            if inspection_id not in self._store:
                self._store[inspection_id] = WorkingMemory(
                    inspection_id=inspection_id,
                    vendor_id=vendor_id,
                    location=location,
                )
            return self._store[inspection_id]

    async def get(self, inspection_id: UUID) -> WorkingMemory | None:
        async with self._registry_lock:
            return self._store.get(inspection_id)

    async def release(self, inspection_id: UUID) -> None:
        async with self._registry_lock:
            self._store.pop(inspection_id, None)


working_memory_registry = WorkingMemoryRegistry()