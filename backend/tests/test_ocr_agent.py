# backend/tests/test_ocr_agent.py
from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.pipeline.agents.base_agent import AgentResult
from app.pipeline.agents.ocr_agent import (
    OCRAgent,
    find_character_mismatches,
    normalize_text,
)
from app.shared.evidence_store import AgentType


class _MockEasyOCRReader:
    """Mock EasyOCR reader returning fixed text and confidence."""

    def __init__(self, text: str = "SN-2026-VF", conf: float = 0.96) -> None:
        self.text = text
        self.conf = conf

    def readtext(self, img):
        if not self.text:
            return []
        # Return format: (bbox, text, prob)
        return [([[0, 0], [10, 0], [10, 10], [0, 10]], self.text, self.conf)]


class _MockFailingReader:
    def readtext(self, img):
        raise RuntimeError("GPU OOM / Engine Crash")


def test_normalize_text():
    assert normalize_text("  sn-9821-x \n") == "SN-9821-X"
    assert normalize_text("batch   # 123 ") == "BATCH # 123"
    assert normalize_text("") == ""


def test_find_character_mismatches():
    # Substitution
    diffs = find_character_mismatches("SN-1234", "SN-1294")
    assert len(diffs) == 1
    assert diffs[0]["type"] == "replace"
    assert diffs[0]["expected_char"] == "3"
    assert diffs[0]["actual_char"] == "9"

    # Perfect match
    diffs_match = find_character_mismatches("MATCH", "MATCH")
    assert len(diffs_match) == 0


@pytest.mark.asyncio
async def test_ocr_agent_matching_text_with_mock():
    mock_reader = _MockEasyOCRReader(text="VF-SN-8921-A", conf=0.98)
    agent = OCRAgent(reader=mock_reader)

    img_golden = np.zeros((60, 200, 3), dtype=np.uint8)
    img_inspection = np.zeros((60, 200, 3), dtype=np.uint8)

    result = await agent.run(
        golden_roi=img_golden,
        inspection_roi=img_inspection,
        roi_data={
            "roi_id": "text_serial",
            "type": "text",
            "expected_text": "VF-SN-8921-A",
            "threshold": 0.85,
        },
    )

    assert result.failed is False
    assert result.agent_type == AgentType.OCR
    assert result.detector_name == "ocr_agent"
    assert result.has_defect is False
    assert result.confidence >= 0.90
    assert result.evidence["match_status"] == "match"
    assert result.evidence["similarity"] == 1.0
    assert result.evidence["extracted_text"] == "VF-SN-8921-A"
    assert len(result.evidence["mismatches"]) == 0


@pytest.mark.asyncio
async def test_ocr_agent_tampered_serial_detected():
    mock_reader = _MockEasyOCRReader(text="VF-SN-8921-FAKE", conf=0.92)
    agent = OCRAgent(reader=mock_reader)

    img_golden = np.zeros((60, 200, 3), dtype=np.uint8)
    img_inspection = np.zeros((60, 200, 3), dtype=np.uint8)

    result = await agent.run(
        golden_roi=img_golden,
        inspection_roi=img_inspection,
        roi_data={
            "roi_id": "text_serial",
            "expected_text": "VF-SN-8921-ORIG",
            "threshold": 0.85,
        },
    )

    assert result.failed is False
    assert result.has_defect is True
    assert result.evidence["match_status"] == "mismatch"
    assert result.evidence["similarity"] < 0.85
    assert len(result.evidence["mismatches"]) > 0
    assert "Text mismatch on text_serial" in result.explanation


@pytest.mark.asyncio
async def test_ocr_agent_uses_checkpoints_for_expected_text():
    mock_reader = _MockEasyOCRReader(text="REV-B", conf=0.95)
    agent = OCRAgent(reader=mock_reader)

    img_golden = np.zeros((60, 200, 3), dtype=np.uint8)
    img_inspection = np.zeros((60, 200, 3), dtype=np.uint8)

    result = await agent.run(
        golden_roi=img_golden,
        inspection_roi=img_inspection,
        roi_data={
            "roi_id": "pcb_rev",
            "checkpoints": [
                {
                    "id": "cp_rev",
                    "description": "Hardware Revision Check",
                    "expected_value": "REV-B",
                }
            ],
        },
    )

    assert result.failed is False
    assert result.has_defect is False
    assert result.evidence["expected_text"] == "REV-B"
    assert result.evidence["extracted_text"] == "REV-B"


@pytest.mark.asyncio
async def test_ocr_agent_engine_failure_reported_cleanly():
    failing_reader = _MockFailingReader()
    agent = OCRAgent(reader=failing_reader)

    img_golden = np.zeros((60, 200, 3), dtype=np.uint8)
    img_inspection = np.zeros((60, 200, 3), dtype=np.uint8)

    result = await agent.run(
        golden_roi=img_golden,
        inspection_roi=img_inspection,
        roi_data={"roi_id": "roi_crash"},
    )

    assert result.failed is True
    assert result.confidence == 0.0
    assert "GPU OOM / Engine Crash" in (result.failure_reason or "")


@pytest.mark.asyncio
async def test_ocr_agent_zero_dimension_crops():
    mock_reader = _MockEasyOCRReader(text="TEXT")
    agent = OCRAgent(reader=mock_reader)

    empty_img = np.zeros((0, 0, 3), dtype=np.uint8)
    valid_img = np.zeros((50, 50, 3), dtype=np.uint8)

    result = await agent.run(
        golden_roi=empty_img,
        inspection_roi=valid_img,
        roi_data={"roi_id": "roi_zero"},
    )

    assert result.failed is True
    assert "dimensions" in (result.failure_reason or "").lower()
