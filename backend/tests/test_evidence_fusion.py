# backend/tests/test_evidence_fusion.py
import uuid
import pytest
from app.pipeline.stages.evidence_fusion import run_evidence_fusion
from app.pipeline.state import InspectionState
from app.shared.evidence_store import AgentType, EvidenceStore
from app.shared.memory import PipelineStageName, WorkingMemory


@pytest.fixture
def clean_state():
    insp_id = uuid.uuid4()
    mem = WorkingMemory(
        inspection_id=insp_id,
        part_code="TEST-PART-1",
        product_type="Motherboard",
        authenticity_score=0.98,
        authenticity_flagged=False,
        similarity_score=0.95,
    )
    store = EvidenceStore()
    return InspectionState(memory=mem, evidence=store)


@pytest.mark.asyncio
async def test_evidence_fusion_empty_records(clean_state):
    res = await run_evidence_fusion(clean_state)
    assert res.stage == PipelineStageName.EVIDENCE_FUSION
    assert res.status == "passed"
    assert clean_state.memory.fraud_probability == 0.0
    assert clean_state.memory.fraud_category == "clean"


@pytest.mark.asyncio
async def test_evidence_fusion_clean_agents(clean_state):
    # Append clean structural and clean OCR evidence
    await clean_state.append_evidence(
        agent_type=AgentType.STRUCTURAL,
        roi_id="CPU_SOCKET",
        confidence=0.95,
        evidence={"match": True, "ssim": 0.98, "component_findings": {"missing": [], "extra": []}},
        explanation="Structural match confirmed with golden reference",
        processing_time_ms=12.0,
    )
    await clean_state.append_evidence(
        agent_type=AgentType.OCR,
        roi_id="SERIAL_LABEL",
        confidence=0.98,
        evidence={"match": True, "similarity": 1.0, "mismatches": []},
        explanation="Serial numbers match exactly",
        processing_time_ms=8.0,
    )

    res = await run_evidence_fusion(clean_state)
    assert res.status == "passed"
    assert clean_state.memory.fraud_probability < 0.20
    assert clean_state.memory.fraud_category == "clean"


@pytest.mark.asyncio
async def test_evidence_fusion_detects_missing_components(clean_state):
    # Append structural evidence with missing components
    await clean_state.append_evidence(
        agent_type=AgentType.STRUCTURAL,
        roi_id="CAPACITOR_BANK",
        confidence=0.92,
        evidence={
            "match": False,
            "ssim": 0.72,
            "component_findings": {
                "missing": [{"class_name": "capacitor", "expected": 4, "detected": 2}],
                "extra": [],
            },
        },
        explanation="2 capacitors missing from golden reference positions",
        processing_time_ms=15.0,
    )

    res = await run_evidence_fusion(clean_state)
    assert res.status == "flagged"
    assert clean_state.memory.fraud_probability >= 0.65
    assert clean_state.memory.fraud_category == "missing_components"


@pytest.mark.asyncio
async def test_evidence_fusion_detects_tampered_serial(clean_state):
    await clean_state.append_evidence(
        agent_type=AgentType.OCR,
        roi_id="BARCODE_SERIAL",
        confidence=0.94,
        evidence={
            "match": False,
            "similarity": 0.35,
            "mismatches": [
                {"type": "replace", "expected": "VF-SN-9999", "detected": "VF-CL-0000"}
            ],
        },
        explanation="Serial number mismatch detected",
        processing_time_ms=10.0,
    )

    res = await run_evidence_fusion(clean_state)
    assert res.status == "flagged"
    assert clean_state.memory.fraud_probability >= 0.60
    assert clean_state.memory.fraud_category == "tampered_serial"


@pytest.mark.asyncio
async def test_evidence_fusion_detects_vlm_critical_anomaly(clean_state):
    await clean_state.append_evidence(
        agent_type=AgentType.VLM,
        roi_id="IC_CHIP",
        confidence=0.90,
        evidence={
            "anomaly_detected": True,
            "severity": "critical",
            "defect_type": "burn_mark",
            "explanation": "Severe thermal burn damage on IC package",
        },
        explanation="Severe thermal burn damage detected by VLM",
        processing_time_ms=350.0,
    )

    res = await run_evidence_fusion(clean_state)
    assert res.status == "flagged"
    assert clean_state.memory.fraud_probability >= 0.60
    assert clean_state.memory.fraud_category == "visual_anomaly"
