# backend/app/pipeline/state.py
"""
Inspection state (Anil, W2 D3).

Bridges the two shared services a stage touches — WorkingMemory (per-inspection
scratchpad) and the global EvidenceStore (append-only audit trail) — behind one
object that every LangGraph node receives.

Also exposes progress() which powers the SSE stage events
(GET /inspections/{id}/events, see VisionForge.md §7b).
"""
from __future__ import annotations

import asyncio
from typing import Any, TypedDict

from app.shared.evidence_store import AgentType, EvidenceRecord, EvidenceStore, evidence_store
from app.shared.memory import (
    PipelineStageName,
    StageResult,
    WorkingMemory,
    WorkingMemoryRegistry,
    working_memory_registry,
)


class PipelineError(TypedDict):
    stage_number: int
    stage_name: str
    code: str
    message: str
    recoverable: bool
    occurred_at: str


# Ordered list of the 8 pipeline stages — drives progress() for SSE.
STAGE_ORDER: list[PipelineStageName] = [
    PipelineStageName.QUALITY_CHECK,
    PipelineStageName.AUTHENTICITY,
    PipelineStageName.REFERENCE_MATCH,
    PipelineStageName.ROI_SCHEDULER,
    PipelineStageName.EVIDENCE_EXECUTION,
    PipelineStageName.EVIDENCE_FUSION,
    PipelineStageName.JUDGE,
    PipelineStageName.POLICY_ENGINE,
]


class InspectionState:
    """
    One object per inspection, passed through every pipeline stage.

    - memory: per-inspection scratchpad (fields updated as stages complete)
    - evidence: the global append-only EvidenceStore (write via append_evidence)
    """

    def __init__(self, memory: WorkingMemory, evidence: EvidenceStore) -> None:
        self.memory = memory
        self.evidence = evidence
        self._append_lock = asyncio.Lock()

    # ── Stage recording ───────────────────────────────────────────────────────

    async def record_stage(self, result: StageResult) -> StageResult:
        """Record a stage result into WorkingMemory and return it (stage chaining)."""
        await self.memory.record_stage(result)
        return result

    # ── Evidence bridging ─────────────────────────────────────────────────────

    async def append_evidence(
        self,
        *,
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
        """
        Thread-safe bridge to the append-only EvidenceStore; keeps the
        evidence id referenced in WorkingMemory for later stages.
        """
        async with self._append_lock:
            record = self.evidence.append(
                inspection_id=self.memory.inspection_id,
                agent_type=agent_type,
                roi_id=roi_id,
                confidence=confidence,
                evidence=evidence,
                explanation=explanation,
                processing_time_ms=processing_time_ms,
                bounding_box=bounding_box,
                failed=failed,
                failure_reason=failure_reason,
            )
            refs = list(self.memory.evidence_refs)
            refs.append(record.evidence_id)
            await self.memory.update(evidence_refs=refs)
            return record

    # ── Progress (SSE payload) ────────────────────────────────────────────────

    def progress(self) -> dict[str, Any]:
        """
        Current pipeline progress for the SSE stream / status fallback endpoint.
        Shape matches the documented event payload (VisionForge.md §7b):
        {stage, stage_name, status, progress (n/8), detail}
        """
        done = {r.stage: r for r in self.memory.stage_history}

        completed = sum(
            1 for s in STAGE_ORDER
            if s in done and done[s].status in ("passed", "flagged")
        )
        failed = [s for s in STAGE_ORDER if s in done and done[s].status == "failed"]

        if failed:
            current = failed[0]
            status = "failed"
        elif completed >= len(STAGE_ORDER):
            current = STAGE_ORDER[-1]
            status = "completed"
        else:
            current = STAGE_ORDER[completed]
            status = "in_progress"

        current_result = done.get(current)
        detail = None
        if current_result is not None:
            detail = current_result.error if current_result.status == "failed" else current_result.data
        return {
            "stage": STAGE_ORDER.index(current) + 1,
            "stage_name": current.value,
            "status": status,
            "progress": completed,
            "detail": detail,
        }

    def snapshot(self) -> dict[str, Any]:
        """Full serializable snapshot (memory dict + evidence summary)."""
        return {
            "memory": self.memory.to_dict(),
            "evidence_count": self.evidence.count(self.memory.inspection_id),
        }


class InspectionStateRegistry:
    """
    Process-local registry: inspection_id -> InspectionState.
    Wraps WorkingMemoryRegistry so stages fetch one consistent object.
    """

    def __init__(
        self,
        memory_registry: WorkingMemoryRegistry | None = None,
        store: EvidenceStore | None = None,
    ) -> None:
        self._memories = memory_registry or working_memory_registry
        self._evidence = store or evidence_store
        self._lock = asyncio.Lock()

    async def get_or_create(self, inspection_id, vendor_id=None, location: str | None = None) -> InspectionState:
        memory = await self._memories.get_or_create(
            inspection_id, vendor_id=vendor_id, location=location
        )
        return InspectionState(memory=memory, evidence=self._evidence)

    async def get(self, inspection_id) -> InspectionState | None:
        memory = await self._memories.get(inspection_id)
        if memory is None:
            return None
        return InspectionState(memory=memory, evidence=self._evidence)

    async def release(self, inspection_id) -> None:
        await self._memories.release(inspection_id)


inspection_state_registry = InspectionStateRegistry()
