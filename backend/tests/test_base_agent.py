# backend/tests/test_base_agent.py
from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import pytest

from app.pipeline.agents.base_agent import AgentResult, BaseAgent
from app.shared.evidence_store import AgentType


class _DummySuccessAgent(BaseAgent):
    agent_type = AgentType.LABEL
    detector_name = "dummy_success"

    async def _analyze(
        self,
        golden_roi: Any,
        inspection_roi: Any,
        roi_data: dict[str, Any],
    ) -> AgentResult:
        return AgentResult(
            agent_type=self.agent_type,
            detector_name=self.detector_name,
            roi_id="roi_test_1",
            confidence=0.95,
            has_defect=False,
            evidence={"score": 0.95},
            explanation="Dummy analysis passed",
        )


class _DummyFailingAgent(BaseAgent):
    agent_type = AgentType.OCR
    detector_name = "dummy_failing"

    async def _analyze(
        self,
        golden_roi: Any,
        inspection_roi: Any,
        roi_data: dict[str, Any],
    ) -> AgentResult:
        raise RuntimeError("Low-level OCR engine crash")


def test_agent_result_confidence_clamping():
    res_low = AgentResult(
        agent_type=AgentType.LABEL,
        detector_name="test",
        roi_id="roi_1",
        confidence=-0.5,
    )
    assert res_low.confidence == 0.0

    res_high = AgentResult(
        agent_type=AgentType.LABEL,
        detector_name="test",
        roi_id="roi_1",
        confidence=1.5,
    )
    assert res_high.confidence == 1.0


def test_agent_result_to_evidence_dict():
    res = AgentResult(
        agent_type=AgentType.LABEL,
        detector_name="test_det",
        roi_id="roi_qc_seal",
        roi_type="label",
        confidence=0.92,
        has_defect=False,
        evidence={"match_score": 0.92},
        explanation="QC Seal verified",
        bounding_box=[10.0, 20.0, 100.0, 50.0],
        processing_time_ms=12.5,
    )
    d = res.to_evidence_dict()
    assert d["agent_type"] == AgentType.LABEL
    assert d["roi_id"] == "roi_qc_seal"
    assert d["confidence"] == 0.92
    assert d["evidence"]["has_defect"] is False
    assert d["evidence"]["detector_name"] == "test_det"
    assert d["bounding_box"] == [10.0, 20.0, 100.0, 50.0]
    assert d["failed"] is False


@pytest.mark.asyncio
async def test_base_agent_success_run():
    agent = _DummySuccessAgent()
    img_golden = np.zeros((100, 100, 3), dtype=np.uint8)
    img_inspection = np.zeros((100, 100, 3), dtype=np.uint8)

    result = await agent.run(
        img_golden,
        img_inspection,
        roi_data={"roi_id": "seal_1", "type": "label", "bbox": [0, 0, 50, 50]},
    )

    assert result.failed is False
    assert result.agent_type == AgentType.LABEL
    assert result.detector_name == "dummy_success"
    assert result.confidence == 0.95
    assert result.roi_id == "seal_1"
    assert result.roi_type == "label"
    assert result.bounding_box == [0, 0, 50, 50]
    assert result.processing_time_ms >= 0.0


@pytest.mark.asyncio
async def test_base_agent_exception_boundary_reports_failure():
    agent = _DummyFailingAgent()
    img_golden = np.zeros((100, 100, 3), dtype=np.uint8)
    img_inspection = np.zeros((100, 100, 3), dtype=np.uint8)

    # Calling run() must NOT raise an unhandled exception
    result = await agent.run(
        img_golden,
        img_inspection,
        roi_data={"roi_id": "ocr_serial", "type": "text"},
    )

    assert result.failed is True
    assert "Low-level OCR engine crash" in (result.failure_reason or "")
    assert result.confidence == 0.0
    assert result.has_defect is False
    assert result.roi_id == "ocr_serial"
    assert result.processing_time_ms >= 0.0


@pytest.mark.asyncio
async def test_base_agent_missing_images_handled():
    agent = _DummySuccessAgent()

    result = await agent.run(None, None, roi_data={"roi_id": "test"})

    assert result.failed is True
    assert "Both golden_roi and inspection_roi must be provided" in (result.failure_reason or "")
    assert result.confidence == 0.0
