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


@pytest.mark.asyncio
async def test_evidence_fusion_structural_agent_real_format(clean_state):
    """
    Verifies that evidence generated directly by StructuralAgent
    (list-based component_findings, ssim_score, missing_components)
    is correctly parsed by Evidence Fusion without errors.
    """
    await clean_state.append_evidence(
        agent_type=AgentType.STRUCTURAL,
        roi_id="IC_BANK",
        confidence=0.88,
        evidence={
            "ssim_score": 0.68,
            "threshold": 0.85,
            "match_status": "defect_detected",
            "component_findings": [
                {
                    "class_name": "ic_chip",
                    "golden_count": 2,
                    "inspection_count": 1,
                    "diff": -1,
                    "status": "missing",
                }
            ],
            "missing_components": ["missing:ic_chip(diff=-1)"],
            "extra_components": [],
        },
        explanation="Missing IC chip at golden location",
        processing_time_ms=45.0,
    )

    res = await run_evidence_fusion(clean_state)
    assert res.status == "flagged"
    assert clean_state.memory.fraud_probability >= 0.75
    assert clean_state.memory.fraud_category == "missing_components"


@pytest.mark.asyncio
async def test_evidence_fusion_vlm_agent_real_format(clean_state):
    """
    Verifies that evidence generated directly by VLMAgent
    (has_defect=True, severity, defect_type) is correctly parsed.
    """
    await clean_state.append_evidence(
        agent_type=AgentType.VLM,
        roi_id="CONNECTOR_HEADER",
        confidence=0.91,
        evidence={
            "has_defect": True,
            "defect_type": "physical_crack",
            "severity": "critical",
            "description": "Fractured solder joint and cracked PCB substrate",
            "affected_area": "pin_row_1",
            "vlm_confidence": 0.95,
        },
        explanation="Critical physical crack detected on connector",
        processing_time_ms=250.0,
    )

    res = await run_evidence_fusion(clean_state)
    assert res.status == "flagged"
    assert clean_state.memory.fraud_probability >= 0.75
    assert clean_state.memory.fraud_category == "visual_anomaly"


@pytest.mark.asyncio
async def test_evidence_fusion_critical_anomaly_max_pooling_prevents_dilution(clean_state):
    """
    Verifies that 9 clean ROIs do not dilute a single critical defect (missing IC chip)
    below the quarantine threshold (fraud_probability >= 0.70).
    """
    # 9 Clean ROIs
    for i in range(9):
        await clean_state.append_evidence(
            agent_type=AgentType.STRUCTURAL,
            roi_id=f"CLEAN_ROI_{i}",
            confidence=0.98,
            evidence={
                "ssim_score": 0.99,
                "threshold": 0.85,
                "match_status": "match",
                "component_findings": [],
                "missing_components": [],
                "extra_components": [],
            },
            explanation="Clean ROI conforming to golden standard",
            processing_time_ms=10.0,
        )

    # 1 Severe Defect ROI
    await clean_state.append_evidence(
        agent_type=AgentType.STRUCTURAL,
        roi_id="DEFECTIVE_IC_ROI",
        confidence=0.95,
        evidence={
            "ssim_score": 0.55,
            "threshold": 0.85,
            "match_status": "defect_detected",
            "component_findings": [
                {
                    "class_name": "ic_chip",
                    "golden_count": 1,
                    "inspection_count": 0,
                    "diff": -1,
                    "status": "missing",
                }
            ],
            "missing_components": ["missing:ic_chip(diff=-1)"],
            "extra_components": [],
        },
        explanation="Critical missing IC chip",
        processing_time_ms=20.0,
    )

    res = await run_evidence_fusion(clean_state)
    assert res.status == "flagged"
    # Max-pooling guarantees risk is >= 0.75 even with 9 clean ROIs
    assert clean_state.memory.fraud_probability >= 0.75
    assert clean_state.memory.fraud_category == "missing_components"
