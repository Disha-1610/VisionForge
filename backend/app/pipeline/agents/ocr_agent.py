# backend/app/pipeline/agents/ocr_agent.py
"""
OCR Evidence Agent (Disha, W3 D2).

Per VisionForge.md Section 4 Stage 5a & Section 2:
  - Primary engine: PaddleOCR (industrial precision on stamped/micro serials).
  - Secondary / Fallback engine: EasyOCR (local, CPU/GPU capable).
  - Inspects text ROIs (serial numbers, part numbers, batch IDs).
  - Compares extracted text from inspection ROI against golden ROI or expected text.
  - Generates character-level diff analysis and similarity metrics.
  - Never fabricates text or confidence on failure; adheres to BaseAgent contract.
"""
from __future__ import annotations

import difflib
import logging
import re
from typing import Any

import cv2
import numpy as np

from app.pipeline.agents.base_agent import AgentResult, BaseAgent
from app.shared.evidence_store import AgentType
from app.utils.image_utils import ImageSource, load_cv_image

logger = logging.getLogger("app.pipeline.agents.ocr")

DEFAULT_OCR_THRESHOLD = 0.85


def normalize_text(text: str) -> str:
    """Normalize text for consistent comparison (uppercase, trimmed, normalized whitespace)."""
    if not text:
        return ""
    # Strip control characters, normalize whitespace
    cleaned = re.sub(r"\s+", " ", text.strip().upper())
    return cleaned


def find_character_mismatches(expected: str, actual: str) -> list[dict[str, Any]]:
    """
    Identify character-level differences between expected and actual text
    using difflib.SequenceMatcher.
    """
    matcher = difflib.SequenceMatcher(None, expected, actual)
    mismatches: list[dict[str, Any]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        mismatches.append(
            {
                "type": tag,  # 'replace', 'delete', 'insert'
                "expected_pos": (i1, i2),
                "actual_pos": (j1, j2),
                "expected_char": expected[i1:i2],
                "actual_char": actual[j1:j2],
            }
        )
    return mismatches


class OCRAgent(BaseAgent):
    """
    Specialized evidence agent for textual components (serial numbers,
    part codes, MAC addresses, QC text).
    """

    agent_type = AgentType.OCR
    detector_name = "ocr_agent"

    def __init__(
        self,
        default_threshold: float = DEFAULT_OCR_THRESHOLD,
        languages: list[str] | None = None,
        detector_name: str | None = None,
        reader: Any = None,
        paddle_ocr: Any = None,
    ) -> None:
        super().__init__(detector_name=detector_name)
        self.default_threshold = default_threshold
        self.languages = languages or ["en"]
        self._easyocr_reader = reader
        self._paddle_ocr = paddle_ocr
        self._engine_initialized = False

    def _init_engines_if_needed(self) -> None:
        """Lazy initialization of OCR engines."""
        if self._engine_initialized:
            return

        # 1. Try PaddleOCR if not injected
        if self._paddle_ocr is None:
            try:
                from paddleocr import PaddleOCR  # type: ignore

                self._paddle_ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
                logger.info("PaddleOCR engine initialized successfully")
            except Exception as exc:
                logger.debug("PaddleOCR not available or failed to load: %s", exc)
                self._paddle_ocr = None

        # 2. Try EasyOCR if not injected
        if self._easyocr_reader is None:
            try:
                import easyocr  # type: ignore

                self._easyocr_reader = easyocr.Reader(self.languages, gpu=False)
                logger.info("EasyOCR engine initialized successfully")
            except Exception as exc:
                logger.debug("EasyOCR not available or failed to load: %s", exc)
                self._easyocr_reader = None

        self._engine_initialized = True

    def _extract_with_paddle(self, img: np.ndarray) -> tuple[str, float]:
        """Extract text and confidence using PaddleOCR."""
        if self._paddle_ocr is None:
            raise RuntimeError("PaddleOCR not initialized")

        result = self._paddle_ocr.ocr(img, cls=True)
        if not result or not result[0]:
            return "", 0.0

        texts = []
        confs = []
        for line in result[0]:
            if line and len(line) >= 2:
                text, conf = line[1]
                texts.append(str(text))
                confs.append(float(conf))

        combined_text = " ".join(texts).strip()
        avg_conf = float(np.mean(confs)) if confs else 0.0
        return combined_text, avg_conf

    def _extract_with_easyocr(self, img: np.ndarray) -> tuple[str, float]:
        """Extract text and confidence using EasyOCR."""
        if self._easyocr_reader is None:
            raise RuntimeError("EasyOCR not initialized")

        # EasyOCR accepts RGB or BGR numpy array
        results = self._easyocr_reader.readtext(img)
        if not results:
            return "", 0.0

        texts = []
        confs = []
        for res in results:
            # Format: (bbox, text, prob)
            if len(res) >= 3:
                texts.append(str(res[1]))
                confs.append(float(res[2]))
            elif len(res) == 2:
                texts.append(str(res[1]))
                confs.append(1.0)

        combined_text = " ".join(texts).strip()
        avg_conf = float(np.mean(confs)) if confs else 0.0
        return combined_text, avg_conf

    def extract_text(self, img: np.ndarray) -> tuple[str, float, str]:
        """
        Extract text from an image crop, trying PaddleOCR first then EasyOCR.
        Returns: (extracted_text, confidence, engine_used)
        """
        self._init_engines_if_needed()

        errors: list[str] = []
        # Try PaddleOCR first
        if self._paddle_ocr is not None:
            try:
                text, conf = self._extract_with_paddle(img)
                if text:
                    return text, conf, "paddleocr"
            except Exception as exc:
                errors.append(f"PaddleOCR error: {exc}")
                logger.warning("PaddleOCR extraction failed: %s, falling back to EasyOCR", exc)

        # Fallback to EasyOCR
        if self._easyocr_reader is not None:
            try:
                text, conf = self._extract_with_easyocr(img)
                return text, conf, "easyocr"
            except Exception as exc:
                errors.append(f"EasyOCR error: {exc}")
                logger.warning("EasyOCR extraction failed: %s", exc)

        if errors:
            raise RuntimeError(f"OCR extraction failed: {'; '.join(errors)}")
        raise RuntimeError("No OCR engine available or all extraction attempts failed")


    @staticmethod
    def _preprocess_crop(img: np.ndarray) -> np.ndarray:
        """Preprocess crop for enhanced OCR readability."""
        if img.ndim == 3 and img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img

    async def _analyze(
        self,
        golden_roi: ImageSource,
        inspection_roi: ImageSource,
        roi_data: dict[str, Any],
    ) -> AgentResult:
        """
        Analyze text ROI by extracting text from the inspection ROI and
        comparing against golden ROI or expected text from checkpoints.
        """
        roi_id = str(roi_data.get("roi_id") or roi_data.get("id") or "ocr_roi")
        threshold = float(roi_data.get("threshold") or self.default_threshold)

        # 1. Load images
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
                evidence={"error": f"Failed to load ROI image: {exc}"},
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

        # 2. Determine expected text
        # Check roi_data for checkpoints or explicit expected_text
        expected_text = ""
        checkpoints = roi_data.get("checkpoints") or []
        for cp in checkpoints:
            if isinstance(cp, dict) and cp.get("expected_value"):
                expected_text = str(cp["expected_value"])
                break

        if not expected_text:
            expected_text = str(roi_data.get("expected_text") or "")

        # 3. Perform OCR Extraction
        golden_cv_pre = self._preprocess_crop(golden_cv)
        inspection_cv_pre = self._preprocess_crop(inspection_cv)

        # Extract inspection text
        try:
            actual_text, actual_conf, engine_used = self.extract_text(inspection_cv_pre)
        except Exception as exc:
            logger.error("OCR extraction failed on inspection crop: %s", exc)
            return AgentResult(
                agent_type=self.agent_type,
                detector_name=self.detector_name,
                roi_id=roi_id,
                confidence=0.0,
                has_defect=True,
                evidence={"error": str(exc)},
                explanation=f"OCR extraction failed on inspection sample: {exc}",
                failed=True,
                failure_reason=str(exc),
            )

        # If expected text was not in metadata, extract it from golden crop
        golden_extracted = ""
        if not expected_text:
            try:
                golden_extracted, _g_conf, _ = self.extract_text(golden_cv_pre)
                expected_text = golden_extracted
            except Exception as exc:
                logger.warning("Could not extract text from golden crop: %s", exc)

        # 4. Compare Normalized Strings
        norm_expected = normalize_text(expected_text)
        norm_actual = normalize_text(actual_text)

        if not norm_expected and not norm_actual:
            # Both images have no readable text
            similarity = 1.0
            has_defect = False
            explanation = f"No text detected in both golden and inspection crops for {roi_id}"
            mismatches: list[dict[str, Any]] = []
        elif not norm_expected or not norm_actual:
            # One has text, one does not -> defect
            similarity = 0.0
            has_defect = True
            explanation = (
                f"Text absence mismatch on {roi_id}: expected '{norm_expected}', "
                f"extracted '{norm_actual}'"
            )
            mismatches = find_character_mismatches(norm_expected, norm_actual)
        else:
            matcher = difflib.SequenceMatcher(None, norm_expected, norm_actual)
            similarity = float(matcher.ratio())
            has_defect = similarity < threshold
            mismatches = find_character_mismatches(norm_expected, norm_actual)

            if has_defect:
                explanation = (
                    f"Text mismatch on {roi_id}: expected '{norm_expected}', "
                    f"extracted '{norm_actual}' (similarity {similarity:.1%} below threshold {threshold:.1%})"
                )
            else:
                explanation = (
                    f"Text verified on {roi_id}: '{norm_actual}' matches expected '{norm_expected}' "
                    f"(similarity {similarity:.1%} >= {threshold:.1%})"
                )

        # Standardize confidence
        # When defect detected, confidence in the defect finding is high when similarity is low.
        # When matching, confidence reflects both OCR extraction quality and text similarity.
        if has_defect:
            result_confidence = max(0.6, min(1.0, 1.0 - similarity))
        else:
            result_confidence = max(0.0, min(1.0, (similarity + actual_conf) / 2.0 if actual_conf > 0 else similarity))

        evidence = {
            "expected_text": expected_text,
            "extracted_text": actual_text,
            "normalized_expected": norm_expected,
            "normalized_extracted": norm_actual,
            "similarity": round(similarity, 4),
            "threshold": round(threshold, 4),
            "match_status": "mismatch" if has_defect else "match",
            "mismatches": mismatches,
            "ocr_confidence": round(actual_conf, 3),
            "engine_used": engine_used,
        }

        return AgentResult(
            agent_type=self.agent_type,
            detector_name=self.detector_name,
            roi_id=roi_id,
            confidence=round(result_confidence, 3),
            has_defect=has_defect,
            evidence=evidence,
            explanation=explanation,
            raw_output={"extracted_raw": actual_text, "engine": engine_used},
        )
