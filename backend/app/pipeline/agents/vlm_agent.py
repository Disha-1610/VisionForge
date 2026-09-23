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
    LLMProvider,
    LLMRequest,
    LLMTask,
    ResponseFormat,
    get_llm_client,
)
from app.utils.image_utils import ImageSource, load_pil_image

logger = logging.getLogger("app.pipeline.agents.vlm")

VLM_SYSTEM_PROMPT = """You are VisionForge AI's specialized VLM Hardware Inspection Agent — an expert electronics quality engineer inspecting computer hardware components (RAM modules, laptop batteries, motherboards, GPUs, SSDs).

You receive TWO images:
- Image 1: GOLDEN REFERENCE (known authentic, factory-new, flawless standard)
- Image 2: INSPECTION SAMPLE (hardware under inspection)

## INSPECTION PROTOCOL — follow these steps IN ORDER for every ROI

### Step 1: COMPONENTS & COUNT
- Identify all discrete components: IC chips, capacitors, resistors, connectors, gold pins, mounting holes, shielding, cells, diodes, inductors
- Count each type in BOTH images and compare
- MISSING, EXTRA, or DIFFERENT component = HIGH severity defect

### Step 2: POSITION & ALIGNMENT
- Compare component placement between the two images
- Skewed, tilted, rotated, shifted, or protruding components = defect
- Bent / broken pins, lifted connectors, misaligned ICs = defect

### Step 3: SURFACE & MATERIAL CONDITION
- Physical damage: scratches, cracks, edge chipping, broken corners, deformed heatsink fins, dented pins
- Thermal/electrical damage: burn marks, scorch, heat discoloration, darkened/melted traces, swollen or leaking cells (battery)
- Chemical/contamination: flux residue, solder splatter, corrosion, oxidation, foreign debris, moisture stains

### Step 4: SOLDER & CONNECTIONS
- Compare solder joint density, wetness, and uniformity
- Missing solder, cold joints, bridging, lifted pads, tombstoned components = defect

### Step 5: SILKSCREEN, LABELS & TEXT
- Compare visible printed text: part numbers, serials, logos, batch codes, capacity labels, certification marks (CE/FCC/RoHS), date codes
- Faded / smudged / tampered / double-printed text or labels = defect
- Note: another agent (OCR) handles precise text matching; focus on visual label integrity (peeling, bubbles, misplacement, re-labelling)

### Step 6: PHYSICAL FORM & PROFILE (special concern per hardware type)
- RAM modules: PCB edge uniformity, gold finger contacts, mounting notches, heat spreader alignment
- Laptop batteries: cell swelling, wrapper wrinkles, labeling bubbles, connector damage, vent bulges
- Motherboards: board bending/twist, capacitor bulge, heat sink seating, bracket/mount alignment, socket integrity

## RESPONSE REQUIREMENTS (CRITICAL)
1. NEVER write generic "verified normal" / "verified clean" — ALWAYS give specific reasoning tied to what you actually SEE
2. ALWAYS state what Image 1 looks like and what Image 2 looks like, then the DIFFERENCE (or state "no visible difference" with observed evidence)
3. Provide component counts when the ROI contains countable components
4. Confidence must reflect visual evidence strength — if crops are too small/blurry/unclear, lower confidence and say why
5. defect_type must be SPECIFIC: use one of: scratch, crack, burn_mark, discoloration, corrosion, misalignment, missing_component, extra_component, bent_pin, solder_defect, label_tampering, swelling, contamination, or none
6. SIMPLE PLAIN ENGLISH: Always write descriptions, observations, and explanations in simple, clear everyday English. Avoid complex mathematical terms, statistical symbols, or obscure jargon so that anyone can immediately understand the findings.

Return your evaluation strictly as valid JSON.
"""


class VLMAnomalyReport(BaseModel):
    """Structured report returned by VLM visual analysis."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    has_defect: bool = Field(default=False, description="True if anomaly or tampering is detected")
    defect_type: str = Field(
        default="none",
        description="Type: scratch, crack, burn_mark, discoloration, corrosion, misalignment, missing_component, extra_component, bent_pin, solder_defect, label_tampering, swelling, contamination, or none",
    )
    confidence: float = Field(default=0.85, ge=0.0, le=1.0, description="Confidence in finding")
    severity: str = Field(default="none", description="Severity: none, low, medium, high, critical")
    description: str = Field(default="No visual defects detected", description="Detailed visual explanation")
    affected_area: str = Field(default="none", description="Specific region or pin/component affected")
    component_count_expected: int | None = Field(default=None, description="Expected component count from golden reference")
    component_count_observed: int | None = Field(default=None, description="Observed component count in inspection sample")
    specific_differences: list[str] = Field(default_factory=list, description="Exact differences found between golden and sample")
    visual_evidence: str = Field(default="", description="What each image actually shows — golden vs sample")


def _image_to_data_payload(pil_img: Image.Image, max_dim: int = 512) -> ImageInput:
    """Encode PIL image to base64 ImageInput for LLMClient, scaling large crops to conserve VLM input tokens."""
    buffered = io.BytesIO()
    # Convert RGBA to RGB for JPEG encoding
    if pil_img.mode in ("RGBA", "P"):
        pil_img = pil_img.convert("RGB")
    if max(pil_img.size) > max_dim:
        pil_img = pil_img.copy()
        pil_img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
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

        hardware_type = roi_data.get("hardware_type") or roi_data.get("product_type") or "computer hardware"
        roi_expected_count = str(roi_data.get("expected_count") or "") 
        count_info = f"Expected component count in this ROI: {roi_expected_count}." if roi_expected_count else ""

        user_prompt = (
            f"Inspecting ROI: '{roi_name}' (ID: {roi_id}) on a {hardware_type} unit.\n"
            f"{checkpoints_info}"
            f"{count_info}\n"
            f"Image 1 is the GOLDEN REFERENCE. Image 2 is the INSPECTION SAMPLE.\n"
            f"Follow the inspection protocol and provide a detailed structured report "
            f"describing the SPECIFIC differences you observe between the two images."
        )

        pref_provider = None
        if "preferred_provider" in roi_data and roi_data["preferred_provider"]:
            val = str(roi_data["preferred_provider"]).lower()
            if "groq" in val:
                pref_provider = LLMProvider.GROQ
            elif "gemini" in val:
                pref_provider = LLMProvider.GEMINI

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
            preferred_provider=pref_provider,
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
            expected_count = report.component_count_expected
            observed_count = report.component_count_observed
            specific_diffs = list(report.specific_differences)
            visual_evidence = str(report.visual_evidence)

            # Safety check: enforce has_defect if anomalies, differences or explicit defect indicators are reported
            if not has_defect:
                clean_phrases = (
                    "no visual defect",
                    "no visual defects",
                    "no defect",
                    "no defects",
                    "no visible defect",
                    "no visible defects",
                    "clean and verified",
                    "no anomaly",
                    "no anomalies",
                    "without defect",
                    "normal condition",
                )
                desc_lower = description.lower().strip()
                is_explicitly_clean = any(cp in desc_lower for cp in clean_phrases)

                defect_keywords = (
                    "missing", "damage", "scratch", "corrosion",
                    "tamper", "counterfeit", "discrepanc", "broken", "burn", "peel"
                )
                has_keywords = (not is_explicitly_clean) and any(kw in desc_lower for kw in defect_keywords)
                has_sev = severity.lower() in ("critical", "high", "medium", "low")
                has_type = defect_type.lower() not in ("none", "clean", "null", "normal", "unknown", "")
                has_diffs = len(specific_diffs) > 0

                if (has_keywords and (has_sev or has_type or has_diffs)) or (has_sev and has_type) or (has_diffs and (has_type or has_sev)):
                    has_defect = True

            if has_defect:
                defect_title = defect_type if defect_type and defect_type.lower() not in ("none", "clean", "null", "unknown") else "Hardware Defect"
                desc_clean = description.strip()
                if not desc_clean or desc_clean.lower() in (
                    "no visual defects detected",
                    "no visual defects detected.",
                    "no visual defect detected",
                    "no defect detected",
                    "no visible defect",
                    "none",
                    "clean",
                    "normal",
                ):
                    if specific_diffs:
                        desc_clean = f"Observed discrepancies: {'; '.join(specific_diffs[:2])}"
                    elif affected_area and affected_area.lower() not in ("none", "unknown", "n/a"):
                        desc_clean = f"Observed anomaly affecting {affected_area}."
                    else:
                        desc_clean = f"Observed hardware discrepancy during visual inspection."
                explanation = (
                    f"{roi_name}: {defect_title} detected (severity: {severity}) — "
                    f"{desc_clean}"
                )
            else:
                explanation = f"{roi_name}: No visible defect — {description}"

            evidence = {
                "has_defect": has_defect,
                "defect_type": defect_type,
                "severity": severity,
                "description": description,
                "affected_area": affected_area,
                "component_count_expected": expected_count,
                "component_count_observed": observed_count,
                "specific_differences": specific_diffs,
                "visual_evidence": visual_evidence,
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
