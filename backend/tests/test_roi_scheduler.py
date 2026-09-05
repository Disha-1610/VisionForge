# backend/tests/test_roi_scheduler.py
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.models.product import GoldenReference
from app.pipeline.stages.roi_scheduler import (
    infer_product_type,
    resolve_roi_template,
    run_roi_scheduler,
)
from app.pipeline.state import InspectionState
from app.shared.evidence_store import EvidenceStore
from app.shared.memory import PipelineStageName, WorkingMemory
from app.utils.roi_templates import (
    ProductType,
    ROIPriority,
    load_roi_template,
)


def _make_state(
    *,
    inspection_id: uuid.UUID | None = None,
    quality_passed: bool = True,
    part_code: str | None = None,
    product_type: str | None = None,
    golden_ref_id: uuid.UUID | None = None,
) -> InspectionState:
    iid = inspection_id or uuid.uuid4()
    mem = WorkingMemory(
        inspection_id=iid,
        quality_passed=quality_passed,
        part_code=part_code,
        product_type=product_type,
        golden_reference_id=golden_ref_id,
    )
    store = EvidenceStore()
    return InspectionState(memory=mem, evidence=store)


class _FakeScalar:
    def __init__(self, value):
        self._val = value

    def scalar_one_or_none(self):
        return self._val


class _FakeDB:
    def __init__(self, golden):
        self.golden = golden

    async def execute(self, _query):
        return _FakeScalar(self.golden)


def test_infer_product_type():
    assert infer_product_type("PCB-MCU-V2") == ProductType.MOTHERBOARD
    assert infer_product_type("MOTHERBOARD_X") == ProductType.MOTHERBOARD
    assert infer_product_type("BAT-STD-V1") == ProductType.BATTERY
    assert infer_product_type("LITHIUM_CELL_9") == ProductType.BATTERY
    assert infer_product_type("RAM-DDR4-V1") == ProductType.RAM
    assert infer_product_type("SODIMM-8GB") == ProductType.RAM
    # fallback
    assert infer_product_type("GENERIC-DEVICE") == ProductType.MOTHERBOARD


@pytest.mark.asyncio
async def test_run_roi_scheduler_with_explicit_template():
    template = await load_roi_template(ProductType.MOTHERBOARD, "PCB-MCU-V2")
    state = _make_state(quality_passed=True)

    result = await run_roi_scheduler(state, template=template)

    assert result.status == "passed"
    assert result.stage == PipelineStageName.ROI_SCHEDULER
    assert result.data["template_id"] == template.id
    assert result.data["total_rois"] == len(template.regions)
    assert len(result.data["batches"]) > 0

    # WorkingMemory updated
    assert state.memory.roi_template is not None
    assert state.memory.roi_template["id"] == template.id
    assert len(state.memory.roi_execution_plan) == len(result.data["batches"])
    assert state.memory.part_code == template.part_code
    assert state.memory.product_type == template.product_type.value

    # First batch has critical priority
    assert result.data["batches"][0]["priority"] == ROIPriority.CRITICAL.value


@pytest.mark.asyncio
async def test_run_roi_scheduler_from_memory_part_code():
    state = _make_state(
        quality_passed=True,
        part_code="BAT-STD-V1",
        product_type=ProductType.BATTERY.value,
    )

    result = await run_roi_scheduler(state)

    assert result.status == "passed"
    assert result.data["part_code"] == "BAT-STD-V1"
    assert result.data["product_type"] == ProductType.BATTERY.value
    assert state.memory.roi_template["productType"] == ProductType.BATTERY.value


@pytest.mark.asyncio
async def test_run_roi_scheduler_from_db_golden_reference():
    golden_id = uuid.uuid4()
    golden = GoldenReference(
        id=golden_id,
        part_id="RAM-DDR4-V1",
        part_name="DDR4 16GB RAM",
        image_path="data/golden_images/ram.jpg",
        view_angle="front",
        meta={"product_type": "ram"},
    )
    fake_db = _FakeDB(golden)
    state = _make_state(quality_passed=True, golden_ref_id=golden_id)

    result = await run_roi_scheduler(state, db=fake_db)

    assert result.status == "passed"
    assert result.data["part_code"] == "RAM-DDR4-V1"
    assert result.data["product_type"] == ProductType.RAM.value
    assert state.memory.part_code == "RAM-DDR4-V1"


@pytest.mark.asyncio
async def test_run_roi_scheduler_quality_failed_skips():
    state = _make_state(quality_passed=False, part_code="PCB-MCU-V2")

    result = await run_roi_scheduler(state)

    assert result.status == "failed"
    assert "Quality check failed" in (result.error or "")
    assert len(state.memory.roi_execution_plan) == 0


@pytest.mark.asyncio
async def test_run_roi_scheduler_missing_template_fails():
    state = _make_state(quality_passed=True, part_code="NON-EXISTENT-PART-XYZ")

    result = await run_roi_scheduler(state)

    assert result.status == "failed"
    assert "Could not load ROI template" in (result.error or "")


@pytest.mark.asyncio
async def test_run_roi_scheduler_priority_ordering():
    template = await load_roi_template(ProductType.MOTHERBOARD, "PCB-MCU-V2")
    state = _make_state(quality_passed=True)

    result = await run_roi_scheduler(state, template=template)
    items = result.data["items"]
    batches = result.data["batches"]

    # Critical items must come first
    priorities = [item["priority"] for item in items]
    crit_indices = [i for i, p in enumerate(priorities) if p == "critical"]
    norm_indices = [i for i, p in enumerate(priorities) if p == "normal"]

    if crit_indices and norm_indices:
        assert max(crit_indices) < min(norm_indices)

    # Batches must also be ordered critical first
    assert batches[0]["priority"] == "critical"
