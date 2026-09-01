# backend/app/pipeline/workflow.py
"""LangGraph orchestration layer for the VisionForge AI 8-stage inspection pipeline."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Literal, Optional, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

from app.core.exceptions import PipelineStageError
from app.pipeline.state import InspectionState, PipelineError as PipelineErrorDict
from app.pipeline.stages.quality_check import run_quality_check
from app.pipeline.stages.authenticity import run_authenticity_stage as run_authenticity
from app.pipeline.stages.reference_match import run_reference_match
from app.pipeline.stages.roi_scheduler import run_roi_scheduler
from app.pipeline.stages.evidence_execution import execute_evidence_stage as run_evidence_execution
from app.pipeline.stages.evidence_fusion import run_evidence_fusion
from app.pipeline.stages.judge import run_judge
from app.pipeline.stages.policy_engine import run_policy_engine
from app.shared.memory import WorkingMemory
from app.shared.evidence_store import EvidenceStore
import logging

logger = logging.getLogger("visionforge.pipeline.workflow")

# ---------------------------------------------------------------------------
# Domain literal types
# ---------------------------------------------------------------------------

StageNumber = Literal[1, 2, 3, 4, 5, 6, 7, 8]
StageName = Literal[
    "quality_check",
    "authenticity",
    "reference_match",
    "roi_scheduler",
    "evidence_execution",
    "evidence_fusion",
    "judge",
    "policy_engine",
]
StageStatus = Literal["pending", "started", "completed", "failed", "skipped"]
PipelineStatus = Literal["pending", "running", "completed", "failed", "review_required"]
WorkflowRoute = Literal["continue", "stop", "review"]

ORDERED_STAGES: tuple[tuple[StageNumber, StageName], ...] = (
    (1, "quality_check"),
    (2, "authenticity"),
    (3, "reference_match"),
    (4, "roi_scheduler"),
    (5, "evidence_execution"),
    (6, "evidence_fusion"),
    (7, "judge"),
    (8, "policy_engine"),
)

STAGE_NUMBER_BY_NAME: dict[StageName, StageNumber] = {
    name: number for number, name in ORDERED_STAGES
}


class WorkflowRunConfig(TypedDict, total=False):
    inspection_id: str
    thread_id: str
    checkpoint_id: Optional[str]
    metadata: dict[str, str]


class WorkflowRunResult(TypedDict):
    state: InspectionState
    status: PipelineStatus
    verdict: Optional[str]
    policy_action: Optional[str]
    error: Optional[PipelineErrorDict]


# ---------------------------------------------------------------------------
# Stage progress helpers (Working Memory / SSE synchronization)
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def mark_stage_started(
    state: InspectionState, stage_number: StageNumber, stage_name: StageName
) -> dict[str, Any]:
    stage_results = list(state.get("stage_results", []))
    stage_results.append(
        {
            "stage_number": stage_number,
            "stage_name": stage_name,
            "status": "started",
            "started_at": _now_iso(),
            "completed_at": None,
            "duration_ms": None,
            "detail": None,
            "error": None,
            "output_keys": [],
        }
    )
    return {
        "current_stage": stage_number,
        "current_stage_name": stage_name,
        "status": "running",
        "stage_results": stage_results,
    }


def mark_stage_completed(
    state: InspectionState,
    stage_number: StageNumber,
    stage_name: StageName,
    output_keys: list[str],
    detail: Optional[str] = None,
) -> dict[str, Any]:
    stage_results = list(state.get("stage_results", []))
    started_at = None
    for result in reversed(stage_results):
        if result["stage_number"] == stage_number and result["status"] == "started":
            started_at = result.get("started_at")
            stage_results.remove(result)
            break

    completed_at = _now_iso()
    duration_ms: Optional[float] = None
    if started_at is not None:
        try:
            start_dt = datetime.fromisoformat(started_at)
            end_dt = datetime.fromisoformat(completed_at)
            duration_ms = (end_dt - start_dt).total_seconds() * 1000.0
        except ValueError:
            duration_ms = None

    stage_results.append(
        {
            "stage_number": stage_number,
            "stage_name": stage_name,
            "status": "completed",
            "started_at": started_at,
            "completed_at": completed_at,
            "duration_ms": duration_ms,
            "detail": detail,
            "error": None,
            "output_keys": output_keys,
        }
    )
    return {"stage_results": stage_results}


def mark_stage_failed(
    state: InspectionState,
    stage_number: StageNumber,
    stage_name: StageName,
    error: PipelineErrorDict,
) -> dict[str, Any]:
    stage_results = list(state.get("stage_results", []))
    started_at = None
    for result in reversed(stage_results):
        if result["stage_number"] == stage_number and result["status"] == "started":
            started_at = result.get("started_at")
            stage_results.remove(result)
            break

    stage_results.append(
        {
            "stage_number": stage_number,
            "stage_name": stage_name,
            "status": "failed",
            "started_at": started_at,
            "completed_at": _now_iso(),
            "duration_ms": None,
            "detail": None,
            "error": error["message"],
            "output_keys": [],
        }
    )
    return {
        "status": "failed",
        "stage_results": stage_results,
        "error": error,
    }


def _build_pipeline_error(
    stage_number: StageNumber,
    stage_name: StageName,
    code: str,
    message: str,
    recoverable: bool = False,
) -> PipelineErrorDict:
    return {
        "stage_number": stage_number,
        "stage_name": stage_name,
        "code": code,
        "message": message,
        "recoverable": recoverable,
        "occurred_at": _now_iso(),
    }


# ---------------------------------------------------------------------------
# Generic stage node wrapper — enforces progress tracking + error isolation
# ---------------------------------------------------------------------------

def _make_stage_node(
    stage_number: StageNumber,
    stage_name: StageName,
    stage_fn,
):
    async def _node(state: InspectionState) -> dict[str, Any]:
        started_patch = mark_stage_started(state, stage_number, stage_name)
        working_state: InspectionState = {**state, **started_patch}  # type: ignore[typeddict-item]

        t0 = time.perf_counter()
        try:
            result_patch: dict[str, Any] = await stage_fn(working_state)
        except PipelineStageError as exc:
            logger.error(
                "Stage %s (%s) failed for inspection %s: %s",
                stage_number,
                stage_name,
                state.get("inspection_id"),
                exc,
                exc_info=True,
            )
            error = _build_pipeline_error(
                stage_number, stage_name, exc.code, str(exc), exc.recoverable
            )
            failed_patch = mark_stage_failed(working_state, stage_number, stage_name, error)
            return {**started_patch, **failed_patch}
        except Exception as exc:  # noqa: BLE001 — top-level isolation boundary
            logger.exception(
                "Unhandled exception in stage %s (%s) for inspection %s",
                stage_number,
                stage_name,
                state.get("inspection_id"),
            )
            error = _build_pipeline_error(
                stage_number,
                stage_name,
                "UNHANDLED_EXCEPTION",
                str(exc),
                recoverable=False,
            )
            failed_patch = mark_stage_failed(working_state, stage_number, stage_name, error)
            return {**started_patch, **failed_patch}

        duration_ms = (time.perf_counter() - t0) * 1000.0
        detail = result_patch.pop("_stage_detail", None)
        completed_patch = mark_stage_completed(
            {**working_state, **result_patch},  # type: ignore[typeddict-item]
            stage_number,
            stage_name,
            output_keys=sorted(result_patch.keys()),
            detail=detail,
        )
        logger.info(
            "Stage %s (%s) completed for inspection %s in %.1fms",
            stage_number,
            stage_name,
            state.get("inspection_id"),
            duration_ms,
        )
        return {**started_patch, **result_patch, **completed_patch}

    return _node


# ---------------------------------------------------------------------------
# Conditional routing functions
# ---------------------------------------------------------------------------

def route_after_quality_check(state: InspectionState) -> WorkflowRoute:
    if state.get("status") == "failed":
        return "stop"
    if not state.get("quality_passed", False):
        return "stop"
    return "continue"


def route_after_authenticity(state: InspectionState) -> WorkflowRoute:
    if state.get("status") == "failed":
        return "stop"
    # Authenticity never hard-blocks per spec — always continue unless the
    # stage itself raised a fatal error captured as "failed" status.
    return "continue"


def route_after_reference_match(state: InspectionState) -> WorkflowRoute:
    if state.get("status") == "failed":
        return "stop"
    if not state.get("reference_matched", False):
        return "review"
    return "continue"


def route_after_policy(state: InspectionState) -> Literal["complete", "review"]:
    policy_result = state.get("policy_result")
    if policy_result and policy_result.get("requires_human_review"):
        return "review"
    return "complete"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

class WorkflowDependencies(TypedDict):
    working_memory: WorkingMemory
    evidence_store: EvidenceStore
    checkpointer: Optional[BaseCheckpointSaver]


def _finalize_review(state: InspectionState) -> dict[str, Any]:
    return {"status": "review_required"}


def _finalize_complete(state: InspectionState) -> dict[str, Any]:
    return {"status": "completed"}


def create_inspection_workflow(
    dependencies: WorkflowDependencies,
) -> CompiledStateGraph:
    """Builds and compiles the 8-stage LangGraph StateGraph for inspections."""

    graph: StateGraph = StateGraph(InspectionState)

    graph.add_node(
        "quality_check", _make_stage_node(1, "quality_check", run_quality_check)
    )
    graph.add_node(
        "authenticity", _make_stage_node(2, "authenticity", run_authenticity)
    )
    graph.add_node(
        "reference_match", _make_stage_node(3, "reference_match", run_reference_match)
    )
    graph.add_node(
        "roi_scheduler", _make_stage_node(4, "roi_scheduler", run_roi_scheduler)
    )
    graph.add_node(
        "evidence_execution",
        _make_stage_node(5, "evidence_execution", run_evidence_execution),
    )
    graph.add_node(
        "evidence_fusion", _make_stage_node(6, "evidence_fusion", run_evidence_fusion)
    )
    graph.add_node("judge", _make_stage_node(7, "judge", run_judge))
    graph.add_node(
        "policy_engine", _make_stage_node(8, "policy_engine", run_policy_engine)
    )
    graph.add_node("finalize_review", _finalize_review)
    graph.add_node("finalize_complete", _finalize_complete)

    graph.add_edge(START, "quality_check")

    graph.add_conditional_edges(
        "quality_check",
        route_after_quality_check,
        {"continue": "authenticity", "stop": END, "review": "finalize_review"},
    )

    graph.add_conditional_edges(
        "authenticity",
        route_after_authenticity,
        {"continue": "reference_match", "stop": END, "review": "finalize_review"},
    )

    graph.add_conditional_edges(
        "reference_match",
        route_after_reference_match,
        {
            "continue": "roi_scheduler",
            "stop": END,
            "review": "finalize_review",
        },
    )

    graph.add_edge("roi_scheduler", "evidence_execution")
    graph.add_edge("evidence_execution", "evidence_fusion")
    graph.add_edge("evidence_fusion", "judge")
    graph.add_edge("judge", "policy_engine")

    graph.add_conditional_edges(
        "policy_engine",
        route_after_policy,
        {"complete": "finalize_complete", "review": "finalize_review"},
    )

    graph.add_edge("finalize_review", END)
    graph.add_edge("finalize_complete", END)

    checkpointer = dependencies.get("checkpointer") or MemorySaver()

    return graph.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Module-level singleton workflow (lazily constructed)
# ---------------------------------------------------------------------------

_compiled_workflow: Optional[CompiledStateGraph] = None


def get_compiled_workflow(
    working_memory: Optional[WorkingMemory] = None,
    evidence_store: Optional[EvidenceStore] = None,
) -> CompiledStateGraph:
    global _compiled_workflow
    if _compiled_workflow is None:
        if working_memory is None or evidence_store is None:
            raise PipelineStageError(
                code="WORKFLOW_NOT_INITIALIZED",
                message=(
                    "Working memory and evidence store must be provided on first "
                    "call to get_compiled_workflow()."
                ),
                recoverable=False,
            )
        _compiled_workflow = create_inspection_workflow(
            {
                "working_memory": working_memory,
                "evidence_store": evidence_store,
                "checkpointer": None,
            }
        )
    return _compiled_workflow


# ---------------------------------------------------------------------------
# Public workflow API
# ---------------------------------------------------------------------------

def _extract_run_result(final_state: InspectionState) -> WorkflowRunResult:
    status: PipelineStatus = final_state.get("status", "pending")  # type: ignore[assignment]
    judge_result = final_state.get("judge_result")
    policy_result = final_state.get("policy_result")
    return {
        "state": final_state,
        "status": status,
        "verdict": judge_result.get("verdict") if judge_result else None,
        "policy_action": policy_result.get("action") if policy_result else None,
        "error": final_state.get("error"),
    }


async def run_inspection_workflow(
    state: InspectionState,
    config: WorkflowRunConfig,
    working_memory: WorkingMemory,
    evidence_store: EvidenceStore,
) -> WorkflowRunResult:
    """Invokes the compiled workflow to completion and returns the final result."""

    if not config.get("inspection_id"):
        raise PipelineStageError(
            code="MISSING_INSPECTION_ID",
            message="WorkflowRunConfig.inspection_id is required.",
            recoverable=False,
        )

    thread_id = config.get("thread_id") or str(uuid.uuid4())
    workflow = get_compiled_workflow(working_memory, evidence_store)

    run_config = {
        "configurable": {
            "thread_id": thread_id,
            **({"checkpoint_id": config["checkpoint_id"]} if config.get("checkpoint_id") else {}),
        },
        "metadata": config.get("metadata", {}),
    }

    try:
        final_state: InspectionState = await workflow.ainvoke(state, config=run_config)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001 — outermost safety net
        logger.exception(
            "Workflow execution crashed for inspection %s", config["inspection_id"]
        )
        error = _build_pipeline_error(
            state.get("current_stage", 1),  # type: ignore[arg-type]
            state.get("current_stage_name", "quality_check"),  # type: ignore[arg-type]
            "WORKFLOW_CRASH",
            str(exc),
            recoverable=False,
        )
        crashed_state: InspectionState = {**state, "status": "failed", "error": error}  # type: ignore[typeddict-item]
        return _extract_run_result(crashed_state)

    return _extract_run_result(final_state)


async def stream_inspection_workflow(
    state: InspectionState,
    config: WorkflowRunConfig,
    working_memory: WorkingMemory,
    evidence_store: EvidenceStore,
) -> AsyncIterator[dict[str, Any]]:
    """Streams partial state updates for SSE consumption by the inspections router."""

    if not config.get("inspection_id"):
        raise PipelineStageError(
            code="MISSING_INSPECTION_ID",
            message="WorkflowRunConfig.inspection_id is required.",
            recoverable=False,
        )

    thread_id = config.get("thread_id") or str(uuid.uuid4())
    workflow = get_compiled_workflow(working_memory, evidence_store)

    run_config = {
        "configurable": {
            "thread_id": thread_id,
            **({"checkpoint_id": config["checkpoint_id"]} if config.get("checkpoint_id") else {}),
        },
        "metadata": config.get("metadata", {}),
    }

    try:
        async for partial_state in workflow.astream(state, config=run_config):  # type: ignore[arg-type]
            yield partial_state
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Workflow stream crashed for inspection %s", config["inspection_id"]
        )
        error = _build_pipeline_error(
            state.get("current_stage", 1),  # type: ignore[arg-type]
            state.get("current_stage_name", "quality_check"),  # type: ignore[arg-type]
            "WORKFLOW_STREAM_CRASH",
            str(exc),
            recoverable=False,
        )
        yield {"status": "failed", "error": error}


async def get_inspection_workflow_state(
    inspection_id: str,
    thread_id: str,
    working_memory: WorkingMemory,
    evidence_store: EvidenceStore,
) -> InspectionState:
    """Fetches the current checkpointed state for a running/completed inspection."""

    workflow = get_compiled_workflow(working_memory, evidence_store)
    snapshot = await workflow.aget_state(
        config={"configurable": {"thread_id": thread_id}}
    )
    if snapshot is None or snapshot.values is None:
        raise PipelineStageError(
            code="INSPECTION_STATE_NOT_FOUND",
            message=f"No workflow state found for inspection {inspection_id}.",
            recoverable=False,
        )
    return snapshot.values  # type: ignore[return-value]