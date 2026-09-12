# backend/tests/test_week3_integration.py
"""
Week 3 Integration Tests (Anil & Disha, W3 D6).

Validates end-to-end integration across Stages 4 and 5:
  Stage 4: ROI Scheduler (pure logic, priority grouping, agent routing)
  Stage 5: Evidence Execution (parallel batch dispatch, paired ROI cropping,
           all 4 agents: OCR, Label, Structural+YOLO, VLM, and EvidenceStore audit trail).
"""
from __future__ import annotations

import uuid
from typing import Any

from PIL import Image
import pytest

from app.pipeline.agents.base_agent import AgentResult, BaseAgent
from app.pipeline.agents.label_agent import LabelAgent
from app.pipeline.agents.ocr_agent import OCRAgent
from app.pipeline.agents.structural_agent import StructuralAgent
from app.pipeline.agents.vlm_agent import VLMAgent, VLMAnomalyReport
from app.pipeline.stages.evidence_execution import (
    get_default_agent_registry,
    run_evidence_execution,
)
from app.pipeline.stages.roi_scheduler import run_roi_scheduler
from app.pipeline.state import STAGE_ORDER, InspectionState
from app.shared.evidence_store import AgentType, EvidenceStore
from app.shared.llm_client import FinishReason, LLMProvider, LLMResponse
from app.shared.memory import PipelineStageName, WorkingMemory
from app.utils.roi_templates import ProductType, load_roi_template


class _MockLLMClientForIntegration:
    async def generate_json(self, request, response_model):
        report = VLMAnomalyReport(
            has_defect=False,
            defect_type="none",
            confidence=0.93,
            severity="none",
            description="Integration test visual check normal",
        )
        fake_resp = LLMResponse(
            provider=LLMProvider.GEMINI,
            model="gemini-3.5-flash",
            content=report.model_dump_json(),
            finish_reason=FinishReason.STOP,
            latency_ms=130.0,
            attempt=1,
            used_fallback=False,
        )
        return fake_resp, report



class _MockOCRReader:
    def readtext(self, img):
        return [([[0, 0], [10, 0], [10, 10], [0, 10]], "PCB-MCU-V2-SN", 0.98)]


@pytest.mark.asyncio
async def test_week3_stages_4_and_5_all_4_agents_end_to_end():
    # 1. Initialize State
    inspection_id = uuid.uuid4()
    memory = WorkingMemory(
        inspection_id=inspection_id,
        quality_passed=True,
        part_code="PCB-MCU-V2",
        product_type="motherboard",
    )
    store = EvidenceStore()
    state = InspectionState(memory=memory, evidence=store)

    # 2. Stage 4: ROI Scheduler
    template = await load_roi_template(ProductType.MOTHERBOARD, "PCB-MCU-V2")
    sched_result = await run_roi_scheduler(state, template=template)

    assert sched_result.status == "passed"
    assert sched_result.stage == PipelineStageName.ROI_SCHEDULER
    assert state.memory.roi_template is not None
    assert len(state.memory.roi_execution_plan) > 0

    # 3. Setup 4-agent Registry with deterministic test mocks
    ocr_agent = OCRAgent(reader=_MockOCRReader())
    label_agent = LabelAgent()
    structural_agent = StructuralAgent(enable_yolo=False, default_threshold=0.80)
    vlm_agent = VLMAgent(client=_MockLLMClientForIntegration())

    four_agent_registry = {
        AgentType.OCR: ocr_agent,
        AgentType.LABEL: label_agent,
        AgentType.STRUCTURAL: structural_agent,
        AgentType.VLM: vlm_agent,
    }

    # 4. Create synthetic Golden & Inspection Images matching reference dimensions
    golden_img = Image.new(
        "RGB",
        (template.reference_image_width, template.reference_image_height),
        color=(140, 140, 140),
    )
    inspection_img = golden_img.copy()

    # 5. Stage 5: Evidence Execution
    exec_result = await run_evidence_execution(
        state=state,
        agent_registry=four_agent_registry,
        golden_image=golden_img,
        inspection_image=inspection_img,
    )

    # 6. Verify Stage 5 Result & Metrics
    assert exec_result.status == "passed"
    assert exec_result.stage == PipelineStageName.EVIDENCE_EXECUTION
    assert exec_result.data["total_rois_executed"] == len(template.regions)
    assert exec_result.data["agent_failures"] == 0

    # 7. Verify All 4 Agents Recorded Evidence into EvidenceStore
    records = state.evidence.get_all_for_inspection(inspection_id)
    assert len(records) == len(template.regions)
    assert len(state.memory.evidence_refs) == len(template.regions)

    recorded_agent_types = set(r.agent_type for r in records)
    assert AgentType.OCR in recorded_agent_types
    assert AgentType.LABEL in recorded_agent_types
    assert AgentType.STRUCTURAL in recorded_agent_types
    assert AgentType.VLM in recorded_agent_types

    # 8. Verify SSE Telemetry Progress tracks stage
    progress = state.progress()
    assert progress["progress"] == 2  # Stage 4 and Stage 5 recorded
    assert progress["status"] == "in_progress"

