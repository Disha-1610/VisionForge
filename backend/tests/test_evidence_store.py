import uuid
import pytest
from app.shared.evidence_store import (
    EvidenceStore,
    AgentType,
    EvidenceImmutableError,
    EvidenceStoreError,
    EvidenceNotFoundError,
)


def test_evidence_store_append_and_retrieve():
    store = EvidenceStore()
    inspection_id = uuid.uuid4()

    # Append OCR evidence
    rec1 = store.append(
        inspection_id=inspection_id,
        agent_type=AgentType.OCR,
        roi_id="roi_serial_01",
        confidence=0.98,
        evidence={"detected_text": "SN123456", "expected_text": "SN123456"},
        explanation="Serial number matched golden reference",
        processing_time_ms=45.2,
        bounding_box=[10.0, 20.0, 100.0, 30.0],
    )
    assert rec1.sequence == 0
    assert rec1.agent_type == AgentType.OCR
    assert rec1.confidence == 0.98

    # Append Structural evidence
    rec2 = store.append(
        inspection_id=inspection_id,
        agent_type=AgentType.STRUCTURAL,
        roi_id="roi_capacitors_02",
        confidence=0.95,
        evidence={"detected_count": 4, "expected_count": 4},
        explanation="All 4 capacitors verified present",
        processing_time_ms=88.5,
    )
    assert rec2.sequence == 1

    # Verify retrieval
    all_recs = store.get_all_for_inspection(inspection_id)
    assert len(all_recs) == 2
    assert store.count(inspection_id) == 2

    # Get by ID
    fetched = store.get(rec1.evidence_id)
    assert fetched.evidence_id == rec1.evidence_id

    # Filter by Agent Type
    ocr_recs = store.get_by_agent(inspection_id, AgentType.OCR)
    assert len(ocr_recs) == 1
    assert ocr_recs[0].roi_id == "roi_serial_01"


def test_evidence_store_immutable_guarantee():
    store = EvidenceStore()
    inspection_id = uuid.uuid4()
    store.append(
        inspection_id=inspection_id,
        agent_type=AgentType.LABEL,
        roi_id="roi_logo_01",
        confidence=0.92,
        evidence={"match": True},
        explanation="Logo matches",
        processing_time_ms=25.0,
    )

    # Attempting to clear/delete must fail
    with pytest.raises(EvidenceImmutableError):
        store.clear_inspection(inspection_id)


def test_evidence_store_failed_flag_validation():
    store = EvidenceStore()
    inspection_id = uuid.uuid4()

    # Failed flag requires failure_reason
    with pytest.raises(EvidenceStoreError):
        store.append(
            inspection_id=inspection_id,
            agent_type=AgentType.VLM,
            roi_id="roi_surface_01",
            confidence=0.0,
            evidence={},
            explanation="Failed",
            processing_time_ms=10.0,
            failed=True,
            failure_reason=None,  # Missing reason
        )
