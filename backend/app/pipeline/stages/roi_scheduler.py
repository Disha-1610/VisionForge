# backend/app/pipeline/stages/roi_scheduler.py
"""
Stage 4 — ROI Scheduler (Anil, W3 D1).

Pure Python deterministic scheduling logic (no AI model).
Per VisionForge.md Section 4, Stage 4:
  - Reads the ROI template for the matched golden reference.
  - Identifies inspection type required for each ROI (Text -> OCR, Label -> Label,
    Structural -> Structural, Visual -> VLM).
  - Groups same-type ROIs into execution batches.
  - Prioritizes critical ROIs (serial numbers, security labels, QC seals)
    before non-critical ones.
  - Produces an execution plan (ROI -> agent mapping) and stores it in
    WorkingMemory / StageResult for Stage 5 (Evidence Execution).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import GoldenReference
from app.pipeline.state import InspectionState
from app.shared.memory import PipelineStageName, StageResult
from app.utils.roi_templates import (
    DEFAULT_ROI_TEMPLATE_DIR,
    ProductType,
    ROIExecutionPlan,
    ROITemplate,
    ROITemplateError,
    create_execution_plan,
    load_roi_template,
)

logger = logging.getLogger("app.pipeline.roi_scheduler")


def infer_product_type(part_code: str) -> ProductType:
    """
    Infer the product type from a part code or part ID prefix/substring.
    Handles known product families:
      - PCB / MCU / MOTHERBOARD -> ProductType.MOTHERBOARD
      - BAT / BATTERY -> ProductType.BATTERY
      - RAM / DDR / MEMORY -> ProductType.RAM
    """
    code = part_code.strip().upper()
    if any(k in code for k in ("PCB", "MCU", "MOTHERBOARD", "MB")):
        return ProductType.MOTHERBOARD
    if any(k in code for k in ("BAT", "BATTERY", "CELL")):
        return ProductType.BATTERY
    if any(k in code for k in ("RAM", "DDR", "DIMM", "SODIMM")):
        return ProductType.RAM

    # Default fallback to motherboard if unrecognized
    return ProductType.MOTHERBOARD


async def resolve_roi_template(
    state: InspectionState,
    db: AsyncSession | None = None,
    base_dir: Path = DEFAULT_ROI_TEMPLATE_DIR,
    template: ROITemplate | None = None,
) -> ROITemplate:
    """
    Resolve the ROITemplate for the current inspection state.

    Resolution precedence:
      1. Explicit `template` argument (e.g. testing or explicit injection).
      2. `state.memory.roi_template` (dict in working memory).
      3. `GoldenReference` looked up via `state.memory.golden_reference_id` from DB.
      4. `state.memory.part_code` / `product_type` in working memory.
    """
    if template is not None:
        return template

    if state.memory.roi_template:
        try:
            return ROITemplate.model_validate(state.memory.roi_template)
        except Exception as exc:
            logger.warning("Failed parsing roi_template from memory: %s", exc)

    part_code: str | None = state.memory.part_code
    product_type: ProductType | None = (
        ProductType(state.memory.product_type) if state.memory.product_type else None
    )

    if db is not None and state.memory.golden_reference_id is not None:
        result = await db.execute(
            select(GoldenReference).where(GoldenReference.id == state.memory.golden_reference_id)
        )
        golden = result.scalar_one_or_none()
        if golden is not None:
            if not part_code:
                part_code = golden.part_id
            if not product_type:
                # Check meta first if present
                meta = golden.meta or {}
                if meta.get("product_type"):
                    try:
                        product_type = ProductType(meta["product_type"].lower())
                    except ValueError:
                        pass
                if not product_type:
                    product_type = infer_product_type(golden.part_id)

    if not part_code:
        raise ROITemplateError(
            "No part_code or golden reference found in InspectionState to resolve ROI template"
        )

    if not product_type:
        product_type = infer_product_type(part_code)

    return await load_roi_template(
        product_type=product_type,
        part_code=part_code,
        base_dir=base_dir,
    )


async def run_roi_scheduler(
    state: InspectionState,
    db: AsyncSession | None = None,
    base_dir: Path = DEFAULT_ROI_TEMPLATE_DIR,
    template: ROITemplate | None = None,
) -> StageResult:
    """
    Stage 4 entrypoint — ROI Scheduler.

    Reads ROI template, builds the execution plan with agent routing and
    priority ordering, stores plan into WorkingMemory, and records StageResult.
    """
    # 1. Quality gate check
    if state.memory.quality_passed is False:
        detail = {"reason": "quality_check_failed"}
        return await state.record_stage(
            StageResult(
                stage=PipelineStageName.ROI_SCHEDULER,
                status="failed",
                data=detail,
                error="Quality check failed in Stage 1; ROI scheduling skipped",
            )
        )

    # 2. Resolve template
    try:
        loaded_template = await resolve_roi_template(
            state=state,
            db=db,
            base_dir=base_dir,
            template=template,
        )
    except Exception as exc:
        logger.error("Failed resolving ROI template: %s", exc)
        return await state.record_stage(
            StageResult(
                stage=PipelineStageName.ROI_SCHEDULER,
                status="failed",
                data={"error_type": type(exc).__name__},
                error=f"Could not load ROI template: {exc}",
            )
        )

    # 3. Create execution plan
    try:
        plan: ROIExecutionPlan = create_execution_plan(loaded_template)
    except Exception as exc:
        logger.error("Failed creating execution plan from template %s: %s", loaded_template.id, exc)
        return await state.record_stage(
            StageResult(
                stage=PipelineStageName.ROI_SCHEDULER,
                status="failed",
                data={"template_id": loaded_template.id},
                error=f"Failed creating execution plan: {exc}",
            )
        )

    # 4. Serialize plan and update WorkingMemory
    plan_batches_data = [b.model_dump() for b in plan.batches]
    plan_items_data = [item.model_dump() for item in plan.items]
    template_data = loaded_template.model_dump(by_alias=True)

    await state.memory.update(
        part_code=loaded_template.part_code,
        product_type=loaded_template.product_type.value,
        roi_template=template_data,
        roi_execution_plan=plan_batches_data,
    )

    detail: dict[str, Any] = {
        "template_id": loaded_template.id,
        "product_type": loaded_template.product_type.value,
        "part_code": loaded_template.part_code,
        "total_rois": len(loaded_template.regions),
        "total_batches": len(plan.batches),
        "items": plan_items_data,
        "batches": plan_batches_data,
    }

    logger.info(
        "Stage 4 ROI Scheduler passed: template=%s, %d ROIs across %d batches",
        loaded_template.id,
        len(loaded_template.regions),
        len(plan.batches),
    )

    return await state.record_stage(
        StageResult(
            stage=PipelineStageName.ROI_SCHEDULER,
            status="passed",
            data=detail,
        )
    )
