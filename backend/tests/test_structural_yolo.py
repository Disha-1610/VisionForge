# backend/tests/test_structural_yolo.py
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
import cv2
import numpy as np
import pytest

from app.pipeline.agents.structural_agent import StructuralAgent
from app.shared.evidence_store import AgentType


class _MockBox:
    def __init__(self, cls_id: int, conf: float) -> None:
        self.cls = [cls_id]
        self.conf = [conf]
        self.xywhn = [[0.5, 0.5, 0.2, 0.2]]


class _MockYOLOResult:
    def __init__(self, detections: list[tuple[int, float]]) -> None:
        self.boxes = [_MockBox(cls_id, conf) for cls_id, conf in detections]


class _MockYOLOModel:
    def __init__(self, golden_dets: list[tuple[int, float]], insp_dets: list[tuple[int, float]]) -> None:
        self.names = {0: "capacitor", 1: "resistor", 2: "ic_chip", 3: "connector"}
        self._golden_dets = golden_dets
        self._insp_dets = insp_dets
        self._call_count = 0

    def predict(self, source, conf=0.20, verbose=False):
        self._call_count += 1
        # First call is golden, second is inspection
        if self._call_count % 2 == 1:
            return [_MockYOLOResult(self._golden_dets)]
        return [_MockYOLOResult(self._insp_dets)]


@pytest.mark.asyncio
async def test_structural_yolo_identical_components_pass():
    # Both golden and inspection have 4 capacitors (cls 0)
    mock_yolo = _MockYOLOModel(
        golden_dets=[(0, 0.85), (0, 0.82), (0, 0.88), (0, 0.90)],
        insp_dets=[(0, 0.85), (0, 0.82), (0, 0.88), (0, 0.90)],
    )

    agent = StructuralAgent(yolo_model=mock_yolo, enable_yolo=True, default_threshold=0.70)

    # Identical textured image
    img = np.full((100, 100, 3), 128, dtype=np.uint8)
    cv2.circle(img, (50, 50), 30, (255, 255, 255), -1)

    result = await agent.run(
        golden_roi=img,
        inspection_roi=img,
        roi_data={"roi_id": "cap_bank", "name": "Capacitor Bank 1"},
    )

    assert result.failed is False
    assert result.has_defect is False
    assert result.evidence["yolo_enabled"] is True
    assert result.evidence["golden_detections_count"] == 4
    assert result.evidence["inspection_detections_count"] == 4
    assert len(result.evidence["missing_components"]) == 0
    assert len(result.evidence["extra_components"]) == 0


@pytest.mark.asyncio
async def test_structural_yolo_missing_component_defect():
    # Golden has 4 capacitors, inspection only has 3 (1 stolen/missing)
    mock_yolo = _MockYOLOModel(
        golden_dets=[(0, 0.85), (0, 0.82), (0, 0.88), (0, 0.90)],
        insp_dets=[(0, 0.85), (0, 0.82), (0, 0.88)],
    )

    agent = StructuralAgent(yolo_model=mock_yolo, enable_yolo=True)

    img1 = np.full((100, 100, 3), 128, dtype=np.uint8)
    img2 = np.full((100, 100, 3), 128, dtype=np.uint8)

    result = await agent.run(
        golden_roi=img1,
        inspection_roi=img2,
        roi_data={"roi_id": "cap_bank", "name": "Capacitor Bank 1"},
    )

    assert result.failed is False
    assert result.has_defect is True
    assert len(result.evidence["missing_components"]) == 1
    assert result.evidence["missing_components"][0]["class_name"] == "capacitor"
    assert result.evidence["missing_components"][0]["diff"] == -1
    assert "YOLO detected: capacitor missing (4 vs 3)" in result.explanation


@pytest.mark.asyncio
async def test_structural_yolo_extra_counterfeit_component_defect():
    # Golden has 0 IC, Inspection has 1 extra rogue component
    mock_yolo = _MockYOLOModel(
        golden_dets=[],
        insp_dets=[(2, 0.80)],
    )

    agent = StructuralAgent(yolo_model=mock_yolo, enable_yolo=True)

    img = np.full((100, 100, 3), 128, dtype=np.uint8)

    result = await agent.run(
        golden_roi=img,
        inspection_roi=img,
        roi_data={"roi_id": "ic_slot", "name": "IC Socket"},
    )

    assert result.failed is False
    assert result.has_defect is True
    assert len(result.evidence["extra_components"]) == 1
    assert result.evidence["extra_components"][0]["class_name"] == "ic_chip"
    assert "extra ic_chip detected (1 vs 0)" in result.explanation


@pytest.mark.asyncio
async def test_structural_yolo_disabled_uses_pure_ssim():
    agent = StructuralAgent(enable_yolo=False, default_threshold=0.80)

    # Identical images
    img = np.zeros((80, 80, 3), dtype=np.uint8)
    cv2.rectangle(img, (10, 10), (70, 70), (200, 200, 200), -1)

    result = await agent.run(
        golden_roi=img,
        inspection_roi=img,
        roi_data={"roi_id": "pure_ssim_test"},
    )

    assert result.failed is False
    assert result.has_defect is False
    assert result.evidence["yolo_enabled"] is False
    assert result.evidence["ssim_score"] == 1.0


def test_structural_real_weights_loading():
    weights_path = Path(__file__).resolve().parent.parent / "data" / "yolo_weights" / "component_detector.pt"
    if not weights_path.exists():
        weights_path = Path("data/yolo_weights/component_detector.pt")
    if not weights_path.exists():
        pytest.skip("component_detector.pt not present locally")

    agent = StructuralAgent(yolo_weights_path=weights_path, enable_yolo=True)
    agent._init_yolo_if_needed()

    assert agent._yolo_model is not None
    assert len(agent._yolo_model.names) == 8
