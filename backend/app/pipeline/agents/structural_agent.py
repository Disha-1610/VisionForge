# backend/app/pipeline/agents/structural_agent.py
"""
Structural Evidence Agent — SSIM Foundation (Disha, W3 D3).

Per VisionForge.md Section 4 Stage 5c & Section 2:
  - Calculates Structural Similarity Index (SSIM) between golden and inspection crops.
  - Generates structural diff heatmaps, Mean Squared Error (MSE), and diff percentages.
  - Detects structural defects, physical displacement, surface anomalies, and missing traces.
  - Prepares architecture for Day 4/5 YOLO component detection count integration.
  - Standardized BaseAgent implementation reporting to EvidenceStore.
"""
from __future__ import annotations

import logging
from typing import Any

import cv2
import numpy as np

from app.pipeline.agents.base_agent import AgentResult, BaseAgent
from app.shared.evidence_store import AgentType
from app.utils.image_utils import ImageSource, load_cv_image

logger = logging.getLogger("app.pipeline.agents.structural")

DEFAULT_SSIM_THRESHOLD = 0.80
DEFAULT_DIFF_TOLERANCE = 25  # pixel intensity difference threshold


def calculate_opencv_ssim(
    img1: np.ndarray,
    img2: np.ndarray,
) -> tuple[float, np.ndarray]:
    """
    Compute Structural Similarity Index (SSIM) using standard OpenCV
    Gaussian filtering and windowing formula as a local fallback.
    """
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2

    img1 = img1.astype(np.float64)
    img2 = img2.astype(np.float64)

    kernel = (11, 11)
    sigma = 1.5

    mu1 = cv2.GaussianBlur(img1, kernel, sigma)
    mu2 = cv2.GaussianBlur(img2, kernel, sigma)

    mu1_sq = mu1 ** 2
    mu2_sq = mu2 ** 2
    mu1_mu2 = mu1 * mu2

    sigma1_sq = cv2.GaussianBlur(img1 ** 2, kernel, sigma) - mu1_sq
    sigma2_sq = cv2.GaussianBlur(img2 ** 2, kernel, sigma) - mu2_sq
    sigma12 = cv2.GaussianBlur(img1 * img2, kernel, sigma) - mu1_mu2

    num = (2 * mu1_mu2 + c1) * (2 * sigma12 + c2)
    den = (mu1_sq + mu2_sq + c1) * (sigma1_sq + sigma2_sq + c2)
    ssim_map = num / den
    ssim_score = float(np.mean(ssim_map))

    diff = cv2.absdiff(img1.astype(np.uint8), img2.astype(np.uint8))
    return max(-1.0, min(1.0, ssim_score)), diff


class StructuralAgent(BaseAgent):
    """
    Specialized evidence agent for PCB structural similarity,
    trace integrity, component layout, and physical alignment.
    """

    agent_type = AgentType.STRUCTURAL
    detector_name = "structural_ssim"

    def __init__(
        self,
        default_threshold: float = DEFAULT_SSIM_THRESHOLD,
        detector_name: str | None = None,
        diff_tolerance: int = DEFAULT_DIFF_TOLERANCE,
    ) -> None:
        super().__init__(detector_name=detector_name)
        self.default_threshold = default_threshold
        self.diff_tolerance = diff_tolerance

    @staticmethod
    def _to_gray(img: np.ndarray) -> np.ndarray:
        """Convert image ndarray to single-channel uint8 grayscale."""
        if img.ndim == 2:
            return img
        if img.ndim == 3:
            channels = img.shape[2]
            if channels == 4:
                return cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
            if channels == 3:
                return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return img

    def _compute_ssim(
        self,
        golden_gray: np.ndarray,
        inspection_gray: np.ndarray,
    ) -> tuple[float, np.ndarray]:
        """Compute SSIM score and diff image, preferring skimage with OpenCV fallback."""
        try:
            from skimage.metrics import structural_similarity as ssim_metric  # type: ignore

            score, diff_map = ssim_metric(
                golden_gray,
                inspection_gray,
                full=True,
                data_range=255,
            )
            # diff_map from skimage is float in range [-1, 1], normalize to uint8
            diff_uint8 = ((1.0 - diff_map) * 127.5).astype(np.uint8)
            return float(score), diff_uint8
        except Exception as exc:
            logger.debug("skimage.metrics.structural_similarity unavailable: %s, using OpenCV fallback", exc)
            return calculate_opencv_ssim(golden_gray, inspection_gray)

    async def _analyze(
        self,
        golden_roi: ImageSource,
        inspection_roi: ImageSource,
        roi_data: dict[str, Any],
    ) -> AgentResult:
        """
        Analyze structural integrity by comparing golden ROI crop against
        inspection ROI crop using SSIM and pixel difference metrics.
        """
        roi_id = str(roi_data.get("roi_id") or roi_data.get("id") or "structural_roi")
        roi_name = str(roi_data.get("name") or roi_id)
        threshold = float(roi_data.get("threshold") or self.default_threshold)

        # 1. Load images into OpenCV format
        try:
            golden_cv = load_cv_image(golden_roi)
            inspection_cv = load_cv_image(inspection_roi)
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

        gh, gw = golden_cv.shape[:2]
        ih, iw = inspection_cv.shape[:2]

        if gh == 0 or gw == 0 or ih == 0 or iw == 0:
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

        # 2. Convert to grayscale
        golden_gray = self._to_gray(golden_cv)
        inspection_gray = self._to_gray(inspection_cv)

        # 3. Handle dimension matching if slight differences exist
        resized_for_comparison = False
        if (gh, gw) != (ih, iw):
            # Resize inspection crop to golden dimensions for pixel-level SSIM
            inspection_gray = cv2.resize(
                inspection_gray,
                (gw, gh),
                interpolation=cv2.INTER_AREA if (ih > gh or iw > gw) else cv2.INTER_LINEAR,
            )
            resized_for_comparison = True

        # 4. Uniformity check
        golden_std = float(np.std(golden_gray))
        inspection_std = float(np.std(inspection_gray))

        if golden_std < 1e-3 and inspection_std < 1e-3:
            # Both crops flat: compare intensity difference
            diff_mean = abs(float(np.mean(golden_gray)) - float(np.mean(inspection_gray)))
            ssim_score = max(0.0, 1.0 - (diff_mean / 255.0))
            diff_pct = 0.0 if diff_mean <= self.diff_tolerance else 100.0
            mse = float(diff_mean ** 2)
        elif golden_std < 1e-3 or inspection_std < 1e-3:
            # One is flat and other is textured -> severe structural defect
            ssim_score = 0.0
            diff_pct = 100.0
            mse = float(np.mean((golden_gray.astype(float) - inspection_gray.astype(float)) ** 2))
        else:
            # Standard SSIM computation
            raw_ssim, diff_img = self._compute_ssim(golden_gray, inspection_gray)
            ssim_score = max(0.0, min(1.0, raw_ssim))

            # Mean Squared Error (MSE)
            mse = float(np.mean((golden_gray.astype(np.float64) - inspection_gray.astype(np.float64)) ** 2))

            # Diff percentage: pixels exceeding tolerance
            abs_diff = cv2.absdiff(golden_gray, inspection_gray)
            diff_pixels = int(np.count_nonzero(abs_diff > self.diff_tolerance))
            total_pixels = gw * gh
            diff_pct = (diff_pixels / total_pixels) * 100.0 if total_pixels > 0 else 0.0

        # 5. Evaluate findings against threshold
        has_defect = ssim_score < threshold

        if has_defect:
            confidence = max(0.6, min(1.0, 1.0 - ssim_score))
            explanation = (
                f"Structural anomaly detected on {roi_name}: SSIM similarity {ssim_score:.3f} "
                f"is below required threshold {threshold:.2f} (diff: {diff_pct:.1f}%, MSE: {mse:.1f})"
            )
        else:
            confidence = max(0.0, min(1.0, ssim_score))
            explanation = (
                f"Structural integrity verified for {roi_name}: SSIM similarity {ssim_score:.3f} "
                f"meets threshold {threshold:.2f} (diff: {diff_pct:.1f}%, MSE: {mse:.1f})"
            )

        # 6. Extensible component findings placeholder (Day 5 YOLO integration)
        component_findings: list[dict[str, Any]] = roi_data.get("component_findings") or []

        evidence = {
            "ssim_score": round(ssim_score, 4),
            "threshold": round(threshold, 4),
            "mean_squared_error": round(mse, 2),
            "diff_percentage": round(diff_pct, 2),
            "match_status": "defect_detected" if has_defect else "match",
            "dimensions": {"width": gw, "height": gh},
            "inspection_original_dimensions": {"width": iw, "height": ih},
            "resized_for_comparison": resized_for_comparison,
            "component_findings": component_findings,
        }

        return AgentResult(
            agent_type=self.agent_type,
            detector_name=self.detector_name,
            roi_id=roi_id,
            confidence=round(confidence, 3),
            has_defect=has_defect,
            evidence=evidence,
            explanation=explanation,
            raw_output={"ssim_score": ssim_score, "mse": mse, "diff_pct": diff_pct},
        )
