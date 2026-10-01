# backend/tests/test_vlm_agent.py
from __future__ import annotations

import numpy as np
from PIL import Image
import pytest

from app.pipeline.agents.vlm_agent import (
    VLMAgent,
    VLMAnomalyReport,
    _image_to_data_payload,
)
from app.shared.evidence_store import AgentType
from app.shared.llm_client import FinishReason, LLMProvider, LLMResponse


class _MockLLMClient:
    def __init__(self, report: VLMAnomalyReport | None = None, fail: bool = False) -> None:
        self.report = report or VLMAnomalyReport()
        self.fail = fail

    async def generate_json(self, request, response_model):
        if self.fail:
            raise RuntimeError("LLM API connection timeout")

        fake_resp = LLMResponse(
            provider=LLMProvider.GEMINI,
            model="gemini-3.5-flash",
            content=self.report.model_dump_json(),
            finish_reason=FinishReason.STOP,
            latency_ms=120.0,
            attempt=1,
            used_fallback=False,
        )
        return fake_resp, self.report



def test_image_to_data_payload():
    img = Image.new("RGB", (64, 64), color="red")
    payload = _image_to_data_payload(img)
    assert payload.mime_type == "image/jpeg"
    assert payload.source.startswith("data:image/jpeg;base64,")


@pytest.mark.asyncio
async def test_vlm_agent_clean_inspection_passes():
    mock_report = VLMAnomalyReport(
        has_defect=False,
        defect_type="none",
        confidence=0.95,
        severity="none",
        description="Surface integrity clean and verified",
        affected_area="none",
    )
    mock_client = _MockLLMClient(report=mock_report)
    agent = VLMAgent(client=mock_client)

    golden = np.zeros((80, 80, 3), dtype=np.uint8)
    inspection = np.zeros((80, 80, 3), dtype=np.uint8)

    result = await agent.run(
        golden_roi=golden,
        inspection_roi=inspection,
        roi_data={"roi_id": "vlm_surface_1", "name": "Board Surface"},
    )

    assert result.failed is False
    assert result.agent_type == AgentType.VLM
    assert result.detector_name == "vlm_agent"
    assert result.has_defect is False
    assert result.confidence == 0.95
    assert result.evidence["defect_type"] == "none"
    assert "no visible defect" in result.explanation.lower()


@pytest.mark.asyncio
async def test_vlm_agent_default_no_visual_defects_does_not_false_alarm():
    """Verify default phrase 'No visual defects detected' does NOT trigger keyword false positive."""
    mock_report = VLMAnomalyReport(
        has_defect=False,
        defect_type="none",
        confidence=0.85,
        severity="none",
        description="No visual defects detected",
        affected_area="none",
    )
    mock_client = _MockLLMClient(report=mock_report)
    agent = VLMAgent(client=mock_client)

    golden = np.zeros((80, 80, 3), dtype=np.uint8)
    inspection = np.zeros((80, 80, 3), dtype=np.uint8)

    result = await agent.run(
        golden_roi=golden,
        inspection_roi=inspection,
        roi_data={"roi_id": "vlm_surface_1", "name": "General Board Surface"},
    )

    assert result.has_defect is False
    assert result.evidence["severity"] == "none"
    assert "no visible defect" in result.explanation.lower()
    assert "hardware defect detected" not in result.explanation.lower()


@pytest.mark.asyncio
async def test_vlm_agent_detects_visual_anomaly():
    mock_report = VLMAnomalyReport(
        has_defect=True,
        defect_type="burn_mark",
        confidence=0.92,
        severity="critical",
        description="Severe thermal scorch mark on power rail",
        affected_area="pin_3_vcc",
    )
    mock_client = _MockLLMClient(report=mock_report)
    agent = VLMAgent(client=mock_client)

    golden = np.full((80, 80, 3), 128, dtype=np.uint8)
    inspection = np.full((80, 80, 3), 128, dtype=np.uint8)

    result = await agent.run(
        golden_roi=golden,
        inspection_roi=inspection,
        roi_data={"roi_id": "vlm_power_stage", "name": "Power Rail"},
    )

    assert result.failed is False
    assert result.has_defect is True
    assert result.confidence == 0.92
    assert result.evidence["defect_type"] == "burn_mark"
    assert result.evidence["severity"] == "critical"
    assert "burn_mark" in result.explanation
    assert "thermal scorch" in result.explanation


@pytest.mark.asyncio
async def test_vlm_agent_api_failure_handled():
    mock_client = _MockLLMClient(fail=True)
    agent = VLMAgent(client=mock_client)

    golden = np.zeros((50, 50, 3), dtype=np.uint8)
    inspection = np.zeros((50, 50, 3), dtype=np.uint8)

    result = await agent.run(
        golden_roi=golden,
        inspection_roi=inspection,
        roi_data={"roi_id": "vlm_fail_case"},
    )

    assert result.failed is True
    assert result.confidence == 0.0
    assert "LLM API connection timeout" in (result.failure_reason or "")


@pytest.mark.asyncio
async def test_vlm_agent_zero_dimension_crops():
    agent = VLMAgent()

    empty = np.zeros((0, 0, 3), dtype=np.uint8)
    valid = np.zeros((40, 40, 3), dtype=np.uint8)

    result = await agent.run(golden_roi=empty, inspection_roi=valid, roi_data={"roi_id": "vlm_zero"})
    assert result.failed is True
    assert "dimensions" in (result.failure_reason or "").lower()


def test_vlm_report_normalizes_alternate_keys():
    raw_dict = {
        "findings": "Both images show identical solder joints and 4 capacitors intact",
        "has_defect": False,
        "confidence": 0.95,
    }
    report = VLMAnomalyReport.model_validate(raw_dict)
    assert "identical solder joints" in report.description
    assert "identical solder joints" in report.visual_evidence


def test_vlm_report_normalizes_dict_specific_differences():
    raw_dict = {
        "has_defect": True,
        "defect_type": "label_tampering",
        "confidence": 92.5,
        "severity": {"level": "high"},
        "affected_area": ["product label", "gold fingers"],
        "component_count_expected": "8",
        "component_count_observed": "6",
        "specific_differences": [
            {
                "area": "product label",
                "description": "The product label has peeling on the bottom edge and serial number ending digit differs from standard.",
                "severity": "high",
            },
            {
                "area": "gold fingers",
                "description": "Minor surface discoloration observed near pin 12.",
                "severity": "medium",
            },
        ],
    }
    report = VLMAnomalyReport.model_validate(raw_dict)
    assert report.has_defect is True
    assert report.confidence == 0.925
    assert report.severity == "high"
    assert "product label" in report.affected_area
    assert report.component_count_expected == 8
    assert report.component_count_observed == 6
    assert len(report.specific_differences) == 2
    assert "[product label]" in report.specific_differences[0]
    assert "(severity: high)" in report.specific_differences[0]
    assert "[gold fingers]" in report.specific_differences[1]


