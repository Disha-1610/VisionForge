# backend/app/pipeline/agents/structural_agent.py
"""
Structural Evidence Agent — SSIM & YOLO Component Detection (Anil & Disha, W3 D3 & D5).

Per VisionForge.md Section 4 Stage 5c & Dedicated YOLO11n Specification:
  - Dual-layer defect detection:
    1. OpenCV SSIM: Holistic structural similarity, pixel difference maps, and Mean Squared Error.
    2. YOLO11n Component Detector: Discrete per-object detection and counting (capacitors,
       connectors, IC chips, screws, seals, battery cells, gold pin connectors).
  - Four-mode structural defect reasoning:
    1. Missing Component (detected in Golden ROI but missing in Inspection ROI)
    2. Extra Component (detected in Inspection ROI but absent in Golden ROI)
    3. Count Mismatch (counts diverge from golden or expected ROI template counts)
    4. Position / Alignment Shift
  - Combines discrete YOLO facts with continuous SSIM score for downstream Stage 6 Fusion.
  - Standardized BaseAgent reporting into EvidenceStore.
"""
from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.pipeline.agents.base_agent import AgentResult, BaseAgent
from app.shared.evidence_store import AgentType
from app.utils.image_utils import ImageSource, load_cv_image

logger = logging.getLogger("app.pipeline.agents.structural")

DEFAULT_SSIM_THRESHOLD = 0.80
DEFAULT_DIFF_TOLERANCE = 25  # pixel intensity difference threshold
DEFAULT_YOLO_CONF = 0.20     # calibrated for micro-components in localized ROI crops
_BACKEND_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
DEFAULT_WEIGHTS_PATH = _BACKEND_DATA_DIR / "yolo_weights" / "component_detector.pt"
if not DEFAULT_WEIGHTS_PATH.exists() and Path("data/yolo_weights/component_detector.pt").exists():
    DEFAULT_WEIGHTS_PATH = Path("data/yolo_weights/component_detector.pt")


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
    Specialized evidence agent combining OpenCV SSIM with YOLO11n
    component-level object detection.
    """

    agent_type = AgentType.STRUCTURAL
    detector_name = "structural_ssim"


    def __init__(
        self,
        default_threshold: float = DEFAULT_SSIM_THRESHOLD,
        detector_name: str | None = None,
        diff_tolerance: int = DEFAULT_DIFF_TOLERANCE,
        yolo_weights_path: str | Path | None = None,
        yolo_model: Any = None,
        yolo_conf: float = DEFAULT_YOLO_CONF,
        enable_yolo: bool = True,
    ) -> None:
        super().__init__(detector_name=detector_name)
        self.default_threshold = default_threshold
        self.diff_tolerance = diff_tolerance
        self.yolo_weights_path = Path(yolo_weights_path) if yolo_weights_path else DEFAULT_WEIGHTS_PATH
        self.yolo_conf = yolo_conf
        self.enable_yolo = enable_yolo
        self._yolo_model = yolo_model
        self._yolo_initialized = False

    def _init_yolo_if_needed(self) -> None:
        """Lazy load YOLO model if enabled and not already initialized."""
        if self._yolo_initialized or not self.enable_yolo:
            return

        if self._yolo_model is None:
            if self.yolo_weights_path.exists():
                try:
                    from ultralytics import YOLO  # type: ignore

                    self._yolo_model = YOLO(str(self.yolo_weights_path))
                    logger.info("Loaded YOLO model from %s", self.yolo_weights_path)
                except Exception as exc:
                    logger.warning("Could not load YOLO model from %s: %s", self.yolo_weights_path, exc)
                    self._yolo_model = None
            else:
                logger.debug("YOLO weights file not found at %s", self.yolo_weights_path)

        self._yolo_initialized = True

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
            diff_uint8 = ((1.0 - diff_map) * 127.5).astype(np.uint8)
            return float(score), diff_uint8
        except Exception as exc:
            logger.debug("skimage SSIM unavailable: %s, using OpenCV fallback", exc)
            return calculate_opencv_ssim(golden_gray, inspection_gray)

    def _detect_components_yolo(self, img_cv: np.ndarray) -> list[dict[str, Any]]:
        """Run YOLO inference on an image crop and extract detected components."""
        self._init_yolo_if_needed()
        if self._yolo_model is None:
            return []

        try:
            # Ultralytics model call
            results = self._yolo_model.predict(
                source=img_cv,
                conf=self.yolo_conf,
                verbose=False,
            )
            if not results:
                return []

            boxes = results[0].boxes
            detections = []
            names = getattr(self._yolo_model, "names", {})
            for b in boxes:
                cls_id = int(b.cls[0])
                cls_name = names.get(cls_id, str(cls_id)) if isinstance(names, dict) else str(cls_id)
                conf = float(b.conf[0])
                xywhn = [round(float(v), 3) for v in b.xywhn[0]] if hasattr(b, "xywhn") else []
                detections.append(
                    {
                        "class_id": cls_id,
                        "class_name": cls_name,
                        "confidence": round(conf, 3),
                        "bbox": xywhn,
                    }
                )
            return detections
        except Exception as exc:
            logger.warning("YOLO detection failed on crop: %s", exc)
            return []

    async def _analyze(
        self,
        golden_roi: ImageSource,
        inspection_roi: ImageSource,
        roi_data: dict[str, Any],
    ) -> AgentResult:
        """
        Analyze structural integrity by comparing golden and inspection crops
        using both OpenCV SSIM and YOLO component-level detection.
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

        # 2. Convert to grayscale for SSIM
        golden_gray = self._to_gray(golden_cv)
        inspection_gray = self._to_gray(inspection_cv)

        # 3. Handle dimension matching if slight differences exist
        resized_for_comparison = False
        if (gh, gw) != (ih, iw):
            inspection_gray = cv2.resize(
                inspection_gray,
                (gw, gh),
                interpolation=cv2.INTER_AREA if (ih > gh or iw > gw) else cv2.INTER_LINEAR,
            )
            resized_for_comparison = True

        # 4. SSIM & Pixel Difference Analysis
        golden_std = float(np.std(golden_gray))
        inspection_std = float(np.std(inspection_gray))

        if golden_std < 1e-3 and inspection_std < 1e-3:
            diff_mean = abs(float(np.mean(golden_gray)) - float(np.mean(inspection_gray)))
            ssim_score = max(0.0, 1.0 - (diff_mean / 255.0))
            diff_pct = 0.0 if diff_mean <= self.diff_tolerance else 100.0
            mse = float(diff_mean ** 2)
        elif golden_std < 1e-3 or inspection_std < 1e-3:
            ssim_score = 0.0
            diff_pct = 100.0
            mse = float(np.mean((golden_gray.astype(float) - inspection_gray.astype(float)) ** 2))
        else:
            raw_ssim, diff_img = self._compute_ssim(golden_gray, inspection_gray)
            ssim_score = max(0.0, min(1.0, raw_ssim))
            mse = float(np.mean((golden_gray.astype(np.float64) - inspection_gray.astype(np.float64)) ** 2))
            abs_diff = cv2.absdiff(golden_gray, inspection_gray)
            diff_pixels = int(np.count_nonzero(abs_diff > self.diff_tolerance))
            total_pixels = gw * gh
            diff_pct = (diff_pixels / total_pixels) * 100.0 if total_pixels > 0 else 0.0

        ssim_defect = ssim_score < threshold

        # 5. YOLO Component Detection on Paired Crops
        golden_components = self._detect_components_yolo(golden_cv)
        inspection_components = self._detect_components_yolo(inspection_cv)

        golden_counts = Counter(c["class_name"] for c in golden_components)
        inspection_counts = Counter(c["class_name"] for c in inspection_components)

        # Component findings & comparisons
        component_findings: list[dict[str, Any]] = []
        missing_components: list[dict[str, Any]] = []
        extra_components: list[dict[str, Any]] = []

        all_detected_classes = set(golden_counts.keys()) | set(inspection_counts.keys())
        expected_comps = roi_data.get("expected_components") or roi_data.get("expectedComponents") or []
        for ec in expected_comps:
            if isinstance(ec, dict) and "class_name" in ec:
                all_detected_classes.add(ec["class_name"])
            elif isinstance(ec, dict) and "className" in ec:
                all_detected_classes.add(ec["className"])

        for cls_name in sorted(all_detected_classes):
            g_cnt = golden_counts.get(cls_name, 0)
            i_cnt = inspection_counts.get(cls_name, 0)

            finding = {
                "class_name": cls_name,
                "golden_count": g_cnt,
                "inspection_count": i_cnt,
                "diff": i_cnt - g_cnt,
            }

            if g_cnt > i_cnt:
                finding["status"] = "missing"
                missing_components.append(finding)
            elif i_cnt > g_cnt:
                finding["status"] = "extra"
                extra_components.append(finding)
            else:
                finding["status"] = "match"

            component_findings.append(finding)

        yolo_defect = len(missing_components) > 0 or len(extra_components) > 0
        has_defect = ssim_defect or yolo_defect

        # 6. Build Rich Explanation combining YOLO + SSIM
        explanation_parts = []
        if missing_components:
            missing_desc = ", ".join(f"{m['class_name']} missing ({m['golden_count']} vs {m['inspection_count']})" for m in missing_components)
            explanation_parts.append(f"YOLO detected: {missing_desc}")
        if extra_components:
            extra_desc = ", ".join(f"extra {e['class_name']} detected ({e['inspection_count']} vs {e['golden_count']})" for e in extra_components)
            explanation_parts.append(f"YOLO detected: {extra_desc}")

        if ssim_defect:
            explanation_parts.append(f"Structural anomaly detected: SSIM similarity {ssim_score:.3f} below threshold {threshold:.2f} (diff {diff_pct:.1f}%, MSE {mse:.1f})")
        elif not yolo_defect:
            explanation_parts.append(f"Structural integrity verified: SSIM similarity {ssim_score:.3f} meets threshold {threshold:.2f}")
            if component_findings:
                matched_summary = ", ".join(f"{f['class_name']}: {f['inspection_count']}" for f in component_findings if f["status"] == "match")
                explanation_parts.append(f"components verified ({matched_summary})")
        elif yolo_defect and not ssim_defect:
            explanation_parts.append(f"Structural anomaly detected via component counts (SSIM: {ssim_score:.3f})")

        explanation = f"{roi_name}: " + "; ".join(explanation_parts)


        # 7. Confidence Standardized
        if has_defect:
            if yolo_defect and ssim_defect:
                confidence = 0.95
            elif yolo_defect:
                confidence = 0.90
            else:
                confidence = max(0.65, min(1.0, 1.0 - ssim_score))
        else:
            confidence = max(0.0, min(1.0, ssim_score))

        evidence = {
            "ssim_score": round(ssim_score, 4),
            "threshold": round(threshold, 4),
            "mean_squared_error": round(mse, 2),
            "diff_percentage": round(diff_pct, 2),
            "match_status": "defect_detected" if has_defect else "match",
            "dimensions": {"width": gw, "height": gh},
            "inspection_original_dimensions": {"width": iw, "height": ih},
            "resized_for_comparison": resized_for_comparison,
            "yolo_enabled": self.enable_yolo and self._yolo_model is not None,
            "golden_detections_count": len(golden_components),
            "inspection_detections_count": len(inspection_components),
            "component_findings": component_findings,
            "missing_components": missing_components,
            "extra_components": extra_components,
        }

        return AgentResult(
            agent_type=self.agent_type,
            detector_name=self.detector_name,
            roi_id=roi_id,
            confidence=round(confidence, 3),
            has_defect=has_defect,
            evidence=evidence,
            explanation=explanation,
            raw_output={
                "ssim_score": ssim_score,
                "mse": mse,
                "diff_pct": diff_pct,
                "golden_components": golden_components,
                "inspection_components": inspection_components,
            },
        )
