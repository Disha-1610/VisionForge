# backend/tests/test_structural_agent.py
from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.pipeline.agents.structural_agent import (
    StructuralAgent,
    calculate_opencv_ssim,
)
from app.shared.evidence_store import AgentType


def test_calculate_opencv_ssim_identical():
    img = np.full((100, 100), 128, dtype=np.uint8)
    cv2.circle(img, (50, 50), 20, 200, -1)
    score, diff = calculate_opencv_ssim(img, img)
    assert score > 0.99
    assert np.max(diff) == 0


def test_calculate_opencv_ssim_different():
    img1 = np.full((100, 100), 128, dtype=np.uint8)
    img2 = np.full((100, 100), 128, dtype=np.uint8)
    cv2.circle(img1, (50, 50), 25, 255, -1)
    score, diff = calculate_opencv_ssim(img1, img2)
    assert score < 0.90
    assert np.max(diff) > 0


@pytest.mark.asyncio
async def test_structural_agent_identical_crops_pass():
    agent = StructuralAgent(default_threshold=0.80)

    # Create synthetic textured PCB-like pattern
    golden = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.rectangle(golden, (20, 20), (80, 80), (180, 180, 180), -1)
    cv2.line(golden, (10, 50), (90, 50), (240, 240, 240), 2)
    inspection = golden.copy()

    result = await agent.run(
        golden_roi=golden,
        inspection_roi=inspection,
        roi_data={"roi_id": "pcb_structural_1", "name": "Power Stage"},
    )

    assert result.failed is False
    assert result.agent_type == AgentType.STRUCTURAL
    assert result.detector_name == "structural_ssim"
    assert result.has_defect is False
    assert result.evidence["ssim_score"] >= 0.95
    assert result.evidence["diff_percentage"] == 0.0
    assert result.evidence["match_status"] == "match"
    assert "verified" in result.explanation.lower()


@pytest.mark.asyncio
async def test_structural_agent_detects_defect():
    agent = StructuralAgent(default_threshold=0.80)

    golden = np.zeros((100, 100, 3), dtype=np.uint8)
    cv2.rectangle(golden, (20, 20), (80, 80), (220, 220, 220), -1)

    # Inspection is missing the component / erased
    inspection = np.zeros((100, 100, 3), dtype=np.uint8)

    result = await agent.run(
        golden_roi=golden,
        inspection_roi=inspection,
        roi_data={"roi_id": "pcb_structural_2", "name": "Capacitor Bank"},
    )

    assert result.failed is False
    assert result.has_defect is True
    assert result.evidence["ssim_score"] < 0.80
    assert result.evidence["match_status"] == "defect_detected"
    assert result.evidence["diff_percentage"] > 20.0
    assert "anomaly detected" in result.explanation.lower()


@pytest.mark.asyncio
async def test_structural_agent_handles_dimension_mismatch():
    agent = StructuralAgent()

    # Golden is 80x80, Inspection is 100x100 with same pattern
    golden = np.full((80, 80, 3), 100, dtype=np.uint8)
    cv2.circle(golden, (40, 40), 20, (255, 255, 255), -1)

    inspection = np.full((100, 100, 3), 100, dtype=np.uint8)
    cv2.circle(inspection, (50, 50), 25, (255, 255, 255), -1)

    result = await agent.run(
        golden_roi=golden,
        inspection_roi=inspection,
        roi_data={"roi_id": "pcb_mismatch_dims"},
    )

    assert result.failed is False
    assert result.evidence["resized_for_comparison"] is True
    assert result.evidence["dimensions"] == {"width": 80, "height": 80}
    assert result.evidence["inspection_original_dimensions"] == {"width": 100, "height": 100}


@pytest.mark.asyncio
async def test_structural_agent_flat_surfaces():
    agent = StructuralAgent()

    flat_white = np.full((60, 60, 3), 255, dtype=np.uint8)
    flat_white2 = np.full((60, 60, 3), 255, dtype=np.uint8)

    res_flat = await agent.run(flat_white, flat_white2, {"roi_id": "flat_1"})
    assert res_flat.has_defect is False
    assert res_flat.evidence["ssim_score"] == 1.0

    # One flat, one textured
    textured = np.random.randint(0, 255, (60, 60, 3), dtype=np.uint8)
    res_diff = await agent.run(flat_white, textured, {"roi_id": "flat_vs_textured"})
    assert res_diff.has_defect is True
    assert res_diff.evidence["ssim_score"] == 0.0


@pytest.mark.asyncio
async def test_structural_agent_zero_dimensions():
    agent = StructuralAgent()

    zero_img = np.zeros((0, 0, 3), dtype=np.uint8)
    valid_img = np.zeros((40, 40, 3), dtype=np.uint8)

    res = await agent.run(zero_img, valid_img, {"roi_id": "zero_dim"})
    assert res.failed is True
    assert "dimensions" in (res.failure_reason or "").lower()
