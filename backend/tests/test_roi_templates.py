# backend/tests/test_roi_templates.py
"""
ROI template validation + execution plan tests (Disha, W2 D6).

Verifies:
  - JSON templates load and validate against the Pydantic schema
  - ROI→Agent routing table is correct per VisionForge.md Stage 4
  - Execution plan generation groups ROIs by agent with priority ordering
  - Edge cases: missing files, malformed JSON, duplicate ROI IDs, out-of-bounds bbox
"""
from __future__ import annotations

import json
import pathlib

import pytest

from app.utils.roi_templates import (
    AgentType,
    ROITemplate,
    ROITemplateError,
    ROITemplateNotFoundError,
    ROITemplateValidationError,
    ROIType,
    ROI_TYPE_TO_AGENT,
    clear_roi_template_cache,
    create_execution_plan,
    get_roi_by_id,
    get_rois_by_agent,
    get_rois_by_priority,
    load_roi_template,
    ProductType,
    validate_roi_template,
)

TEMPLATE_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "data" / "roi_templates"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clear_cache():
    """Ensure LRU cache is clean between tests."""
    clear_roi_template_cache()
    yield
    clear_roi_template_cache()


# ── ROI Type → Agent Routing ──────────────────────────────────────────────────

def test_roi_type_to_agent_routing_table():
    """The routing table must match VisionForge.md Stage 4 spec."""
    assert ROI_TYPE_TO_AGENT[ROIType.TEXT] == AgentType.OCR
    assert ROI_TYPE_TO_AGENT[ROIType.LABEL] == AgentType.LABEL
    assert ROI_TYPE_TO_AGENT[ROIType.STRUCTURAL] == AgentType.STRUCTURAL
    assert ROI_TYPE_TO_AGENT[ROIType.VISUAL] == AgentType.VLM


# ── Template Loading (from disk) ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_load_motherboard_template():
    template = await load_roi_template(ProductType.MOTHERBOARD, "PCB-MCU-V2", TEMPLATE_DIR)
    assert template.product_type == ProductType.MOTHERBOARD
    assert template.part_code == "PCB-MCU-V2"
    assert len(template.regions) >= 1
    assert any(r.type == ROIType.TEXT for r in template.regions)


@pytest.mark.asyncio
async def test_load_battery_template():
    template = await load_roi_template(ProductType.BATTERY, "BAT-STD-V1", TEMPLATE_DIR)
    assert template.product_type == ProductType.BATTERY
    assert len(template.regions) >= 1


@pytest.mark.asyncio
async def test_load_ram_template():
    template = await load_roi_template(ProductType.RAM, "RAM-DDR4-V1", TEMPLATE_DIR)
    assert template.product_type == ProductType.RAM
    assert len(template.regions) >= 1


@pytest.mark.asyncio
async def test_load_nonexistent_template_raises():
    with pytest.raises(ROITemplateNotFoundError):
        await load_roi_template(ProductType.MOTHERBOARD, "DOES-NOT-EXIST", TEMPLATE_DIR)


# ── Template Validation ──────────────────────────────────────────────────────

def test_valid_template_constructs():
    """A minimal valid template should construct without errors."""
    raw = {
        "id": "test-template-1",
        "productType": "motherboard",
        "partCode": "TEST-001",
        "version": 1,
        "coordinateSystem": "pixel",
        "referenceImageWidth": 800,
        "referenceImageHeight": 600,
        "regions": [
            {
                "id": "serial",
                "name": "Serial Number",
                "type": "text",
                "bbox": {"x": 10, "y": 10, "width": 200, "height": 50},
                "agent": "ocr",
                "priority": "critical",
            }
        ],
    }
    template = ROITemplate.model_validate(raw)
    assert template.part_code == "TEST-001"
    assert len(template.regions) == 1


def test_template_rejects_duplicate_region_ids():
    """Duplicate ROI IDs must fail validation."""
    raw = {
        "id": "test-dup",
        "productType": "battery",
        "partCode": "DUP-001",
        "version": 1,
        "coordinateSystem": "pixel",
        "referenceImageWidth": 400,
        "referenceImageHeight": 300,
        "regions": [
            {
                "id": "serial",
                "name": "Serial 1",
                "type": "text",
                "bbox": {"x": 0, "y": 0, "width": 100, "height": 30},
                "agent": "ocr",
                "priority": "critical",
            },
            {
                "id": "serial",
                "name": "Serial 2",
                "type": "label",
                "bbox": {"x": 0, "y": 0, "width": 100, "height": 30},
                "agent": "label",
                "priority": "normal",
            },
        ],
    }
    with pytest.raises(Exception):
        ROITemplate.model_validate(raw)


def test_template_rejects_bbox_exceeding_image_bounds():
    """Bounding box that goes outside the reference image must fail."""
    raw = {
        "id": "test-oob",
        "productType": "ram",
        "partCode": "OOB-001",
        "version": 1,
        "coordinateSystem": "pixel",
        "referenceImageWidth": 400,
        "referenceImageHeight": 300,
        "regions": [
            {
                "id": "out-of-bounds",
                "name": "OOB Region",
                "type": "structural",
                "bbox": {"x": 350, "y": 280, "width": 100, "height": 100},
                "agent": "structural",
                "priority": "normal",
            }
        ],
    }
    with pytest.raises(Exception):
        ROITemplate.model_validate(raw)


def test_template_rejects_agent_type_mismatch():
    """text ROI must route to OCR agent, not structural."""
    raw = {
        "id": "test-mismatch",
        "productType": "motherboard",
        "partCode": "MIS-001",
        "version": 1,
        "coordinateSystem": "pixel",
        "referenceImageWidth": 800,
        "referenceImageHeight": 600,
        "regions": [
            {
                "id": "wrong-agent",
                "name": "Wrong Agent",
                "type": "text",
                "bbox": {"x": 0, "y": 0, "width": 100, "height": 30},
                "agent": "structural",
                "priority": "normal",
            }
        ],
    }
    with pytest.raises(Exception):
        ROITemplate.model_validate(raw)


# ── Execution Plan ────────────────────────────────────────────────────────────

def _make_template():
    """Helper: a 4-ROI template with mixed types and priorities."""
    return ROITemplate(
        id="plan-test",
        product_type=ProductType.MOTHERBOARD,
        part_code="PLAN-001",
        version=1,
        coordinate_system="pixel",
        reference_image_width=800,
        reference_image_height=600,
        regions=[
            {
                "id": "serial",
                "name": "Serial",
                "type": "text",
                "bbox": {"x": 0, "y": 0, "width": 200, "height": 50},
                "agent": "ocr",
                "priority": "critical",
            },
            {
                "id": "qc_seal",
                "name": "QC Seal",
                "type": "label",
                "bbox": {"x": 400, "y": 0, "width": 100, "height": 100},
                "agent": "label",
                "priority": "critical",
            },
            {
                "id": "caps",
                "name": "Capacitors",
                "type": "structural",
                "bbox": {"x": 100, "y": 200, "width": 200, "height": 150},
                "agent": "structural",
                "priority": "high",
            },
            {
                "id": "surface",
                "name": "Surface Check",
                "type": "visual",
                "bbox": {"x": 0, "y": 0, "width": 800, "height": 600},
                "agent": "vlm",
                "priority": "normal",
            },
        ],
    )


def test_execution_plan_groups_by_agent():
    template = _make_template()
    plan = create_execution_plan(template)

    assert plan.template_id == "plan-test"
    assert len(plan.items) == 4
    assert len(plan.batches) == 4  # 4 different agents

    batch_agents = [b.agent for b in plan.batches]
    assert AgentType.OCR in batch_agents
    assert AgentType.LABEL in batch_agents
    assert AgentType.STRUCTURAL in batch_agents
    assert AgentType.VLM in batch_agents


def test_execution_plan_orders_by_priority():
    template = _make_template()
    plan = create_execution_plan(template)

    # Items should be ordered: critical first, then high, then normal
    priorities = [item.priority.value for item in plan.items]
    assert priorities == ["critical", "critical", "high", "normal"]


def test_execution_plan_batches_ordered_by_priority():
    template = _make_template()
    plan = create_execution_plan(template)

    batch_priorities = [b.priority.value for b in plan.batches]
    # critical batches first
    assert batch_priorities[0] == "critical"
    assert batch_priorities[-1] == "normal"


# ── ROI Query Helpers ─────────────────────────────────────────────────────────

def test_get_rois_by_priority_sorts_correctly():
    template = _make_template()
    sorted_rois = get_rois_by_priority(template)
    assert sorted_rois[0].priority.value == "critical"
    assert sorted_rois[-1].priority.value == "normal"


def test_get_rois_by_agent_filters_correctly():
    template = _make_template()
    ocr_rois = get_rois_by_agent(template, AgentType.OCR)
    assert len(ocr_rois) == 1
    assert ocr_rois[0].id == "serial"


def test_get_roi_by_id_found():
    template = _make_template()
    roi = get_roi_by_id(template, "caps")
    assert roi is not None
    assert roi.name == "Capacitors"


def test_get_roi_by_id_not_found():
    template = _make_template()
    roi = get_roi_by_id(template, "nonexistent")
    assert roi is None


# ── Raw JSON Template Files Validate ─────────────────────────────────────────

@pytest.mark.parametrize(
    "filename,expected_part",
    [
        ("motherboard_pcb_mcu_v2.json", "PCB-MCU-V2"),
        ("battery_bat_std_v1.json", "BAT-STD-V1"),
        ("ram_ddr4_v1.json", "RAM-DDR4-V1"),
    ],
)
def test_json_template_files_validate(filename, expected_part):
    """Every JSON template on disk must validate against the Pydantic model."""
    path = TEMPLATE_DIR / filename
    raw = json.loads(path.read_text(encoding="utf-8"))
    template = ROITemplate.model_validate(raw)
    assert template.part_code == expected_part

    # Every region must have a valid agent assignment
    for region in template.regions:
        expected_agent = ROI_TYPE_TO_AGENT[region.type]
        assert region.agent == expected_agent
