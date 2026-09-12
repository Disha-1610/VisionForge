# backend/tests/test_workflow_langgraph.py
import uuid
import pytest
from unittest.mock import AsyncMock, patch

from app.models.inspection import PolicyAction
from app.pipeline.state import InspectionState
from app.pipeline.workflow import PipelineGraphState, pipeline_graph
from app.shared.evidence_store import EvidenceStore
from app.shared.memory import PipelineStageName, StageResult, WorkingMemory


@pytest.fixture
def mock_inspection_state():
    insp_id = uuid.uuid4()
    mem = WorkingMemory(
        inspection_id=insp_id,
        part_code="MCU-V2",
        product_type="Motherboard",
        image_paths=["data/test_data/sample.jpg"],
    )
    store = EvidenceStore()
    return InspectionState(memory=mem, evidence=store)


@pytest.mark.asyncio
async def test_langgraph_short_circuit_on_quality_failure(mock_inspection_state):
    """
    If Stage 1 (Quality Check) fails, the LangGraph conditional router
    should bypass Stages 2-7 directly to Stage 8 (Policy Engine) to issue RETAKE.
    """
    # Mock quality_check to fail
    async def mock_qc(state):
        await state.memory.update(quality_passed=False)
        return await state.record_stage(
            StageResult(
                stage=PipelineStageName.QUALITY_CHECK,
                status="failed",
                error="Image variance 32.0 below minimum 100.0 (too blurry)",
            )
        )

    with patch("app.pipeline.workflow.run_quality_check", side_effect=mock_qc):
        initial_payload: PipelineGraphState = {
            "inspection_id": str(mock_inspection_state.memory.inspection_id),
            "state": mock_inspection_state,
            "error": None,
        }
        res = await pipeline_graph.ainvoke(initial_payload)

        # Verify only Quality Check and Policy Engine ran
        stages_run = [r.stage for r in mock_inspection_state.memory.stage_history]
        assert PipelineStageName.QUALITY_CHECK in stages_run
        assert PipelineStageName.POLICY_ENGINE in stages_run
        assert PipelineStageName.AUTHENTICITY not in stages_run
        assert PipelineStageName.EVIDENCE_EXECUTION not in stages_run

        assert mock_inspection_state.memory.policy_action == PolicyAction.RETAKE.value


@pytest.mark.asyncio
async def test_langgraph_full_pipeline_flow(mock_inspection_state):
    """
    When Stage 1 passes, all 8 stages execute sequentially to completion.
    """
    async def mock_qc(state):
        await state.memory.update(quality_passed=True)
        return await state.record_stage(
            StageResult(stage=PipelineStageName.QUALITY_CHECK, status="passed")
        )

    async def mock_auth(state):
        await state.memory.update(authenticity_score=0.98, authenticity_flagged=False)
        return await state.record_stage(
            StageResult(stage=PipelineStageName.AUTHENTICITY, status="passed")
        )

    async def mock_ref(state):
        await state.memory.update(similarity_score=0.94)
        return await state.record_stage(
            StageResult(stage=PipelineStageName.REFERENCE_MATCH, status="passed")
        )

    async def mock_roi(state):
        return await state.record_stage(
            StageResult(stage=PipelineStageName.ROI_SCHEDULER, status="passed")
        )

    async def mock_exec(state):
        return await state.record_stage(
            StageResult(stage=PipelineStageName.EVIDENCE_EXECUTION, status="passed")
        )

    with (
        patch("app.pipeline.workflow.run_quality_check", side_effect=mock_qc),
        patch("app.pipeline.workflow.run_authenticity_stage", side_effect=mock_auth),
        patch("app.pipeline.workflow.run_reference_match", side_effect=mock_ref),
        patch("app.pipeline.workflow.run_roi_scheduler", side_effect=mock_roi),
        patch("app.pipeline.workflow.run_evidence_execution", side_effect=mock_exec),
    ):
        initial_payload: PipelineGraphState = {
            "inspection_id": str(mock_inspection_state.memory.inspection_id),
            "state": mock_inspection_state,
            "error": None,
        }
        await pipeline_graph.ainvoke(initial_payload)

        stages_run = [r.stage for r in mock_inspection_state.memory.stage_history]
        assert len(stages_run) == 8
        assert stages_run[-1] == PipelineStageName.POLICY_ENGINE
        assert mock_inspection_state.memory.policy_action in [p.value for p in PolicyAction]
