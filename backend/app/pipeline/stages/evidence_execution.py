# backend/app/pipeline/stages/evidence_execution.py
"""
Stage 5 — Evidence Execution Orchestrator.

Consumes the Stage 4 ROIExecutionPlan, crops Golden/Inspection ROI pairs,
dispatches the 4 evidence agents (OCR, Label, Structural, VLM) in parallel
grouped batches respecting scheduler priority, and persists every finding
to the Evidence Store. This module contains NO agent-domain logic (no OCR,
template matching, SSIM/YOLO, or VLM code) — it is a pure orchestrator.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.pipeline.agents.base_agent import EvidenceAgent
from app.shared.evidence_store import EvidenceStore
from app.shared.memory import WorkingMemory
from app.utils.image_utils import crop_normalized_roi as crop_roi

logger = logging.getLogger(__name__)

STAGE_NUMBER = 5
STAGE_NAME = "evidence_execution"

# Max concurrent tasks executed within a single agent batch, to avoid
# saturating rate-limited external APIs (Groq / Gemini) or local CPU-bound
# CV routines (OpenCV / PaddleOCR) all at once.
_MAX_CONCURRENCY_PER_BATCH = 4


# ============================================================
# 1. Primitive / Enum Types
# ============================================================

class ProductType(str, Enum):
    MOTHERBOARD = "MOTHERBOARD"
    BATTERY = "BATTERY"
    RAM = "RAM"


class ROIType(str, Enum):
    TEXT = "TEXT"
    LABEL = "LABEL"
    STRUCTURAL = "STRUCTURAL"
    GENERAL_VISUAL = "GENERAL_VISUAL"


class AgentType(str, Enum):
    OCR = "OCR"
    LABEL = "LABEL"
    STRUCTURAL = "STRUCTURAL"
    VLM = "VLM"


class ExecutionPriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"


class EvidenceStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class OverallExecutionStatus(str, Enum):
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class StageRunStatus(str, Enum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


_PRIORITY_ORDER: dict[ExecutionPriority, int] = {
    ExecutionPriority.CRITICAL: 0,
    ExecutionPriority.HIGH: 1,
    ExecutionPriority.NORMAL: 2,
}


# ============================================================
# 2. ROI Geometry
# ============================================================

class BoundingBox(BaseModel):
    model_config = ConfigDict(frozen=True)

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class ROIDefinition(BaseModel):
    model_config = ConfigDict(frozen=True)

    roi_id: str
    name: str
    type: ROIType
    bounding_box: BoundingBox
    priority: ExecutionPriority
    critical: bool = False
    expected_components: list[str] | None = None


# ============================================================
# 3. Stage 4 -> Stage 5 Contract
# ============================================================

class ROIExecutionTask(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: str
    roi: ROIDefinition
    agent_type: AgentType
    golden_image_path: str
    inspection_image_path: str
    product_type: ProductType
    priority: ExecutionPriority


class ROIExecutionPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    inspection_id: uuid.UUID
    product_type: ProductType
    golden_reference_id: uuid.UUID
    golden_image_path: str
    inspection_image_paths: list[str]
    tasks: list[ROIExecutionTask]
    total_rois: int


# ============================================================
# 4. Cropped ROI Pair
# ============================================================

class CroppedROIPair(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: str
    roi_id: str
    golden_crop_path: str
    inspection_crop_path: str
    bounding_box: BoundingBox
    source_golden_image: str
    source_inspection_image: str


# ============================================================
# 5. Agent Input Contract
# ============================================================

class AgentExecutionInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    inspection_id: uuid.UUID
    task_id: str
    roi_id: str
    agent_type: AgentType
    product_type: ProductType
    golden_crop_path: str
    inspection_crop_path: str
    roi: ROIDefinition


# ============================================================
# 6. Agent Evidence Contract
# ============================================================

class AgentEvidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str
    inspection_id: uuid.UUID
    task_id: str
    roi_id: str
    agent_type: AgentType
    status: EvidenceStatus
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: dict[str, Any]
    explanation: str
    processing_time_ms: float
    source_golden_image: str
    source_inspection_image: str
    roi: BoundingBox
    created_at: datetime


# ============================================================
# 7. Agent Result Contract
# ============================================================

class AgentExecutionError(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    retryable: bool


class AgentExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    task_id: str
    roi_id: str
    agent_type: AgentType
    status: EvidenceStatus
    evidence: AgentEvidence | None = None
    error: AgentExecutionError | None = None


# ============================================================
# 8. Execution Batch
# ============================================================

@dataclass(frozen=True, slots=True)
class AgentExecutionBatch:
    agent_type: AgentType
    tasks: tuple[ROIExecutionTask, ...]
    priority: ExecutionPriority


# ============================================================
# 9. Stage 5 Output
# ============================================================

class EvidenceExecutionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    inspection_id: uuid.UUID
    status: OverallExecutionStatus
    results: list[AgentExecutionResult]
    successful_tasks: int
    failed_tasks: int
    total_processing_time_ms: float
    evidence_ids: list[str]
    errors: list[AgentExecutionError]


# ============================================================
# 10. Agent Registry Protocol
# ============================================================

class EvidenceAgentRegistry:
    """Resolves an AgentType to its concrete EvidenceAgent implementation."""

    def __init__(self, agents: dict[AgentType, EvidenceAgent]) -> None:
        if not agents:
            raise ValueError("EvidenceAgentRegistry requires at least one registered agent")
        self._agents = dict(agents)

    def get(self, agent_type: AgentType) -> EvidenceAgent:
        try:
            return self._agents[agent_type]
        except KeyError as exc:
            raise LookupError(
                f"No EvidenceAgent registered for agent_type={agent_type.value!r}"
            ) from exc


# ============================================================
# 11. Stage Dependencies
# ============================================================

@dataclass(slots=True)
class EvidenceExecutionDependencies:
    evidence_store: EvidenceStore
    working_memory: WorkingMemory
    agent_registry: EvidenceAgentRegistry
    max_concurrency_per_batch: int = _MAX_CONCURRENCY_PER_BATCH


# ============================================================
# 12. Custom Exceptions
# ============================================================

class EvidenceExecutionError(Exception):
    """Raised when the orchestrator itself cannot proceed (not an agent failure)."""


class ROICropError(EvidenceExecutionError):
    """Raised when cropping the golden/inspection ROI pair fails."""


# ============================================================
# 13. Internal Orchestration Functions
# ============================================================

async def crop_execution_task(task: ROIExecutionTask) -> CroppedROIPair:
    """
    Crop the exact bounding-box region from both the golden reference image
    and the inspection image for a single ROI task.
    """
    bbox = task.roi.bounding_box
    try:
        golden_crop_path, inspection_crop_path = await asyncio.gather(
            crop_roi(
                image_path=task.golden_image_path,
                x=bbox.x,
                y=bbox.y,
                width=bbox.width,
                height=bbox.height,
            ),
            crop_roi(
                image_path=task.inspection_image_path,
                x=bbox.x,
                y=bbox.y,
                width=bbox.width,
                height=bbox.height,
            ),
        )
    except Exception as exc:
        raise ROICropError(
            f"Failed to crop ROI '{task.roi.roi_id}' for task '{task.task_id}': {exc}"
        ) from exc

    return CroppedROIPair(
        task_id=task.task_id,
        roi_id=task.roi.roi_id,
        golden_crop_path=golden_crop_path,
        inspection_crop_path=inspection_crop_path,
        bounding_box=bbox,
        source_golden_image=task.golden_image_path,
        source_inspection_image=task.inspection_image_path,
    )


async def build_agent_input(
    task: ROIExecutionTask,
    crops: CroppedROIPair,
    inspection_id: uuid.UUID,
) -> AgentExecutionInput:
    """Build the standardized input contract handed to an EvidenceAgent."""
    return AgentExecutionInput(
        inspection_id=inspection_id,
        task_id=task.task_id,
        roi_id=task.roi.roi_id,
        agent_type=task.agent_type,
        product_type=task.product_type,
        golden_crop_path=crops.golden_crop_path,
        inspection_crop_path=crops.inspection_crop_path,
        roi=task.roi,
    )


async def execute_task(
    task: ROIExecutionTask,
    inspection_id: uuid.UUID,
    dependencies: EvidenceExecutionDependencies,
) -> AgentExecutionResult:
    """
    Execute a single ROI task end-to-end: crop -> build input -> invoke agent.
    Never raises — all failures are captured as an explicit AgentExecutionError
    so a single bad ROI cannot abort the whole batch.
    """
    start = time.perf_counter()
    try:
        crops = await crop_execution_task(task)
    except ROICropError as exc:
        logger.error(
            "ROI crop failed",
            extra={"task_id": task.task_id, "roi_id": task.roi.roi_id, "error": str(exc)},
        )
        return AgentExecutionResult(
            task_id=task.task_id,
            roi_id=task.roi.roi_id,
            agent_type=task.agent_type,
            status=EvidenceStatus.FAILED,
            evidence=None,
            error=AgentExecutionError(
                code="ROI_CROP_FAILED",
                message=str(exc),
                retryable=False,
            ),
        )

    try:
        agent = dependencies.agent_registry.get(task.agent_type)
    except LookupError as exc:
        logger.error(
            "Agent resolution failed",
            extra={"task_id": task.task_id, "agent_type": task.agent_type.value},
        )
        return AgentExecutionResult(
            task_id=task.task_id,
            roi_id=task.roi.roi_id,
            agent_type=task.agent_type,
            status=EvidenceStatus.FAILED,
            evidence=None,
            error=AgentExecutionError(
                code="AGENT_NOT_REGISTERED",
                message=str(exc),
                retryable=False,
            ),
        )

    agent_input = await build_agent_input(task, crops, inspection_id)

    try:
        evidence = await agent.execute(agent_input)
    except asyncio.CancelledError:
        raise
    except asyncio.TimeoutError as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.warning(
            "Agent execution timed out",
            extra={"task_id": task.task_id, "agent_type": task.agent_type.value, "elapsed_ms": elapsed_ms},
        )
        return AgentExecutionResult(
            task_id=task.task_id,
            roi_id=task.roi.roi_id,
            agent_type=task.agent_type,
            status=EvidenceStatus.FAILED,
            evidence=None,
            error=AgentExecutionError(
                code="AGENT_TIMEOUT",
                message=f"Agent '{task.agent_type.value}' timed out: {exc}",
                retryable=True,
            ),
        )
    except Exception as exc:  # noqa: BLE001 — agent failures must never fabricate evidence
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.exception(
            "Agent execution raised an unhandled exception",
            extra={"task_id": task.task_id, "agent_type": task.agent_type.value, "elapsed_ms": elapsed_ms},
        )
        return AgentExecutionResult(
            task_id=task.task_id,
            roi_id=task.roi.roi_id,
            agent_type=task.agent_type,
            status=EvidenceStatus.FAILED,
            evidence=None,
            error=AgentExecutionError(
                code="AGENT_EXECUTION_ERROR",
                message=str(exc),
                retryable=True,
            ),
        )

    if evidence.status != EvidenceStatus.SUCCESS:
        return AgentExecutionResult(
            task_id=task.task_id,
            roi_id=task.roi.roi_id,
            agent_type=task.agent_type,
            status=EvidenceStatus.FAILED,
            evidence=evidence,
            error=AgentExecutionError(
                code="AGENT_REPORTED_FAILURE",
                message=evidence.explanation or "Agent reported a non-success status",
                retryable=False,
            ),
        )

    return AgentExecutionResult(
        task_id=task.task_id,
        roi_id=task.roi.roi_id,
        agent_type=task.agent_type,
        status=EvidenceStatus.SUCCESS,
        evidence=evidence,
        error=None,
    )


async def execute_batch(
    batch: AgentExecutionBatch,
    inspection_id: uuid.UUID,
    dependencies: EvidenceExecutionDependencies,
) -> list[AgentExecutionResult]:
    """
    Execute all tasks within a single agent batch concurrently, bounded by
    a semaphore to respect free-tier LLM/VLM rate limits and avoid
    overwhelming local CPU-bound CV routines.
    """
    semaphore = asyncio.Semaphore(dependencies.max_concurrency_per_batch)

    async def _bounded(task: ROIExecutionTask) -> AgentExecutionResult:
        async with semaphore:
            return await execute_task(task, inspection_id, dependencies)

    return await asyncio.gather(*(_bounded(task) for task in batch.tasks))


async def persist_evidence(
    inspection_id: uuid.UUID,
    result: AgentExecutionResult,
    evidence_store: EvidenceStore,
) -> None:
    """
    Append successful evidence to the append-only Evidence Store.
    Failures are logged but never fabricated or silently swallowed at the
    caller's expense — persistence errors are re-raised so the orchestrator
    can record them against the task.
    """
    if result.status != EvidenceStatus.SUCCESS or result.evidence is None:
        return

    try:
        await evidence_store.append(inspection_id, result.evidence)
    except Exception as exc:
        logger.exception(
            "Failed to persist evidence to Evidence Store",
            extra={"task_id": result.task_id, "roi_id": result.roi_id},
        )
        raise EvidenceExecutionError(
            f"Persistence failed for task '{result.task_id}': {exc}"
        ) from exc


def group_execution_tasks(
    tasks: list[ROIExecutionTask],
) -> list[AgentExecutionBatch]:
    """
    Group tasks by agent type into execution batches, ordered so that
    the highest-priority batch (i.e. containing the most urgent ROI)
    executes first. Within a batch, task order is preserved but the
    scheduler's priority is honored by sorting tasks internally too.
    """
    grouped: dict[AgentType, list[ROIExecutionTask]] = {}
    for task in tasks:
        grouped.setdefault(task.agent_type, []).append(task)

    batches: list[AgentExecutionBatch] = []
    for agent_type, agent_tasks in grouped.items():
        sorted_tasks = sorted(
            agent_tasks, key=lambda t: _PRIORITY_ORDER[t.priority]
        )
        batch_priority = min(
            (t.priority for t in sorted_tasks), key=lambda p: _PRIORITY_ORDER[p]
        )
        batches.append(
            AgentExecutionBatch(
                agent_type=agent_type,
                tasks=tuple(sorted_tasks),
                priority=batch_priority,
            )
        )

    batches.sort(key=lambda b: _PRIORITY_ORDER[b.priority])
    return batches


# ============================================================
# 14. Stage Entry Point
# ============================================================

async def execute_evidence_stage(
    plan: ROIExecutionPlan,
    dependencies: EvidenceExecutionDependencies,
) -> EvidenceExecutionResult:
    """
    Stage 5 entry point: consume the Stage 4 ROIExecutionPlan, dispatch the
    4 evidence agents in parallel (grouped by agent, ordered by priority),
    persist successful findings to the Evidence Store, and report status
    to Working Memory for the SSE progress layer to consume.
    """
    stage_start = time.perf_counter()
    inspection_id = plan.inspection_id

    await dependencies.working_memory.update_stage_status(
        inspection_id,
        STAGE_NUMBER,
        StageRunStatus.STARTED,
        detail=f"Dispatching {plan.total_rois} ROIs across 4 agents",
    )

    if not plan.tasks:
        error = AgentExecutionError(
            code="EMPTY_EXECUTION_PLAN",
            message="ROIExecutionPlan contains no tasks to execute",
            retryable=False,
        )
        await dependencies.working_memory.update_stage_status(
            inspection_id,
            STAGE_NUMBER,
            StageRunStatus.FAILED,
            detail=error.message,
        )
        return EvidenceExecutionResult(
            inspection_id=inspection_id,
            status=OverallExecutionStatus.FAILED,
            results=[],
            successful_tasks=0,
            failed_tasks=0,
            total_processing_time_ms=(time.perf_counter() - stage_start) * 1000,
            evidence_ids=[],
            errors=[error],
        )

    batches = group_execution_tasks(plan.tasks)

    all_results: list[AgentExecutionResult] = []
    persistence_errors: list[AgentExecutionError] = []

    for batch in batches:
        try:
            batch_results = await execute_batch(batch, inspection_id, dependencies)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — batch-level infra failure, isolate per batch
            logger.exception(
                "Batch execution failed unexpectedly",
                extra={"agent_type": batch.agent_type.value},
            )
            for task in batch.tasks:
                all_results.append(
                    AgentExecutionResult(
                        task_id=task.task_id,
                        roi_id=task.roi.roi_id,
                        agent_type=task.agent_type,
                        status=EvidenceStatus.FAILED,
                        evidence=None,
                        error=AgentExecutionError(
                            code="BATCH_EXECUTION_ERROR",
                            message=str(exc),
                            retryable=True,
                        ),
                    )
                )
            continue

        all_results.extend(batch_results)

        for result in batch_results:
            try:
                await persist_evidence(inspection_id, result, dependencies.evidence_store)
            except EvidenceExecutionError as exc:
                persistence_errors.append(
                    AgentExecutionError(
                        code="EVIDENCE_PERSISTENCE_FAILED",
                        message=str(exc),
                        retryable=True,
                    )
                )

    successful_results = [r for r in all_results if r.status == EvidenceStatus.SUCCESS]
    failed_results = [r for r in all_results if r.status == EvidenceStatus.FAILED]

    evidence_ids = [
        r.evidence.evidence_id for r in successful_results if r.evidence is not None
    ]
    collected_errors = [r.error for r in failed_results if r.error is not None] + persistence_errors

    total_tasks = len(all_results)
    if len(successful_results) == total_tasks and total_tasks > 0:
        overall_status = OverallExecutionStatus.COMPLETED
    elif len(successful_results) == 0:
        overall_status = OverallExecutionStatus.FAILED
    else:
        overall_status = OverallExecutionStatus.PARTIAL

    total_processing_time_ms = (time.perf_counter() - stage_start) * 1000

    stage_run_status = (
        StageRunStatus.COMPLETED
        if overall_status != OverallExecutionStatus.FAILED
        else StageRunStatus.FAILED
    )
    await dependencies.working_memory.update_stage_status(
        inspection_id,
        STAGE_NUMBER,
        stage_run_status,
        detail=(
            f"{len(successful_results)}/{total_tasks} ROI evidence tasks succeeded "
            f"across {len(batches)} agent batches"
        ),
    )

    return EvidenceExecutionResult(
        inspection_id=inspection_id,
        status=overall_status,
        results=all_results,
        successful_tasks=len(successful_results),
        failed_tasks=len(failed_results),
        total_processing_time_ms=total_processing_time_ms,
        evidence_ids=evidence_ids,
        errors=collected_errors,
    )