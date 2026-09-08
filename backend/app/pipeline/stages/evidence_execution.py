# backend/app/pipeline/stages/evidence_execution.py
"""
Stage 5 — Evidence Execution (Disha, W3 D1).

Per VisionForge.md Section 4 Stage 5 & Section 1:
  - Consumes Stage 4 ROIExecutionPlan and ROITemplate from WorkingMemory.
  - Crops paired Golden ROI and Inspection ROI images using exact bounding boxes.
  - Distributes only the cropped Golden ROI & Inspection ROI image pairs to specialized agents.
  - Executes batches in parallel respecting priority order (critical ROIs first).
  - Collects standardized AgentResult from each agent and stores findings into EvidenceStore
    via state.append_evidence().
  - Isolates errors per ROI/agent so failures do not abort the entire pipeline.
  - Records StageResult for Stage 5.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from PIL import Image

from app.pipeline.agents.base_agent import AgentResult, BaseAgent
from app.pipeline.agents.label_agent import LabelAgent
from app.pipeline.agents.ocr_agent import OCRAgent
from app.pipeline.agents.structural_agent import StructuralAgent
from app.pipeline.state import InspectionState
from app.shared.evidence_store import AgentType
from app.shared.memory import PipelineStageName, StageResult
from app.utils.image_utils import (
    BoundingBox,
    BoundingBoxError,
    ImageProcessingError,
    ImageSource,
    NormalizedBoundingBox,
    crop_normalized_roi_pair,
    crop_roi_pair,
    get_image_size,
    load_pil_image,
)

logger = logging.getLogger("app.pipeline.evidence_execution")

DEFAULT_MAX_CONCURRENCY = 4


def get_default_agent_registry() -> dict[AgentType, BaseAgent]:
    """Provide the default set of initialized specialized evidence agents."""
    return {
        AgentType.OCR: OCRAgent(),
        AgentType.LABEL: LabelAgent(),
        AgentType.STRUCTURAL: StructuralAgent(),
    }


def _parse_bbox(bbox_data: Any) -> tuple[float, float, float, float]:
    """Extract (x, y, width, height) from dict or model."""
    if isinstance(bbox_data, dict):
        return (
            float(bbox_data.get("x", 0)),
            float(bbox_data.get("y", 0)),
            float(bbox_data.get("width", 0)),
            float(bbox_data.get("height", 0)),
        )
    if hasattr(bbox_data, "x") and hasattr(bbox_data, "y"):
        return (
            float(bbox_data.x),
            float(bbox_data.y),
            float(bbox_data.width),
            float(bbox_data.height),
        )
    raise ValueError(f"Unrecognized bounding box format: {bbox_data}")


def _crop_roi_pair_safe(
    golden_img: Image.Image,
    inspection_img: Image.Image,
    bbox_data: Any,
    coordinate_system: str,
) -> tuple[Image.Image, Image.Image, list[float]]:
    """
    Safely crop paired ROIs from golden and inspection images,
    handling coordinate normalization and boundary clamping.
    """
    x, y, w, h = _parse_bbox(bbox_data)
    is_normalized = (
        coordinate_system.lower() == "normalized"
        or (x <= 1.0 and y <= 1.0 and w <= 1.0 and h <= 1.0 and (w < 1.0 or h < 1.0))
    )

    if is_normalized:
        # Clamp normalized coordinates to [0, 1]
        nx = max(0.0, min(1.0, x))
        ny = max(0.0, min(1.0, y))
        nw = max(0.001, min(1.0 - nx, w))
        nh = max(0.001, min(1.0 - ny, h))
        norm_bbox = NormalizedBoundingBox(x=nx, y=ny, width=nw, height=nh)
        pair = crop_normalized_roi_pair(golden_img, inspection_img, norm_bbox)
        return pair.golden, pair.inspection, [nx, ny, nw, nh]

    # Pixel coordinates
    gw_size = get_image_size(golden_img)
    iw_size = get_image_size(inspection_img)
    max_w = min(gw_size.width, iw_size.width)
    max_h = min(gw_size.height, iw_size.height)

    px = max(0, min(max_w - 1, int(round(x))))
    py = max(0, min(max_h - 1, int(round(y))))
    pw = max(1, min(max_w - px, int(round(w))))
    ph = max(1, min(max_h - py, int(round(h))))

    pixel_bbox = BoundingBox(x=px, y=py, width=pw, height=ph)
    pair = crop_roi_pair(golden_img, inspection_img, pixel_bbox)
    return pair.golden, pair.inspection, [float(px), float(py), float(pw), float(ph)]


def _resolve_agent_type(raw_val: Any) -> AgentType:
    if isinstance(raw_val, AgentType):
        return raw_val
    if hasattr(raw_val, "value"):
        raw_val = raw_val.value
    raw_str = str(raw_val).lower().strip()
    if "." in raw_str:
        raw_str = raw_str.split(".")[-1]

    mapping = {
        "text": AgentType.OCR,
        "ocr": AgentType.OCR,
        "label": AgentType.LABEL,
        "structural": AgentType.STRUCTURAL,
        "vlm": AgentType.VLM,
        "visual": AgentType.VLM,
    }
    return mapping.get(raw_str, AgentType.STRUCTURAL)


async def _execute_single_roi(
    roi_id: str,
    region_info: dict[str, Any],
    golden_img: Image.Image,
    inspection_img: Image.Image,
    coordinate_system: str,
    agent_registry: dict[AgentType, BaseAgent],
    state: InspectionState,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    """Execute a single ROI crop analysis with error isolation."""
    raw_agent = region_info.get("agent") or region_info.get("type") or "structural"
    agent_type = _resolve_agent_type(raw_agent)


    bbox_data = region_info.get("bbox")
    roi_type = region_info.get("type")

    async with semaphore:
        start_time = time.perf_counter()
        # 1. Crop ROI pair
        try:
            golden_crop, inspection_crop, final_bbox = _crop_roi_pair_safe(
                golden_img=golden_img,
                inspection_img=inspection_img,
                bbox_data=bbox_data,
                coordinate_system=coordinate_system,
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error("Failed to crop ROI pair for roi_id=%s: %s", roi_id, exc)
            ev = await state.append_evidence(
                agent_type=agent_type,
                roi_id=roi_id,
                confidence=0.0,
                evidence={"error": str(exc), "stage": "cropping"},
                explanation=f"Failed to crop ROI pair: {exc}",
                processing_time_ms=round(elapsed_ms, 2),
                failed=True,
                failure_reason=str(exc),
            )
            return {
                "roi_id": roi_id,
                "agent_type": agent_type.value,
                "has_defect": True,
                "failed": True,
                "evidence_id": ev.evidence_id,
            }

        # 2. Select Agent from Registry
        agent = agent_registry.get(agent_type)
        if agent is None:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            msg = f"No agent registered for type '{agent_type.value}'"
            logger.warning("Stage 5 skipping roi_id=%s: %s", roi_id, msg)
            ev = await state.append_evidence(
                agent_type=agent_type,
                roi_id=roi_id,
                confidence=0.0,
                evidence={"error": msg, "stage": "dispatch"},
                explanation=msg,
                processing_time_ms=round(elapsed_ms, 2),
                bounding_box=final_bbox,
                failed=True,
                failure_reason=msg,
            )
            return {
                "roi_id": roi_id,
                "agent_type": agent_type.value,
                "has_defect": False,
                "failed": True,
                "evidence_id": ev.evidence_id,
            }

        # 3. Run Agent
        agent_input_data = {
            **region_info,
            "roi_id": roi_id,
            "roi_type": roi_type,
            "bbox": final_bbox,
        }
        result: AgentResult = await agent.run(
            golden_roi=golden_crop,
            inspection_roi=inspection_crop,
            roi_data=agent_input_data,
        )

        # 4. Save to EvidenceStore via InspectionState
        ev = await state.append_evidence(
            agent_type=result.agent_type,
            roi_id=result.roi_id,
            confidence=result.confidence,
            evidence={
                **result.evidence,
                "detector_name": result.detector_name,
                "has_defect": result.has_defect,
                "roi_type": result.roi_type or str(roi_type),
            },
            explanation=result.explanation,
            processing_time_ms=result.processing_time_ms,
            bounding_box=final_bbox,
            failed=result.failed,
            failure_reason=result.failure_reason,
        )

        return {
            "roi_id": roi_id,
            "agent_type": result.agent_type.value,
            "has_defect": result.has_defect,
            "confidence": result.confidence,
            "failed": result.failed,
            "evidence_id": ev.evidence_id,
        }


async def run_evidence_execution(
    state: InspectionState,
    agent_registry: dict[AgentType, BaseAgent] | None = None,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    golden_image: ImageSource | None = None,
    inspection_image: ImageSource | None = None,
) -> StageResult:
    """
    Stage 5 entrypoint — Evidence Execution Orchestrator.

    Consumes Stage 4 execution plan, crops paired ROIs from golden & inspection images,
    dispatches each to its specialized agent in parallel priority batches,
    and records all findings into the Evidence Store.
    """
    stage_start = time.perf_counter()

    # 1. Quality gate check
    if state.memory.quality_passed is False:
        detail = {"reason": "quality_check_failed"}
        return await state.record_stage(
            StageResult(
                stage=PipelineStageName.EVIDENCE_EXECUTION,
                status="failed",
                data=detail,
                error="Quality check failed in Stage 1; Evidence execution skipped",
            )
        )

    # 2. Verify ROI Template & Execution Plan in Memory
    roi_template_data = state.memory.roi_template
    roi_batches = state.memory.roi_execution_plan

    if not roi_template_data:
        err = "No roi_template found in WorkingMemory; run Stage 4 (ROI Scheduler) first"
        logger.error(err)
        return await state.record_stage(
            StageResult(
                stage=PipelineStageName.EVIDENCE_EXECUTION,
                status="failed",
                data={"error_type": "MissingROITemplate"},
                error=err,
            )
        )

    # 3. Load Golden and Inspection Images
    try:
        if golden_image is not None:
            pil_golden = load_pil_image(golden_image)
        elif state.memory.golden_image_path:
            pil_golden = load_pil_image(state.memory.golden_image_path)
        else:
            raise ValueError("No golden image path or instance found in inspection state")

        if inspection_image is not None:
            pil_inspection = load_pil_image(inspection_image)
        elif state.memory.image_paths:
            pil_inspection = load_pil_image(state.memory.image_paths[0])
        else:
            raise ValueError("No inspection image path or instance found in inspection state")
    except Exception as exc:
        logger.error("Failed loading Golden or Inspection image for Stage 5: %s", exc)
        return await state.record_stage(
            StageResult(
                stage=PipelineStageName.EVIDENCE_EXECUTION,
                status="failed",
                data={"error_type": type(exc).__name__},
                error=f"Could not load images for ROI cropping: {exc}",
            )
        )

    # 4. Setup Agents and Region Index
    registry = agent_registry if agent_registry is not None else get_default_agent_registry()
    regions_list = roi_template_data.get("regions") or []
    regions_by_id: dict[str, dict[str, Any]] = {
        str(r.get("id")): r for r in regions_list if isinstance(r, dict) and "id" in r
    }
    coord_system = str(roi_template_data.get("coordinate_system") or roi_template_data.get("coordinateSystem") or "pixel")

    semaphore = asyncio.Semaphore(max_concurrency)

    # 5. Execute ROIs by Batch (or directly from regions if no batches)
    executed_results: list[dict[str, Any]] = []

    if roi_batches:
        # Grouped execution ordered by Stage 4 scheduler priority
        for batch in roi_batches:
            batch_roi_ids = batch.get("roi_ids") or []
            tasks = []
            for roi_id in batch_roi_ids:
                region_info = regions_by_id.get(roi_id)
                if not region_info:
                    logger.warning("ROI id '%s' in batch not found in template regions", roi_id)
                    continue
                tasks.append(
                    _execute_single_roi(
                        roi_id=roi_id,
                        region_info=region_info,
                        golden_img=pil_golden,
                        inspection_img=pil_inspection,
                        coordinate_system=coord_system,
                        agent_registry=registry,
                        state=state,
                        semaphore=semaphore,
                    )
                )
            if tasks:
                batch_results = await asyncio.gather(*tasks, return_exceptions=False)
                executed_results.extend(batch_results)
    else:
        # Fallback to direct region execution
        tasks = [
            _execute_single_roi(
                roi_id=str(r.get("id")),
                region_info=r,
                golden_img=pil_golden,
                inspection_img=pil_inspection,
                coordinate_system=coord_system,
                agent_registry=registry,
                state=state,
                semaphore=semaphore,
            )
            for r in regions_list
        ]
        if tasks:
            executed_results = await asyncio.gather(*tasks, return_exceptions=False)

    total_time_ms = round((time.perf_counter() - stage_start) * 1000, 2)
    defects_count = sum(1 for r in executed_results if r.get("has_defect"))
    failures_count = sum(1 for r in executed_results if r.get("failed"))

    summary_data = {
        "total_rois_executed": len(executed_results),
        "defects_detected": defects_count,
        "agent_failures": failures_count,
        "execution_time_ms": total_time_ms,
        "results": executed_results,
    }

    logger.info(
        "Stage 5 Evidence Execution completed: %d ROIs analyzed, %d defects detected, %d failures in %.1fms",
        len(executed_results),
        defects_count,
        failures_count,
        total_time_ms,
    )

    return await state.record_stage(
        StageResult(
            stage=PipelineStageName.EVIDENCE_EXECUTION,
            status="passed",
            data=summary_data,
        )
    )
