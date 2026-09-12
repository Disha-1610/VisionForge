# backend/tests/test_judge_and_policy.py
import uuid
import pytest
from app.models.inspection import PolicyAction
from app.pipeline.stages.judge import run_judge
from app.pipeline.stages.policy_engine import run_policy_engine
from app.pipeline.state import InspectionState
from app.shared.evidence_store import EvidenceStore
from app.shared.memory import PipelineStageName, StageResult, WorkingMemory


@pytest.fixture
def base_state():
    insp_id = uuid.uuid4()
    mem = WorkingMemory(
        inspection_id=insp_id,
        part_code="MCU-V2",
        product_type="Motherboard",
        quality_passed=True,
        authenticity_score=0.95,
        authenticity_flagged=False,
        similarity_score=0.92,
    )
    store = EvidenceStore()
    return InspectionState(memory=mem, evidence=store)


@pytest.mark.asyncio
async def test_judge_offline_clean_verdict(base_state):
    await base_state.memory.update(
        fraud_probability=0.05,
        fraud_category="clean",
        fused_evidence={"fraud_score": 5.0, "detected_issues": [], "primary_category": "clean"},
    )

    res = await run_judge(base_state)
    assert res.stage == PipelineStageName.JUDGE
    assert res.status == "passed"
    assert res.data["verdict"] == "accept"
    assert base_state.memory.judge_confidence >= 0.80
    assert len(base_state.memory.root_cause) > 10


@pytest.mark.asyncio
async def test_judge_offline_critical_reject_verdict(base_state):
    await base_state.memory.update(
        fraud_probability=0.85,
        fraud_category="missing_components",
        fused_evidence={
            "fraud_score": 85.0,
            "detected_issues": ["missing_components:2", "ssim_drift"],
            "primary_category": "missing_components",
        },
    )

    res = await run_judge(base_state)
    assert res.stage == PipelineStageName.JUDGE
    assert res.status == "flagged"
    assert res.data["verdict"] == "reject"
    assert base_state.memory.judge_confidence >= 0.80
    assert len(res.data["recommendations"]) > 0


@pytest.mark.asyncio
async def test_judge_offline_fallback_when_api_fails(base_state):
    from unittest.mock import patch
    await base_state.memory.update(
        fraud_probability=0.05,
        fraud_category="clean",
        fused_evidence={"fraud_score": 5.0, "detected_issues": [], "primary_category": "clean"},
    )
    with patch("app.shared.llm_client.LLMClient.generate_json", side_effect=RuntimeError("API Network Down")):
        res = await run_judge(base_state)
        assert res.status == "passed"
        assert res.data["verdict"] == "accept"
        assert res.data["used_offline_fallback"] is True
        assert "tolerance" in base_state.memory.root_cause.lower()


@pytest.mark.asyncio
async def test_policy_engine_accept(base_state):
    await base_state.memory.update(
        quality_passed=True,
        fraud_probability=0.10,
        fraud_category="clean",
    )
    res = await run_policy_engine(base_state)
    assert res.status == "passed"
    assert base_state.memory.policy_action == PolicyAction.ACCEPT.value


@pytest.mark.asyncio
async def test_policy_engine_retake_on_quality_failure(base_state):
    await base_state.memory.update(quality_passed=False)
    await base_state.record_stage(
        StageResult(
            stage=PipelineStageName.QUALITY_CHECK,
            status="failed",
            error="Image blurry, laplacian variance 42.1 < 100.0",
        )
    )

    res = await run_policy_engine(base_state)
    assert res.status == "flagged"
    assert base_state.memory.policy_action == PolicyAction.RETAKE.value
    assert "blurry" in res.data["explanation"].lower()


@pytest.mark.asyncio
async def test_policy_engine_quarantine_on_high_fraud(base_state):
    await base_state.memory.update(
        quality_passed=True,
        fraud_probability=0.78,
        fraud_category="counterfeit_rework",
    )
    await base_state.record_stage(
        StageResult(
            stage=PipelineStageName.JUDGE,
            status="flagged",
            data={"verdict": "reject", "confidence": 0.90},
        )
    )

    res = await run_policy_engine(base_state)
    assert res.status == "flagged"
    assert base_state.memory.policy_action == PolicyAction.QUARANTINE.value


@pytest.mark.asyncio
async def test_policy_engine_vendor_verification_on_borderline(base_state):
    await base_state.memory.update(
        quality_passed=True,
        fraud_probability=0.45,
        fraud_category="structural_defect",
    )
    await base_state.record_stage(
        StageResult(
            stage=PipelineStageName.JUDGE,
            status="flagged",
            data={"verdict": "review", "confidence": 0.75},
        )
    )

    res = await run_policy_engine(base_state)
    assert res.data["policy_action"] == PolicyAction.VENDOR_VERIFICATION.value
    assert base_state.memory.policy_action == PolicyAction.VENDOR_VERIFICATION.value
