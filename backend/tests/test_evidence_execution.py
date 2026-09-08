# backend/tests/test_evidence_execution.py
from __future__ import annotations

import uuid
from typing import Any

import numpy as np
from PIL import Image
import pytest

from app.pipeline.agents.base_agent import AgentResult, BaseAgent
from app.pipeline.stages.evidence_execution import run_evidence_execution
from app.pipeline.stages.roi_scheduler import run_roi_scheduler
from app.pipeline.state import InspectionState
from app.shared.evidence_store import AgentType, EvidenceStore
from app.shared.memory import PipelineStageName, WorkingMemory
from app.utils.roi_templates import ProductType, load_roi_template


class _MockAgent(BaseAgent):
    def __init__(self, agent_type: AgentType, has_defect: bool = False, fail: bool = False) -> None:
        super().__init__(detector_name=f"mock_{agent_type.value}")
        self.agent_type = agent_type
        self._has_defect = has_defect
        self._fail = fail

    async def _analyze(
        self,
        golden_roi: Any,
        inspection_roi: Any,
        roi_data: dict[str, Any],
    ) -> AgentResult:
        if self._fail:
            raise RuntimeError(f"Simulated failure in {self.detector_name}")

        roi_id = str(roi_data.get("roi_id") or "mock_roi")
        return AgentResult(
            agent_type=self.agent_type,
            detector_name=self.detector_name,
            roi_id=roi_id,
            confidence=0.95 if not self._has_defect else 0.88,
            has_defect=self._has_defect,
            evidence={"mock": True, "roi_id": roi_id},
            explanation=f"Mock analysis on {roi_id}",
        )


def _make_state(
    *,
    quality_passed: bool = True,
    part_code: str | None = "PCB-MCU-V2",
    product_type: str | None = "motherboard",
) -> InspectionState:
    iid = uuid.uuid4()
    mem = WorkingMemory(
        inspection_id=iid,
        quality_passed=quality_passed,
        part_code=part_code,
        product_type=product_type,
    )
    store = EvidenceStore()
    return InspectionState(memory=mem, evidence=store)


@pytest.mark.asyncio
async def test_evidence_execution_quality_gate():
    state = _make_state(quality_passed=False)
    result = await run_evidence_execution(state)

    assert result.status == "failed"
    assert result.stage == PipelineStageName.EVIDENCE_EXECUTION
    assert "quality_check_failed" in str(result.data)


@pytest.mark.asyncio
async def test_evidence_execution_missing_template_in_memory():
    state = _make_state(quality_passed=True)
    # No Stage 4 run, roi_template is None
    result = await run_evidence_execution(state)

    assert result.status == "failed"
    assert "No roi_template found" in (result.error or "")


@pytest.mark.asyncio
async def test_evidence_execution_end_to_end_with_mock_agents():
    # 1. Prepare template and run Stage 4 (ROI Scheduler)
    template = await load_roi_template(ProductType.MOTHERBOARD, "PCB-MCU-V2")
    state = _make_state(quality_passed=True)
    sched_result = await run_roi_scheduler(state, template=template)
    assert sched_result.status == "passed"

    # 2. Prepare mock agents for Stage 5
    mock_registry = {
        AgentType.OCR: _MockAgent(AgentType.OCR, has_defect=False),
        AgentType.LABEL: _MockAgent(AgentType.LABEL, has_defect=False),
        AgentType.STRUCTURAL: _MockAgent(AgentType.STRUCTURAL, has_defect=True),  # 1 agent finds defect
        AgentType.VLM: _MockAgent(AgentType.VLM, has_defect=False),
    }


    # Synthetic reference image
    img = Image.new("RGB", (template.reference_image_width, template.reference_image_height), (120, 120, 120))

    # 3. Run Stage 5 Evidence Execution
    stage_res = await run_evidence_execution(
        state=state,
        agent_registry=mock_registry,
        golden_image=img,
        inspection_image=img,
    )

    # 4. Assert stage result
    assert stage_res.status == "passed"
    assert stage_res.stage == PipelineStageName.EVIDENCE_EXECUTION
    assert stage_res.data["total_rois_executed"] == len(template.regions)
    assert stage_res.data["defects_detected"] > 0
    assert stage_res.data["agent_failures"] == 0

    # 5. Assert EvidenceStore audit trail populated
    evidence_records = state.evidence.get_all_for_inspection(state.memory.inspection_id)
    assert len(evidence_records) == len(template.regions)
    assert len(state.memory.evidence_refs) == len(template.regions)

    # Check that structural evidence has defect recorded
    structural_records = [r for r in evidence_records if r.agent_type == AgentType.STRUCTURAL]
    assert len(structural_records) > 0
    for sr in structural_records:
        assert sr.evidence["has_defect"] is True


@pytest.mark.asyncio
async def test_evidence_execution_agent_failure_isolated():
    template = await load_roi_template(ProductType.MOTHERBOARD, "PCB-MCU-V2")
    state = _make_state(quality_passed=True)
    await run_roi_scheduler(state, template=template)

    # Make OCR agent fail
    mock_registry = {
        AgentType.OCR: _MockAgent(AgentType.OCR, fail=True),
        AgentType.LABEL: _MockAgent(AgentType.LABEL, has_defect=False),
        AgentType.STRUCTURAL: _MockAgent(AgentType.STRUCTURAL, has_defect=False),
    }

    img = Image.new("RGB", (template.reference_image_width, template.reference_image_height), (120, 120, 120))

    stage_res = await run_evidence_execution(
        state=state,
        agent_registry=mock_registry,
        golden_image=img,
        inspection_image=img,
    )

    # Stage should NOT crash — failures are recorded into evidence
    assert stage_res.status == "passed"
    assert stage_res.data["agent_failures"] > 0

    records = state.evidence.get_all_for_inspection(state.memory.inspection_id)
    failed_ocr_records = [r for r in records if r.agent_type == AgentType.OCR and r.failed]
    assert len(failed_ocr_records) > 0
    assert "Simulated failure" in (failed_ocr_records[0].failure_reason or "")

