# backend/tests/test_reporting_service.py
import os
import uuid
import pytest
from app.services.reporting_service import reporting_service


def test_generate_pdf_report(tmp_path):
    custom_service = reporting_service.__class__(reports_dir=str(tmp_path))
    insp_id = uuid.uuid4()
    case_num = f"CASE-TEST-{uuid.uuid4().hex[:6].upper()}"

    evidence_samples = [
        {
            "agent_type": "structural",
            "roi_id": "CPU_SOCKET",
            "confidence": 0.95,
            "has_defect": False,
            "explanation": "SSIM=0.98. Golden component counts verified.",
        },
        {
            "agent_type": "ocr",
            "roi_id": "SERIAL_CODE",
            "confidence": 0.98,
            "has_defect": False,
            "explanation": "Serial matches golden reference VF-SN-2026.",
        },
    ]

    pdf_path = custom_service.generate_pdf_report(
        case_number=case_num,
        inspection_id=insp_id,
        vendor_name="Acme Circuit Co.",
        location="Austin Cleanroom 4",
        part_code="PCB-MCU-V2",
        product_type="Industrial Motherboard",
        verdict="accept",
        policy_action="accept",
        fraud_score=2.5,
        confidence=96.0,
        fraud_category="clean",
        root_cause="All components conform to IPC-A-610 Class 3 certified tolerances.",
        authenticity_score=0.98,
        reference_similarity=0.97,
        evidence_items=evidence_samples,
    )

    assert os.path.exists(pdf_path)
    file_size = os.path.getsize(pdf_path)
    assert file_size > 1000  # PDF must have generated content
