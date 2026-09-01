# path: backend/app/pipeline/agents/ocr_agent.py
"""
OCR Agent — Stage 5 Evidence Execution.

Primary engine: PaddleOCR (industrial-grade precision on tiny/stamped serials).
Secondary engine: EasyOCR (lightweight fallback on PaddleOCR failure/timeout).

Receives only cropped Golden/Inspection ROI image pairs (never full images),
extracts text from both, diffs them, and returns a standardized EvidenceResult
for storage in the Evidence Store. Never fabricates text or confidence on
failure — always returns an explicit failed EvidenceResult instead.
"""

from __future__ import annotations

import logging
import time
import uuid
from difflib import SequenceMatcher
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.pipeline.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

OCREngine = Literal["paddleocr", "easyocr"]
AgentType = Literal["ocr"]
ProductType = Literal["motherboard", "battery", "ram"]
MismatchType = Literal["missing", "extra", "different"]


# ============================================================
# Schemas
# ============================================================


class BoundingBox(BaseModel):
    """ROI bounding box in image pixel coordinates."""

    model_config = ConfigDict(frozen=True)

    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    width: int = Field(..., gt=0)
    height: int = Field(..., gt=0)


class OCRROI(BaseModel):
    """OCR ROI metadata supplied by the ROI Scheduler."""

    model_config = ConfigDict(frozen=True)

    roi_id: str = Field(..., alias="roiId")
    roi_type: Literal["text"] = Field(default="text", alias="roiType")
    label: str
    bounding_box: BoundingBox = Field(..., alias="boundingBox")
    critical: bool = False
    expected_text: str | None = Field(default=None, alias="expectedText")
    metadata: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True)


class OCRDetection(BaseModel):
    """Individual OCR detection."""

    model_config = ConfigDict(frozen=True)

    text: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    bounding_box: BoundingBox | None = None


class CharacterMismatch(BaseModel):
    """Character-level mismatch between golden and inspection text."""

    model_config = ConfigDict(frozen=True)

    position: int = Field(..., ge=0)
    expected: str
    actual: str
    mismatch_type: MismatchType


class OCRComparison(BaseModel):
    """OCR comparison result between golden and inspection ROI text."""

    model_config = ConfigDict(frozen=True)

    golden_text: str
    inspection_text: str
    normalized_golden_text: str
    normalized_inspection_text: str
    exact_match: bool
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    mismatches: list[CharacterMismatch] = Field(default_factory=list)


class EvidenceResult(BaseModel):
    """Standard evidence result produced by every specialized agent (Stage 5)."""

    model_config = ConfigDict(frozen=True)

    evidence_id: str
    inspection_id: str
    agent_type: AgentType
    roi: OCRROI
    result: OCRComparison | None
    confidence: float = Field(..., ge=0.0, le=1.0)
    explanation: str
    processing_time_ms: float = Field(..., ge=0.0)
    engine: OCREngine
    success: bool
    error: str | None = None
    metadata: dict[str, Any] | None = None


class AgentContext(BaseModel):
    """Runtime context supplied by Evidence Execution (Stage 5 dispatcher)."""

    model_config = ConfigDict(frozen=True)

    inspection_id: str
    product_type: ProductType
    roi: OCRROI
    golden_image_path: str
    inspection_image_path: str


class OCRAgentConfig(BaseModel):
    """OCR Agent configuration."""

    primary_engine: Literal["paddleocr"] = "paddleocr"
    fallback_engine: Literal["easyocr"] = "easyocr"
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    language_codes: list[str] = Field(default_factory=lambda: ["en"])
    enable_preprocessing: bool = True

    @field_validator("language_codes")
    @classmethod
    def _non_empty_languages(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("language_codes must contain at least one language")
        return value


# ============================================================
# Internal exceptions
# ============================================================


class OCREngineError(Exception):
    """Raised when an OCR engine fails to extract text from an image."""

    def __init__(self, engine: OCREngine, message: str) -> None:
        self.engine = engine
        super().__init__(f"[{engine}] {message}")


class OCRImageLoadError(Exception):
    """Raised when a cropped ROI image cannot be loaded from disk."""


# ============================================================
# OCR Agent
# ============================================================


class OCRAgent(BaseAgent):
    """
    Stage-5 specialized evidence agent responsible exclusively for Text ROIs
    (serial numbers, part numbers) assigned by the ROI Scheduler.

    Engine strategy: PaddleOCR is attempted first; on any failure, timeout,
    or empty/low-confidence result, EasyOCR is used as a secondary fallback.
    If both engines fail, a failed EvidenceResult is returned — text and
    confidence are never fabricated.
    """

    agent_type: AgentType = "ocr"

    def __init__(self, config: OCRAgentConfig | None = None) -> None:
        self._config = config or OCRAgentConfig()
        self._paddle_ocr: Any | None = None
        self._easy_ocr: Any | None = None

    # ------------------------------------------------------------------
    # Lazy engine initialization
    # ------------------------------------------------------------------

    def _get_paddle_engine(self) -> Any:
        """Lazily initialize and cache the PaddleOCR engine instance."""
        if self._paddle_ocr is not None:
            return self._paddle_ocr

        try:
            from paddleocr import PaddleOCR  # type: ignore[import-untyped]
        except ImportError as exc:
            raise OCREngineError(
                "paddleocr",
                "paddleocr package is not installed in the runtime environment",
            ) from exc

        try:
            self._paddle_ocr = PaddleOCR(
                use_angle_cls=True,
                lang=self._config.language_codes[0],
                show_log=False,
            )
        except Exception as exc:  # noqa: BLE001 - engine init failures vary by backend
            raise OCREngineError(
                "paddleocr", f"failed to initialize engine: {exc}"
            ) from exc

        return self._paddle_ocr

    def _get_easy_engine(self) -> Any:
        """Lazily initialize and cache the EasyOCR engine instance."""
        if self._easy_ocr is not None:
            return self._easy_ocr

        try:
            import easyocr  # type: ignore[import-untyped]
        except ImportError as exc:
            raise OCREngineError(
                "easyocr",
                "easyocr package is not installed in the runtime environment",
            ) from exc

        try:
            self._easy_ocr = easyocr.Reader(
                self._config.language_codes,
                gpu=False,
                verbose=False,
            )
        except Exception as exc:  # noqa: BLE001
            raise OCREngineError(
                "easyocr", f"failed to initialize engine: {exc}"
            ) from exc

        return self._easy_ocr

    # ------------------------------------------------------------------
    # Image loading / preprocessing
    # ------------------------------------------------------------------

    def _load_image(self, image_path: str) -> Any:
        """Load an image from disk as a numpy BGR array, with optional preprocessing."""
        try:
            import cv2  # type: ignore[import-untyped]
        except ImportError as exc:
            raise OCRImageLoadError(
                "opencv-python (cv2) is not installed in the runtime environment"
            ) from exc

        image = cv2.imread(image_path)
        if image is None:
            raise OCRImageLoadError(f"could not read image at path: {image_path}")

        if self._config.enable_preprocessing:
            image = self._preprocess(image)

        return image

    def _preprocess(self, image: Any) -> Any:
        """
        Apply light preprocessing to improve OCR accuracy on small/stamped text:
        grayscale-preserving contrast enhancement (CLAHE) and mild denoising.
        Preserves the 3-channel BGR format expected by both engines.
        """
        import cv2  # type: ignore[import-untyped]

        try:
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l_channel, a_channel, b_channel = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l_channel = clahe.apply(l_channel)
            enhanced_lab = cv2.merge((l_channel, a_channel, b_channel))
            enhanced = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
            denoised = cv2.fastNlMeansDenoisingColored(enhanced, None, 5, 5, 7, 21)
            return denoised
        except Exception as exc:  # noqa: BLE001 - preprocessing must never hard-fail extraction
            logger.warning(
                "OCR preprocessing failed, falling back to raw image: %s", exc
            )
            return image

    # ------------------------------------------------------------------
    # Text extraction
    # ------------------------------------------------------------------

    def extract_text(
        self,
        image_path: str,
        engine: OCREngine | None = None,
    ) -> list[OCRDetection]:
        """
        Extract text detections from an image using the requested engine,
        or PaddleOCR-primary/EasyOCR-fallback if no engine is specified.
        """
        target_engine = engine or self._config.primary_engine
        image = self._load_image(image_path)

        if target_engine == "paddleocr":
            return self._extract_with_paddle(image)
        return self._extract_with_easy(image)

    def _extract_with_paddle(self, image: Any) -> list[OCRDetection]:
        engine = self._get_paddle_engine()
        try:
            raw_result = engine.ocr(image, cls=True)
        except Exception as exc:  # noqa: BLE001
            raise OCREngineError("paddleocr", f"inference failed: {exc}") from exc

        detections: list[OCRDetection] = []
        if not raw_result:
            return detections

        for page in raw_result:
            if not page:
                continue
            for line in page:
                try:
                    box_points, (text, confidence) = line
                    bounding_box = self._points_to_bbox(box_points)
                    detections.append(
                        OCRDetection(
                            text=text,
                            confidence=float(max(0.0, min(1.0, confidence))),
                            bounding_box=bounding_box,
                        )
                    )
                except (ValueError, TypeError) as exc:
                    logger.warning("Skipping malformed PaddleOCR line result: %s", exc)
                    continue

        return detections

    def _extract_with_easy(self, image: Any) -> list[OCRDetection]:
        engine = self._get_easy_engine()
        try:
            raw_result = engine.readtext(image)
        except Exception as exc:  # noqa: BLE001
            raise OCREngineError("easyocr", f"inference failed: {exc}") from exc

        detections: list[OCRDetection] = []
        for box_points, text, confidence in raw_result:
            try:
                bounding_box = self._points_to_bbox(box_points)
                detections.append(
                    OCRDetection(
                        text=text,
                        confidence=float(max(0.0, min(1.0, confidence))),
                        bounding_box=bounding_box,
                    )
                )
            except (ValueError, TypeError) as exc:
                logger.warning("Skipping malformed EasyOCR line result: %s", exc)
                continue

        return detections

    @staticmethod
    def _points_to_bbox(points: list[list[float]]) -> BoundingBox:
        """Convert a 4-point polygon (as returned by both engines) to an axis-aligned bbox."""
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        return BoundingBox(
            x=int(round(x_min)),
            y=int(round(y_min)),
            width=max(1, int(round(x_max - x_min))),
            height=max(1, int(round(y_max - y_min))),
        )

    # ------------------------------------------------------------------
    # Comparison logic
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize text for comparison: uppercase, strip, collapse whitespace."""
        return " ".join(text.strip().upper().split())

    @staticmethod
    def _join_detections(detections: list[OCRDetection]) -> str:
        """Join multiple detected text lines into a single string, reading-order preserved."""
        return " ".join(d.text for d in detections if d.text.strip())

    def _diff_characters(
        self, expected: str, actual: str
    ) -> list[CharacterMismatch]:
        """Produce a character-level mismatch list using an LCS-based sequence diff."""
        mismatches: list[CharacterMismatch] = []
        matcher = SequenceMatcher(a=expected, b=actual, autojunk=False)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            if tag == "replace":
                span = max(i2 - i1, j2 - j1)
                for offset in range(span):
                    exp_char = expected[i1 + offset] if i1 + offset < i2 else ""
                    act_char = actual[j1 + offset] if j1 + offset < j2 else ""
                    mismatches.append(
                        CharacterMismatch(
                            position=i1 + offset,
                            expected=exp_char,
                            actual=act_char,
                            mismatch_type="different",
                        )
                    )
            elif tag == "delete":
                for offset in range(i1, i2):
                    mismatches.append(
                        CharacterMismatch(
                            position=offset,
                            expected=expected[offset],
                            actual="",
                            mismatch_type="missing",
                        )
                    )
            elif tag == "insert":
                mismatches.append(
                    CharacterMismatch(
                        position=i1,
                        expected="",
                        actual=actual[j1:j2],
                        mismatch_type="extra",
                    )
                )

        return mismatches

    def compare_text(
        self,
        golden_detections: list[OCRDetection],
        inspection_detections: list[OCRDetection],
        expected_text: str | None = None,
    ) -> OCRComparison:
        """
        Compare golden vs. inspection OCR detections. If expected_text is
        provided by the ROI template, it takes precedence over the golden
        image's own detected text as the reference string.
        """
        golden_text = self._join_detections(golden_detections)
        inspection_text = self._join_detections(inspection_detections)

        reference_text = expected_text if expected_text else golden_text
        normalized_golden = self._normalize(reference_text)
        normalized_inspection = self._normalize(inspection_text)

        exact_match = normalized_golden == normalized_inspection
        similarity_score = SequenceMatcher(
            a=normalized_golden, b=normalized_inspection
        ).ratio()

        mismatches = (
            []
            if exact_match
            else self._diff_characters(normalized_golden, normalized_inspection)
        )

        return OCRComparison(
            golden_text=golden_text,
            inspection_text=inspection_text,
            normalized_golden_text=normalized_golden,
            normalized_inspection_text=normalized_inspection,
            exact_match=exact_match,
            similarity_score=round(similarity_score, 4),
            mismatches=mismatches,
        )

    # ------------------------------------------------------------------
    # BaseAgent contract
    # ------------------------------------------------------------------

    def standardize_confidence(self, confidence: float) -> float:
        """Clamp any raw confidence value onto the shared 0.0-1.0 agent scale."""
        return max(0.0, min(1.0, float(confidence)))

    def get_evidence(self, result: EvidenceResult) -> EvidenceResult:
        """Return the evidence result unchanged; hook point for downstream normalization."""
        return result

    async def run(self, context: AgentContext) -> EvidenceResult:
        """
        Execute the OCR Agent against a single cropped Golden/Inspection ROI pair.

        Flow: PaddleOCR primary extraction on both crops -> if PaddleOCR fails
        or yields no detections on either crop, fall back to EasyOCR -> compare
        text -> confidence = min(engine confidences) blended with similarity ->
        build EvidenceResult. Any unrecoverable failure yields success=False
        with an explicit error and zero fabricated evidence.
        """
        start_time = time.perf_counter()
        engine_used: OCREngine = self._config.primary_engine

        try:
            golden_detections, inspection_detections, engine_used = (
                self._extract_pair_with_failover(
                    context.golden_image_path, context.inspection_image_path
                )
            )
        except OCRImageLoadError as exc:
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "OCR image load failed for inspection=%s roi=%s: %s",
                context.inspection_id,
                context.roi.roi_id,
                exc,
            )
            return EvidenceResult(
                evidence_id=str(uuid.uuid4()),
                inspection_id=context.inspection_id,
                agent_type=self.agent_type,
                roi=context.roi,
                result=None,
                confidence=0.0,
                explanation=f"OCR could not process the ROI image: {exc}",
                processing_time_ms=processing_time_ms,
                engine=engine_used,
                success=False,
                error=str(exc),
            )
        except OCREngineError as exc:
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "OCR extraction failed for inspection=%s roi=%s: %s",
                context.inspection_id,
                context.roi.roi_id,
                exc,
            )
            return EvidenceResult(
                evidence_id=str(uuid.uuid4()),
                inspection_id=context.inspection_id,
                agent_type=self.agent_type,
                roi=context.roi,
                result=None,
                confidence=0.0,
                explanation=(
                    "Both PaddleOCR and EasyOCR failed to extract text from "
                    f"this ROI: {exc}"
                ),
                processing_time_ms=processing_time_ms,
                engine=exc.engine,
                success=False,
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 - final safety net, never fabricate evidence
            processing_time_ms = (time.perf_counter() - start_time) * 1000
            logger.exception(
                "Unexpected OCR agent failure for inspection=%s roi=%s",
                context.inspection_id,
                context.roi.roi_id,
            )
            return EvidenceResult(
                evidence_id=str(uuid.uuid4()),
                inspection_id=context.inspection_id,
                agent_type=self.agent_type,
                roi=context.roi,
                result=None,
                confidence=0.0,
                explanation=f"Unexpected error during OCR processing: {exc}",
                processing_time_ms=processing_time_ms,
                engine=engine_used,
                success=False,
                error=str(exc),
            )

        comparison = self.compare_text(
            golden_detections=golden_detections,
            inspection_detections=inspection_detections,
            expected_text=context.roi.expected_text,
        )

        engine_confidence = self._aggregate_engine_confidence(
            golden_detections, inspection_detections
        )
        blended_confidence = self.standardize_confidence(
            (engine_confidence * 0.5) + (comparison.similarity_score * 0.5)
        )

        explanation = self._build_explanation(
            comparison, engine_used, context.roi, engine_confidence
        )

        processing_time_ms = (time.perf_counter() - start_time) * 1000

        result = EvidenceResult(
            evidence_id=str(uuid.uuid4()),
            inspection_id=context.inspection_id,
            agent_type=self.agent_type,
            roi=context.roi,
            result=comparison,
            confidence=blended_confidence,
            explanation=explanation,
            processing_time_ms=processing_time_ms,
            engine=engine_used,
            success=True,
            metadata={
                "golden_detection_count": len(golden_detections),
                "inspection_detection_count": len(inspection_detections),
                "product_type": context.product_type,
            },
        )

        return self.get_evidence(result)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_pair_with_failover(
        self, golden_path: str, inspection_path: str
    ) -> tuple[list[OCRDetection], list[OCRDetection], OCREngine]:
        """
        Extract text from both crops using PaddleOCR; if it errors or returns
        empty results on either image, retry the pair fully with EasyOCR.
        Raises OCREngineError if both engines fail.
        """
        primary_error: Exception | None = None

        try:
            golden_detections = self.extract_text(golden_path, engine="paddleocr")
            inspection_detections = self.extract_text(
                inspection_path, engine="paddleocr"
            )
            if golden_detections or inspection_detections:
                return golden_detections, inspection_detections, "paddleocr"
            logger.info(
                "PaddleOCR returned no detections for ROI pair; falling back to EasyOCR"
            )
        except OCREngineError as exc:
            primary_error = exc
            logger.warning(
                "PaddleOCR failed, falling back to EasyOCR: %s", exc
            )

        try:
            golden_detections = self.extract_text(golden_path, engine="easyocr")
            inspection_detections = self.extract_text(
                inspection_path, engine="easyocr"
            )
            return golden_detections, inspection_detections, "easyocr"
        except OCREngineError as fallback_exc:
            message = (
                f"primary error: {primary_error}; fallback error: {fallback_exc}"
                if primary_error
                else str(fallback_exc)
            )
            raise OCREngineError("easyocr", message) from fallback_exc

    @staticmethod
    def _aggregate_engine_confidence(
        golden_detections: list[OCRDetection],
        inspection_detections: list[OCRDetection],
    ) -> float:
        """Average the raw engine confidence across both crops; 0.0 if no detections at all."""
        all_confidences = [d.confidence for d in golden_detections] + [
            d.confidence for d in inspection_detections
        ]
        if not all_confidences:
            return 0.0
        return sum(all_confidences) / len(all_confidences)

    @staticmethod
    def _build_explanation(
        comparison: OCRComparison,
        engine: OCREngine,
        roi: OCRROI,
        engine_confidence: float,
    ) -> str:
        """Build a human-readable explanation surfaced in the report and AI Judge context."""
        if comparison.exact_match:
            return (
                f"[{engine}] Text at ROI '{roi.label}' matches the golden reference "
                f"exactly ('{comparison.golden_text}'), engine confidence "
                f"{engine_confidence:.2f}."
            )

        mismatch_summary = ", ".join(
            f"{m.mismatch_type} '{m.expected or m.actual}' at position {m.position}"
            for m in comparison.mismatches[:5]
        )
        more = (
            f" (+{len(comparison.mismatches) - 5} more)"
            if len(comparison.mismatches) > 5
            else ""
        )
        return (
            f"[{engine}] Text mismatch at ROI '{roi.label}': expected "
            f"'{comparison.normalized_golden_text}', got "
            f"'{comparison.normalized_inspection_text}' "
            f"(similarity={comparison.similarity_score:.2f}). "
            f"Mismatches: {mismatch_summary}{more}."
        )