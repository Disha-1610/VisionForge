# backend/app/pipeline/agents/label_agent.py
"""
Label Agent (Anil, W3 D3).

Specialized evidence agent for labels, seals, and logos.
Per VisionForge.md Section 4, Stage 5b:
  - Tool: OpenCV cv2.matchTemplate (free, local).
  - Inputs: Cropped Golden ROI and Inspection ROI image pair.
  - Logic: Grayscale conversion, normalized cross-correlation (TM_CCOEFF_NORMED),
    peak match score extraction, threshold evaluation, structured evidence generation.
"""
from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

from app.pipeline.agents.base_agent import AgentResult, BaseAgent
from app.shared.evidence_store import AgentType
from app.utils.image_utils import ImageSource, load_cv_image

logger = logging.getLogger("app.pipeline.agents.label")

DEFAULT_LABEL_THRESHOLD = 0.80


class LabelAgent(BaseAgent):
    """
    Evidence agent for logos, QC seals, security labels, and markings
    using OpenCV template matching.
    """

    agent_type = AgentType.LABEL
    detector_name = "opencv_match_template"

    def __init__(
        self,
        default_threshold: float = DEFAULT_LABEL_THRESHOLD,
        detector_name: str | None = None,
    ) -> None:
        super().__init__(detector_name=detector_name)
        self.default_threshold = default_threshold

    @staticmethod
    def _to_gray(img: np.ndarray) -> np.ndarray:
        """Convert BGR/BGRA/RGB or grayscale ndarray to single-channel uint8."""
        if img.ndim == 2:
            return img
        if img.ndim == 3:
            channels = img.shape[2]
            if channels == 4:
                return cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
            if channels == 3:
                return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img

    async def _analyze(
        self,
        golden_roi: ImageSource,
        inspection_roi: ImageSource,
        roi_data: dict[str, Any],
    ) -> AgentResult:
        """
        Compare golden ROI against inspection ROI using cv2.matchTemplate.
        """
        # 1. Load images into OpenCV format
        golden_cv = load_cv_image(golden_roi)
        inspection_cv = load_cv_image(inspection_roi)

        gh, gw = golden_cv.shape[:2]
        ih, iw = inspection_cv.shape[:2]

        if gh == 0 or gw == 0 or ih == 0 or iw == 0:
            return AgentResult(
                agent_type=self.agent_type,
                detector_name=self.detector_name,
                roi_id=str(roi_data.get("roi_id") or "label_roi"),
                confidence=0.0,
                has_defect=True,
                evidence={"error": "Empty crop dimensions"},
                explanation="One or both ROI crops have zero dimensions",
                failed=True,
                failure_reason="Empty crop dimensions",
            )

        # 2. Convert to grayscale
        golden_gray = self._to_gray(golden_cv)
        inspection_gray = self._to_gray(inspection_cv)

        # 3. Check for zero variance / uniform images
        golden_std = float(np.std(golden_gray))
        inspection_std = float(np.std(inspection_gray))

        threshold = float(roi_data.get("threshold") or self.default_threshold)
        roi_id = str(roi_data.get("roi_id") or roi_data.get("id") or "label_roi")
        roi_name = str(roi_data.get("name") or roi_id)

        # If one or both are completely flat/uniform
        if golden_std < 1e-3 or inspection_std < 1e-3:
            if golden_std < 1e-3 and inspection_std < 1e-3:
                # Both flat: compare mean intensity difference
                diff = abs(float(np.mean(golden_gray)) - float(np.mean(inspection_gray)))
                match_score = max(0.0, 1.0 - (diff / 255.0))
            else:
                # One is flat and other is textured -> obvious mismatch/defect
                match_score = 0.0

            has_defect = match_score < threshold
            confidence = match_score if not has_defect else max(0.0, min(1.0, 1.0 - match_score))
            explanation = (
                f"{roi_name} uniform region analysis: score {match_score:.3f} "
                f"({'matches' if not has_defect else 'defect detected'} threshold {threshold:.2f})"
            )
            return AgentResult(
                agent_type=self.agent_type,
                detector_name=self.detector_name,
                roi_id=roi_id,
                confidence=round(confidence, 3),
                has_defect=has_defect,
                evidence={
                    "match_score": round(match_score, 4),
                    "threshold": round(threshold, 4),
                    "match_status": "match" if not has_defect else "mismatch",
                    "method": "uniform_intensity_check",
                    "golden_dimensions": {"width": gw, "height": gh},
                    "inspection_dimensions": {"width": iw, "height": ih},
                },
                explanation=explanation,
            )

        # 4. Handle dimensions for cv2.matchTemplate
        # Template must be smaller than or equal to search image in both dimensions.
        # Primary case: Golden is template, Inspection is search image.
        if ih >= gh and iw >= gw:
            search_img = inspection_gray
            template_img = golden_gray
        elif gh >= ih and gw >= iw:
            search_img = golden_gray
            template_img = inspection_gray
        else:
            # Dimension mismatch in cross directions (e.g. ih > gh but iw < gw).
            # Resize inspection to match golden dimensions.
            search_img = cv2.resize(inspection_gray, (gw, gh), interpolation=cv2.INTER_AREA)
            template_img = golden_gray

        # 5. Run template matching with normalized cross-correlation
        res = cv2.matchTemplate(search_img, template_img, cv2.TM_CCOEFF_NORMED)
        _min_val, max_val, _min_loc, max_loc = cv2.minMaxLoc(res)

        raw_score = float(max_val)
        if np.isnan(raw_score) or np.isinf(raw_score):
            match_score = 0.0
        else:
            match_score = max(0.0, min(1.0, raw_score))

        # 6. Evaluate findings against threshold
        has_defect = match_score < threshold
        if has_defect:
            confidence = max(0.0, min(1.0, 1.0 - match_score))
            explanation = (
                f"{roi_name} mismatch or tampering detected: match score {match_score:.3f} "
                f"is below expected threshold {threshold:.2f}"
            )
        else:
            confidence = match_score
            explanation = (
                f"{roi_name} verified against golden reference: match score {match_score:.3f} "
                f"meets threshold {threshold:.2f}"
            )

        evidence = {
            "match_score": round(match_score, 4),
            "threshold": round(threshold, 4),
            "match_status": "match" if not has_defect else "mismatch",
            "method": "cv2.TM_CCOEFF_NORMED",
            "peak_location": {"x": int(max_loc[0]), "y": int(max_loc[1])},
            "golden_dimensions": {"width": gw, "height": gh},
            "inspection_dimensions": {"width": iw, "height": ih},
        }

        return AgentResult(
            agent_type=self.agent_type,
            detector_name=self.detector_name,
            roi_id=roi_id,
            confidence=round(confidence, 3),
            has_defect=has_defect,
            evidence=evidence,
            explanation=explanation,
            raw_output={"max_val": raw_score, "max_loc": [int(max_loc[0]), int(max_loc[1])]},
        )
