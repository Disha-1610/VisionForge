# backend/tests/test_label_agent.py
from __future__ import annotations

import cv2
import numpy as np
import pytest
from PIL import Image

from app.pipeline.agents.label_agent import LabelAgent
from app.shared.evidence_store import AgentType


def _create_synthetic_label_image(width: int = 120, height: int = 80) -> np.ndarray:
    """Create a realistic textured label image with text/shapes."""
    img = np.full((height, width, 3), 240, dtype=np.uint8)
    # Draw blue border
    cv2.rectangle(img, (5, 5), (width - 5, height - 5), (200, 50, 50), 2)
    # Draw dark circle (seal)
    cv2.circle(img, (width // 2, height // 2), 20, (30, 30, 180), -1)
    # Draw white cross on seal
    cv2.line(img, (width // 2 - 12, height // 2), (width // 2 + 12, height // 2), (255, 255, 255), 2)
    cv2.line(img, (width // 2, height // 2 - 12), (width // 2, height // 2 + 12), (255, 255, 255), 2)
    # Add text
    cv2.putText(img, "QC PASS", (15, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 100, 0), 2)
    return img


@pytest.mark.asyncio
async def test_label_agent_identical_images_match():
    label_img = _create_synthetic_label_image()
    agent = LabelAgent()

    result = await agent.run(
        golden_roi=label_img,
        inspection_roi=label_img.copy(),
        roi_data={"roi_id": "qc_seal_1", "name": "QC Seal"},
    )

    assert result.failed is False
    assert result.agent_type == AgentType.LABEL
    assert result.has_defect is False
    assert result.confidence >= 0.95
    assert result.evidence["match_score"] >= 0.99
    assert result.evidence["match_status"] == "match"
    assert "verified against golden reference" in result.explanation


@pytest.mark.asyncio
async def test_label_agent_tampered_label_detects_defect():
    golden_img = _create_synthetic_label_image()
    # Tamper inspection: deface the seal with a black block
    inspection_img = golden_img.copy()
    cv2.rectangle(inspection_img, (30, 20), (90, 60), (0, 0, 0), -1)

    agent = LabelAgent()
    result = await agent.run(
        golden_roi=golden_img,
        inspection_roi=inspection_img,
        roi_data={"roi_id": "qc_seal_1", "name": "QC Seal", "threshold": 0.85},
    )

    assert result.failed is False
    assert result.has_defect is True
    assert result.evidence["match_status"] == "mismatch"
    assert result.evidence["match_score"] < 0.85
    assert result.confidence > 0.0
    assert "mismatch or tampering detected" in result.explanation


@pytest.mark.asyncio
async def test_label_agent_completely_different_image_fails():
    golden_img = _create_synthetic_label_image()
    # Random noise image
    noise_img = np.random.randint(0, 256, golden_img.shape, dtype=np.uint8)

    agent = LabelAgent()
    result = await agent.run(
        golden_roi=golden_img,
        inspection_roi=noise_img,
        roi_data={"roi_id": "seal_diff"},
    )

    assert result.failed is False
    assert result.has_defect is True
    assert result.evidence["match_score"] < 0.50


@pytest.mark.asyncio
async def test_label_agent_larger_inspection_window_locates_template():
    golden_label = _create_synthetic_label_image(width=100, height=60)

    # Larger inspection frame (e.g. 160x100) with the label placed at offset (30, 20)
    inspection_frame = np.full((100, 160, 3), 100, dtype=np.uint8)
    inspection_frame[20:80, 30:130] = golden_label

    agent = LabelAgent()
    result = await agent.run(
        golden_roi=golden_label,
        inspection_roi=inspection_frame,
        roi_data={"roi_id": "seal_offset"},
    )

    assert result.failed is False
    assert result.has_defect is False
    assert result.evidence["match_score"] >= 0.95
    # Located near (30, 20)
    assert abs(result.evidence["peak_location"]["x"] - 30) <= 2
    assert abs(result.evidence["peak_location"]["y"] - 20) <= 2


@pytest.mark.asyncio
async def test_label_agent_pil_image_support():
    golden_cv = _create_synthetic_label_image()
    golden_pil = Image.fromarray(cv2.cvtColor(golden_cv, cv2.COLOR_BGR2RGB))
    inspection_pil = golden_pil.copy()

    agent = LabelAgent()
    result = await agent.run(
        golden_roi=golden_pil,
        inspection_roi=inspection_pil,
        roi_data={"roi_id": "pil_seal"},
    )

    assert result.failed is False
    assert result.has_defect is False
    assert result.confidence >= 0.95


@pytest.mark.asyncio
async def test_label_agent_flat_uniform_crops():
    # Both blank white
    blank_golden = np.full((50, 50, 3), 255, dtype=np.uint8)
    blank_inspection = np.full((50, 50, 3), 255, dtype=np.uint8)

    agent = LabelAgent()
    res_match = await agent.run(blank_golden, blank_inspection, roi_data={"roi_id": "flat_match"})
    assert res_match.failed is False
    assert res_match.has_defect is False

    # One blank white, one blank black
    blank_black = np.zeros((50, 50, 3), dtype=np.uint8)
    res_mismatch = await agent.run(blank_golden, blank_black, roi_data={"roi_id": "flat_mismatch"})
    assert res_mismatch.failed is False
    assert res_mismatch.has_defect is True
