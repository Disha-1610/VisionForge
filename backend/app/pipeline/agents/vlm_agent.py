# backend/app/pipeline/agents/vlm_agent.py
"""
Visual Language Model (VLM) Evidence Agent (Disha, W3 D5).

Per VisionForge.md Section 4 Stage 5d & Section 2:
  - Specialized multimodal agent using LLMClient (Primary: Gemini 3.5 Flash, Fallback: Groq Qwen 3.8 27B).
  - Inspects general visual anomalies not covered by OCR, Label, or Structural agents.
  - Detects subtle hardware tampering: burn marks, discoloration, scratches, cracks, flux corrosion,
    tilt/misalignment, and surface debris.
  - Returns structured Pydantic anomaly reports with cause-and-effect natural language explanations.
  - Adheres to BaseAgent contract with strict error isolation (no unhandled API crash).
"""
from __future__ import annotations

import base64
import io
import logging
from typing import Any

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from app.pipeline.agents.base_agent import AgentResult, BaseAgent
from app.shared.evidence_store import AgentType
from app.shared.llm_client import (
    ImageInput,
    LLMCapability,
    LLMClient,
    LLMMessage,
    LLMRequest,
    LLMTask,
    ResponseFormat,
    get_llm_client,
)
from app.utils.image_utils import ImageSource, load_pil_image

logger = logging.getLogger("app.pipeline.agents.vlm")

VLM_SYSTEM_PROMPT = """You are VisionForge AI's specialized Visual Language Model (VLM) Hardware Inspection Agent.
Your objective is to inspect and compare two cropped images of industrial hardware components:
- Image 1: Golden Reference ROI Crop (verified authentic, flawless standard)
- Image 2: Inspection Sample ROI Crop (sample under inspection)

Detect visual defects and tampering that classical computer vision might miss:
1. Physical damage: scratches, cracks, edge chipping, puncture marks.
2. Thermal / electrical damage: burn marks, heat discoloration, darkened traces.
3. Chemical / surface contamination: flux residue, solder splatter, oxidation, corrosion, foreign debris.
4. Physical alignment: skewed orientation, tilted ICs, bent connector pins, improper seating.

Analyze carefully and return your evaluation strictly in the requested JSON format.
"""


class VLMAnomalyReport(BaseModel):
    """Structured report returned by VLM visual analysis."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    has_defect: bool = Field(default=False, description="True if anomaly or tampering is detected")
    defect_type: str = Field(
        default="none",
        description="Type: scratch, crack, burn_mark, discoloration, corrosion, misalignment, missing_component, or none",
    )
    confidence: float = Field(default=0.85, ge=0.0, le=1.0, description="Confidence in finding")
    severity: str = Field(default="none", description="Severity: none, low, medium, high, critical")
    description: str = Field(default="Visual appearance verified normal", description="Detailed visual explanation")
    affected_area: str = Field(default="none", description="Specific region or pin/component affected")


def _image_to_data_payload(pil_img: Image.Image) -> ImageInput:
    """Encode PIL image to base64 ImageInput for LLMClient."""
    buffered = io.BytesIO()
    # Convert RGBA to RGB for JPEG encoding
    if pil_img.mode in ("RGBA", "P"):
        pil_img = pil_img.convert("RGB")
    pil_img.save(buffered, format="JPEG", quality=85)
    raw_bytes = buffered.getvalue()
    b64_str = base64.b64encode(raw_bytes).decode("ascii")
    data_uri = f"data:image/jpeg;base64,{b64_str}"
    return ImageInput(source=data_uri, mime_type="image/jpeg")


class VLMAgent(BaseAgent):
    """
    Multimodal visual inspection agent for subtle hardware anomalies.
    """

    agent_type = AgentType.VLM
    detector_name = "vlm_agent"

    def __init__(
        self,
        client: LLMClient | None = None,
        detector_name: str | None = None,
    ) -> None:
        super().__init__(detector_name=detector_name)
        self._client = client

    @property
    def client(self) -> LLMClient:
        return self._client if self._client is not None else get_llm_client()


    async def _analyze(
        self,
        golden_roi: ImageSource,
        inspection_roi: ImageSource,
        roi_data: dict[str, Any],
    ) -> AgentResult:
        """
        Send golden and inspection crops to VLM for visual anomaly detection.
        """
        roi_id = str(roi_data.get("roi_id") or roi_data.get("id") or "vlm_roi")
        roi_name = str(roi_data.get("name") or roi_id)

        # 1. Early dimension checks for numpy ndarrays
        if hasattr(golden_roi, "shape") and (getattr(golden_roi, "size", 1) == 0 or 0 in golden_roi.shape):
            return AgentResult(
                agent_type=self.agent_type,
                detector_name=self.detector_name,
                roi_id=roi_id,
                confidence=0.0,
                has_defect=True,
                evidence={"error": "Crop has zero dimensions"},
                explanation="Crop has zero dimensions",
                failed=True,
                failure_reason="Crop has zero dimensions",
            )
        if hasattr(inspection_roi, "shape") and (getattr(inspection_roi, "size", 1) == 0 or 0 in inspection_roi.shape):
            return AgentResult(
                agent_type=self.agent_type,
                detector_name=self.detector_name,
                roi_id=roi_id,
                confidence=0.0,
                has_defect=True,
                evidence={"error": "Crop has zero dimensions"},
                explanation="Crop has zero dimensions",
                failed=True,
                failure_reason="Crop has zero dimensions",
            )

        # 2. Load images into PIL
        try:
            golden_pil = load_pil_image(golden_roi)
            inspection_pil = load_pil_image(inspection_roi)
        except Exception as exc:
            return AgentResult(
                agent_type=self.agent_type,
                detector_name=self.detector_name,
                roi_id=roi_id,
                confidence=0.0,
                has_defect=True,
                evidence={"error": f"Failed to load image: {exc}"},
                explanation=f"Image load failure on ROI {roi_id}: {exc}",
                failed=True,
                failure_reason=str(exc),
            )


        if golden_pil.width == 0 or golden_pil.height == 0 or inspection_pil.width == 0 or inspection_pil.height == 0:
            return AgentResult(
                agent_type=self.agent_type,
                detector_name=self.detector_name,
                roi_id=roi_id,
                confidence=0.0,
                has_defect=True,
                evidence={"error": "Crop has zero dimensions"},
                explanation="Crop has zero dimensions",
                failed=True,
                failure_reason="Crop has zero dimensions",
            )

        # 2. Encode to base64 images for multimodal payload
        try:
            img1 = _image_to_data_payload(golden_pil)
            img2 = _image_to_data_payload(inspection_pil)
        except Exception as exc:
            logger.error("Failed encoding images for VLM: %s", exc)
            return AgentResult(
                agent_type=self.agent_type,
                detector_name=self.detector_name,
                roi_id=roi_id,
                confidence=0.0,
                has_defect=False,
                evidence={"error": str(exc)},
                explanation=f"Image encoding error: {exc}",
                failed=True,
                failure_reason=str(exc),
            )

        # 3. Construct prompt
        checkpoints_info = ""
        checkpoints = roi_data.get("checkpoints") or []
        if checkpoints:
            descriptions = [cp.get("description", "") for cp in checkpoints if isinstance(cp, dict)]
            if descriptions:
                checkpoints_info = f"Specific checkpoints to evaluate: {'; '.join(descriptions)}.\n"

        user_prompt = (
            f"Inspecting ROI: '{roi_name}' (ID: {roi_id}).\n"
            f"{checkpoints_info}"
            f"Image 1 is the Golden Reference. Image 2 is the Inspection Sample.\n"
            f"Examine Image 2 against Image 1 and provide a structured anomaly report."
        )

        request = LLMRequest(
            task=LLMTask.VLM,
            capability=LLMCapability.VISION,
            messages=[
                LLMMessage(role="system", content=VLM_SYSTEM_PROMPT),
                LLMMessage(role="user", content=user_prompt),
            ],
            images=[img1, img2],
            temperature=0.1,
            max_tokens=1024,
            response_format=ResponseFormat.JSON,
            stage_name="evidence_execution",
        )

        # 4. Call VLM via LLMClient
        try:
            llm_res, report = await self.client.generate_json(request, VLMAnomalyReport)
            has_defect = bool(report.has_defect)
            confidence = float(report.confidence)
            defect_type = str(report.defect_type)
            severity = str(report.severity)
            description = str(report.description)
            affected_area = str(report.affected_area)

            if has_defect:
                explanation = (
                    f"{roi_name}: Visual anomaly detected ({defect_type}, severity: {severity}) - "
                    f"{description}"
                )
            else:
                explanation = f"{roi_name}: Visual appearance verified clean - {description}"

            evidence = {
                "has_defect": has_defect,
                "defect_type": defect_type,
                "severity": severity,
                "description": description,
                "affected_area": affected_area,
                "vlm_confidence": round(confidence, 3),
                "provider": llm_res.provider.value,
                "model": llm_res.model,
                "used_fallback": llm_res.used_fallback,
            }

            return AgentResult(
                agent_type=self.agent_type,
                detector_name=self.detector_name,
                roi_id=roi_id,
                confidence=round(confidence, 3),
                has_defect=has_defect,
                evidence=evidence,
                explanation=explanation,
                raw_output={"content": llm_res.content, "provider": llm_res.provider.value},
            )

        except Exception as exc:
            logger.error("VLM Agent call failed on roi_id=%s: %s", roi_id, exc)
            return AgentResult(
                agent_type=self.agent_type,
                detector_name=self.detector_name,
                roi_id=roi_id,
                confidence=0.0,
                has_defect=False,
                evidence={"error": str(exc), "stage": "vlm_inference"},
                explanation=f"VLM Agent analysis failed: {exc}",
                failed=True,
                failure_reason=str(exc),
            )
