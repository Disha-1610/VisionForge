# ============================================================
# backend/app/pipeline/agents/structural_agent.py
# ============================================================

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Sequence

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator
from skimage.metrics import structural_similarity as ssim_metric

from app.pipeline.agents.base_agent import BaseAgent
from app.shared.evidence_store import EvidenceStore

logger = logging.getLogger(__name__)

try:
    from ultralytics import YOLO
except ImportError as exc:  # pragma: no cover - hard dependency in prod
    raise ImportError(
        "ultralytics is required for structural_agent.py "
        "(pip install ultralytics)"
    ) from exc


# ------------------------------------------------------------
# Enums
# ------------------------------------------------------------

class ProductType(str, Enum):
    MOTHERBOARD = "MOTHERBOARD"
    BATTERY = "BATTERY"
    RAM = "RAM"


class AgentName(str, Enum):
    OCR = "ocr"
    LABEL = "label"
    STRUCTURAL = "structural"
    VLM = "vlm"


class EvidenceStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNCERTAIN = "UNCERTAIN"
    ERROR = "ERROR"


class StructuralComponentClass(str, Enum):
    CAPACITOR = "capacitor"
    RESISTOR = "resistor"
    IC_CHIP = "ic_chip"
    CONNECTOR = "connector"
    SCREW = "screw"
    TERMINAL = "terminal"
    SEAL = "seal"
    BATTERY_CELL = "battery_cell"
    RAM_IC_CHIP = "ram_ic_chip"
    GOLD_PIN_CONNECTOR = "gold_pin_connector"


# Fixed class-index mapping baked into component_detector.pt (10-class shared model)
YOLO_CLASS_INDEX_MAP: dict[int, StructuralComponentClass] = {
    0: StructuralComponentClass.CAPACITOR,
    1: StructuralComponentClass.RESISTOR,
    2: StructuralComponentClass.IC_CHIP,
    3: StructuralComponentClass.CONNECTOR,
    4: StructuralComponentClass.SCREW,
    5: StructuralComponentClass.TERMINAL,
    6: StructuralComponentClass.SEAL,
    7: StructuralComponentClass.BATTERY_CELL,
    8: StructuralComponentClass.RAM_IC_CHIP,
    9: StructuralComponentClass.GOLD_PIN_CONNECTOR,
}

PRODUCT_CLASS_MAP: dict[ProductType, tuple[StructuralComponentClass, ...]] = {
    ProductType.MOTHERBOARD: (
        StructuralComponentClass.CAPACITOR,
        StructuralComponentClass.RESISTOR,
        StructuralComponentClass.IC_CHIP,
        StructuralComponentClass.CONNECTOR,
        StructuralComponentClass.SCREW,
    ),
    ProductType.BATTERY: (
        StructuralComponentClass.TERMINAL,
        StructuralComponentClass.SEAL,
        StructuralComponentClass.BATTERY_CELL,
    ),
    ProductType.RAM: (
        StructuralComponentClass.RAM_IC_CHIP,
        StructuralComponentClass.GOLD_PIN_CONNECTOR,
    ),
}


# ------------------------------------------------------------
# Pydantic v2 schemas (contract types)
# ------------------------------------------------------------

class BoundingBox(BaseModel):
    model_config = ConfigDict(frozen=True)

    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)


class ROIMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    roi_id: str = Field(alias="roiId")
    roi_type: str = Field(default="STRUCTURAL", alias="roiType")
    name: str
    bounding_box: BoundingBox = Field(alias="boundingBox")
    critical: bool = False
    priority: int = 0

    @field_validator("roi_type")
    @classmethod
    def validate_roi_type(cls, v: str) -> str:
        if v != "STRUCTURAL":
            raise ValueError("structural_agent only accepts ROIs of type STRUCTURAL")
        return v

    model_config = ConfigDict(frozen=True, populate_by_name=True)


class ImagePair(BaseModel):
    model_config = ConfigDict(frozen=True)

    golden_image_path: str = Field(alias="goldenImagePath")
    inspection_image_path: str = Field(alias="inspectionImagePath")
    angle_id: Optional[str] = Field(default=None, alias="angleId")

    model_config = ConfigDict(frozen=True, populate_by_name=True)


class StructuralComponentDetection(BaseModel):
    model_config = ConfigDict(frozen=True)

    class_id: int = Field(alias="classId")
    class_name: StructuralComponentClass = Field(alias="className")
    confidence: float = Field(ge=0.0, le=1.0)
    bounding_box: BoundingBox = Field(alias="boundingBox")

    model_config = ConfigDict(frozen=True, populate_by_name=True)


class ComponentCount(BaseModel):
    model_config = ConfigDict(frozen=True)

    class_name: StructuralComponentClass = Field(alias="className")
    expected_count: int = Field(alias="expectedCount", ge=0)
    detected_count: int = Field(alias="detectedCount", ge=0)
    difference: int
    missing: bool
    extra: bool

    model_config = ConfigDict(frozen=True, populate_by_name=True)


class SSIMResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    score: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    passed: bool


class YOLOResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    model_path: str = Field(alias="modelPath")
    detections: tuple[StructuralComponentDetection, ...]
    component_counts: tuple[ComponentCount, ...] = Field(alias="componentCounts")
    confidence: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(frozen=True, populate_by_name=True)


class StructuralComparison(BaseModel):
    model_config = ConfigDict(frozen=True)

    ssim: SSIMResult
    yolo: YOLOResult
    structural_anomaly: bool = Field(alias="structuralAnomaly")
    missing_components: tuple[StructuralComponentClass, ...] = Field(alias="missingComponents")
    extra_components: tuple[StructuralComponentClass, ...] = Field(alias="extraComponents")

    model_config = ConfigDict(frozen=True, populate_by_name=True)


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str = Field(alias="evidenceId")
    inspection_id: str = Field(alias="inspectionId")
    agent: AgentName
    roi: ROIMetadata
    status: EvidenceStatus
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str
    processing_time_ms: float = Field(alias="processingTimeMs", ge=0.0)
    comparison: StructuralComparison
    created_at: str = Field(alias="createdAt")

    model_config = ConfigDict(frozen=True, populate_by_name=True)


class StructuralAgentInput(BaseModel):
    model_config = ConfigDict(frozen=True)

    inspection_id: str = Field(alias="inspectionId")
    product_type: ProductType = Field(alias="productType")
    roi: ROIMetadata
    image_pair: ImagePair = Field(alias="imagePair")

    model_config = ConfigDict(frozen=True, populate_by_name=True)


@dataclass(frozen=True)
class StructuralAgentConfig:
    ssim_threshold: float = 0.75
    yolo_confidence_threshold: float = 0.45
    yolo_iou_threshold: float = 0.45
    yolo_weights_path: str = "data/yolo_weights/component_detector.pt"
    enabled_classes: tuple[StructuralComponentClass, ...] = field(
        default_factory=lambda: tuple(StructuralComponentClass)
    )


# ------------------------------------------------------------
# Domain-specific exceptions
# ------------------------------------------------------------

class StructuralAgentError(Exception):
    """Base exception for structural agent failures."""


class ImageLoadError(StructuralAgentError):
    """Raised when an image cannot be read or decoded from disk."""


class YOLOModelLoadError(StructuralAgentError):
    """Raised when the YOLO11n weights fail to load."""


class YOLOInferenceError(StructuralAgentError):
    """Raised when YOLO inference fails on a given image."""


class SSIMComputationError(StructuralAgentError):
    """Raised when SSIM cannot be computed on the golden/inspection ROI pair."""


# ------------------------------------------------------------
# Structural Agent implementation
# ------------------------------------------------------------

class StructuralAgent(BaseAgent):
    """
    Structural Agent — SSIM + YOLO11n component-level comparison.

    Combines a holistic pixel-similarity signal (SSIM) with a discrete,
    per-object detection signal (YOLO11n) so that Stage 6 (Evidence Fusion)
    can weigh both independently rather than letting either silently
    override the other.
    """

    name: str = AgentName.STRUCTURAL.value
    version: str = "1.0.0"

    def __init__(
        self,
        evidence_store: EvidenceStore,
        config: Optional[StructuralAgentConfig] = None,
    ) -> None:
        self._evidence_store = evidence_store
        self._config = config or StructuralAgentConfig()
        self._yolo_model: Optional[YOLO] = None
        self._load_yolo_model()

    # ----------------------------------------------------------------
    # Model lifecycle
    # ----------------------------------------------------------------

    def _load_yolo_model(self) -> None:
        try:
            self._yolo_model = YOLO(self._config.yolo_weights_path)
            logger.info(
                "structural_agent: loaded YOLO11n weights from %s",
                self._config.yolo_weights_path,
            )
        except Exception as exc:
            logger.error(
                "structural_agent: failed to load YOLO weights from %s: %s",
                self._config.yolo_weights_path,
                exc,
                exc_info=True,
            )
            raise YOLOModelLoadError(
                f"Could not load YOLO11n weights at '{self._config.yolo_weights_path}'"
            ) from exc

    # ----------------------------------------------------------------
    # Public entrypoint
    # ----------------------------------------------------------------

    async def run(self, input_data: StructuralAgentInput) -> Evidence:
        """
        Execute the full structural comparison for one ROI pair and
        persist the resulting evidence to the Evidence Store.
        """
        start_time = time.perf_counter()
        evidence_id = str(uuid.uuid4())

        try:
            golden_roi_path, inspection_roi_path = self._crop_roi_pair(
                input_data.image_pair, input_data.roi
            )

            ssim_result = await self.calculate_ssim(
                golden_roi_path, inspection_roi_path
            )

            enabled_classes = self._resolve_enabled_classes(input_data.product_type)

            golden_detections = await self.detect_components(
                golden_roi_path,
                self._config.yolo_confidence_threshold,
                self._config.yolo_iou_threshold,
                enabled_classes,
            )
            inspection_detections = await self.detect_components(
                inspection_roi_path,
                self._config.yolo_confidence_threshold,
                self._config.yolo_iou_threshold,
                enabled_classes,
            )

            component_counts = self.compare_component_counts(
                golden_detections, inspection_detections, enabled_classes
            )

            yolo_confidence = self._aggregate_yolo_confidence(inspection_detections)

            yolo_result = YOLOResult(
                modelPath=self._config.yolo_weights_path,
                detections=tuple(inspection_detections),
                componentCounts=tuple(component_counts),
                confidence=yolo_confidence,
            )

            comparison = self.build_comparison(ssim_result, yolo_result)
            confidence = self.calculate_confidence(ssim_result, yolo_result)
            explanation = self.build_explanation(comparison)
            status = self._determine_status(comparison)

            processing_time_ms = (time.perf_counter() - start_time) * 1000.0

            evidence = Evidence(
                evidenceId=evidence_id,
                inspectionId=input_data.inspection_id,
                agent=AgentName.STRUCTURAL,
                roi=input_data.roi,
                status=status,
                confidence=confidence,
                explanation=explanation,
                processingTimeMs=processing_time_ms,
                comparison=comparison,
                createdAt=datetime.now(timezone.utc).isoformat(),
            )

            await self._evidence_store.append(evidence)
            logger.info(
                "structural_agent: evidence %s stored for inspection=%s roi=%s status=%s conf=%.3f",
                evidence_id,
                input_data.inspection_id,
                input_data.roi.roi_id,
                status.value,
                confidence,
            )
            return evidence

        except StructuralAgentError as exc:
            processing_time_ms = (time.perf_counter() - start_time) * 1000.0
            logger.error(
                "structural_agent: known failure for inspection=%s roi=%s: %s",
                input_data.inspection_id,
                input_data.roi.roi_id,
                exc,
                exc_info=True,
            )
            error_evidence = self._build_error_evidence(
                evidence_id, input_data, processing_time_ms, str(exc)
            )
            await self._evidence_store.append(error_evidence)
            return error_evidence

        except Exception as exc:  # noqa: BLE001 - agent must never crash the pipeline
            processing_time_ms = (time.perf_counter() - start_time) * 1000.0
            logger.critical(
                "structural_agent: unexpected failure for inspection=%s roi=%s: %s",
                input_data.inspection_id,
                input_data.roi.roi_id,
                exc,
                exc_info=True,
            )
            error_evidence = self._build_error_evidence(
                evidence_id,
                input_data,
                processing_time_ms,
                f"Unexpected error: {exc}",
            )
            await self._evidence_store.append(error_evidence)
            return error_evidence

    # ----------------------------------------------------------------
    # SSIM
    # ----------------------------------------------------------------

    async def calculate_ssim(
        self,
        golden_image_path: str,
        inspection_image_path: str,
    ) -> SSIMResult:
        try:
            golden_img = self._load_grayscale_image(golden_image_path)
            inspection_img = self._load_grayscale_image(inspection_image_path)

            golden_resized, inspection_resized = self._align_dimensions(
                golden_img, inspection_img
            )

            score, _ = ssim_metric(
                golden_resized,
                inspection_resized,
                full=True,
                data_range=255,
            )
            normalized_score = float(np.clip(score, 0.0, 1.0))

            return SSIMResult(
                score=normalized_score,
                threshold=self._config.ssim_threshold,
                passed=normalized_score >= self._config.ssim_threshold,
            )
        except ImageLoadError:
            raise
        except Exception as exc:
            raise SSIMComputationError(
                f"SSIM computation failed between '{golden_image_path}' "
                f"and '{inspection_image_path}': {exc}"
            ) from exc

    def _load_grayscale_image(self, image_path: str) -> np.ndarray:
        image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ImageLoadError(f"Could not read image at path: {image_path}")
        return image

    def _align_dimensions(
        self, img_a: np.ndarray, img_b: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        if img_a.shape == img_b.shape:
            return img_a, img_b
        target_h = min(img_a.shape[0], img_b.shape[0])
        target_w = min(img_a.shape[1], img_b.shape[1])
        if target_h <= 0 or target_w <= 0:
            raise SSIMComputationError(
                "Cannot align images with non-positive dimensions after resize"
            )
        resized_a = cv2.resize(img_a, (target_w, target_h), interpolation=cv2.INTER_AREA)
        resized_b = cv2.resize(img_b, (target_w, target_h), interpolation=cv2.INTER_AREA)
        return resized_a, resized_b

    # ----------------------------------------------------------------
    # YOLO
    # ----------------------------------------------------------------

    async def detect_components(
        self,
        image_path: str,
        confidence_threshold: float,
        iou_threshold: float,
        enabled_classes: Sequence[StructuralComponentClass],
    ) -> list[StructuralComponentDetection]:
        if self._yolo_model is None:
            raise YOLOModelLoadError("YOLO model is not loaded")

        allowed_indices = {
            idx
            for idx, cls in YOLO_CLASS_INDEX_MAP.items()
            if cls in enabled_classes
        }
        if not allowed_indices:
            raise YOLOInferenceError(
                "No enabled classes resolved for this product type; "
                "cannot run component detection"
            )

        try:
            results = self._yolo_model.predict(
                source=image_path,
                conf=confidence_threshold,
                iou=iou_threshold,
                classes=sorted(allowed_indices),
                verbose=False,
            )
        except FileNotFoundError as exc:
            raise ImageLoadError(f"Image not found for YOLO inference: {image_path}") from exc
        except Exception as exc:
            raise YOLOInferenceError(
                f"YOLO inference failed on '{image_path}': {exc}"
            ) from exc

        if not results:
            return []

        detections: list[StructuralComponentDetection] = []
        result = results[0]
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return []

        for box in boxes:
            try:
                class_id = int(box.cls.item())
                confidence = float(box.conf.item())
                xyxy = box.xyxy[0].tolist()
                x1, y1, x2, y2 = xyxy

                class_name = YOLO_CLASS_INDEX_MAP.get(class_id)
                if class_name is None:
                    logger.warning(
                        "structural_agent: unmapped YOLO class_id=%s skipped for %s",
                        class_id,
                        image_path,
                    )
                    continue

                detections.append(
                    StructuralComponentDetection(
                        classId=class_id,
                        className=class_name,
                        confidence=confidence,
                        boundingBox=BoundingBox(
                            x=float(x1),
                            y=float(y1),
                            width=float(max(x2 - x1, 1e-6)),
                            height=float(max(y2 - y1, 1e-6)),
                        ),
                    )
                )
            except Exception as exc:
                logger.warning(
                    "structural_agent: failed to parse a YOLO detection box for %s: %s",
                    image_path,
                    exc,
                )
                continue

        return detections

    # ----------------------------------------------------------------
    # Comparison / fusion helpers
    # ----------------------------------------------------------------

    def compare_component_counts(
        self,
        golden_detections: Sequence[StructuralComponentDetection],
        inspection_detections: Sequence[StructuralComponentDetection],
        enabled_classes: Sequence[StructuralComponentClass],
    ) -> list[ComponentCount]:
        golden_counts: dict[StructuralComponentClass, int] = {
            cls: 0 for cls in enabled_classes
        }
        inspection_counts: dict[StructuralComponentClass, int] = {
            cls: 0 for cls in enabled_classes
        }

        for det in golden_detections:
            if det.class_name in golden_counts:
                golden_counts[det.class_name] += 1

        for det in inspection_detections:
            if det.class_name in inspection_counts:
                inspection_counts[det.class_name] += 1

        results: list[ComponentCount] = []
        for cls in enabled_classes:
            expected = golden_counts[cls]
            detected = inspection_counts[cls]
            difference = detected - expected
            results.append(
                ComponentCount(
                    className=cls,
                    expectedCount=expected,
                    detectedCount=detected,
                    difference=difference,
                    missing=difference < 0,
                    extra=difference > 0,
                )
            )
        return results

    def build_comparison(
        self,
        ssim_result: SSIMResult,
        yolo_result: YOLOResult,
    ) -> StructuralComparison:
        missing_components = tuple(
            count.class_name for count in yolo_result.component_counts if count.missing
        )
        extra_components = tuple(
            count.class_name for count in yolo_result.component_counts if count.extra
        )

        structural_anomaly = (
            not ssim_result.passed
            or len(missing_components) > 0
            or len(extra_components) > 0
        )

        return StructuralComparison(
            ssim=ssim_result,
            yolo=yolo_result,
            structuralAnomaly=structural_anomaly,
            missingComponents=missing_components,
            extraComponents=extra_components,
        )

    def calculate_confidence(
        self,
        ssim_result: SSIMResult,
        yolo_result: YOLOResult,
    ) -> float:
        """
        Weighted fusion of SSIM (holistic) and YOLO (discrete) signals.
        YOLO is weighted higher since component-level presence/count is a
        stronger fraud signal than pixel similarity alone, per the MVP
        architecture's Stage 5c rationale.
        """
        ssim_weight = 0.4
        yolo_weight = 0.6

        has_count_mismatch = any(
            count.missing or count.extra for count in yolo_result.component_counts
        )
        yolo_signal = yolo_result.confidence if not has_count_mismatch else (
            1.0 - yolo_result.confidence
        ) if yolo_result.confidence < 0.5 else yolo_result.confidence

        # When there IS a mismatch, high per-detection confidence in the
        # anomalous detections should translate to high confidence in the
        # anomaly finding itself, not the reverse.
        if has_count_mismatch:
            yolo_signal = yolo_result.confidence

        combined = (ssim_weight * ssim_result.score) + (yolo_weight * yolo_signal)
        return float(np.clip(combined, 0.0, 1.0))

    def build_explanation(self, comparison: StructuralComparison) -> str:
        parts: list[str] = []

        parts.append(
            f"SSIM structural similarity: {comparison.ssim.score:.2f} "
            f"(threshold {comparison.ssim.threshold:.2f}, "
            f"{'passed' if comparison.ssim.passed else 'failed'})."
        )

        if comparison.missing_components:
            missing_names = ", ".join(c.value for c in comparison.missing_components)
            parts.append(f"Missing components detected by YOLO: {missing_names}.")

        if comparison.extra_components:
            extra_names = ", ".join(c.value for c in comparison.extra_components)
            parts.append(f"Unexpected extra components detected by YOLO: {extra_names}.")

        if not comparison.missing_components and not comparison.extra_components:
            parts.append("YOLO component counts match the golden reference.")

        for count in comparison.yolo.component_counts:
            if count.missing or count.extra:
                parts.append(
                    f"{count.class_name.value}: expected {count.expected_count}, "
                    f"detected {count.detected_count} "
                    f"({'missing' if count.missing else 'extra'} "
                    f"{abs(count.difference)})."
                )

        return " ".join(parts)

    def _determine_status(self, comparison: StructuralComparison) -> EvidenceStatus:
        if comparison.structural_anomaly:
            if not comparison.ssim.passed and (
                comparison.missing_components or comparison.extra_components
            ):
                return EvidenceStatus.FAIL
            return EvidenceStatus.UNCERTAIN
        return EvidenceStatus.PASS

    def _aggregate_yolo_confidence(
        self, detections: Sequence[StructuralComponentDetection]
    ) -> float:
        if not detections:
            return 0.0
        confidences = [d.confidence for d in detections]
        return float(np.clip(sum(confidences) / len(confidences), 0.0, 1.0))

    def _resolve_enabled_classes(
        self, product_type: ProductType
    ) -> tuple[StructuralComponentClass, ...]:
        product_classes = PRODUCT_CLASS_MAP.get(product_type)
        if not product_classes:
            raise StructuralAgentError(
                f"No YOLO class mapping defined for product type: {product_type}"
            )
        enabled = tuple(
            cls for cls in product_classes if cls in self._config.enabled_classes
        )
        if not enabled:
            raise StructuralAgentError(
                f"Product type {product_type.value} has no classes enabled in agent config"
            )
        return enabled

    # ----------------------------------------------------------------
    # ROI cropping
    # ----------------------------------------------------------------

    def _crop_roi_pair(
        self, image_pair: ImagePair, roi: ROIMetadata
    ) -> tuple[str, str]:
        """
        Crops the golden and inspection images to the ROI bounding box and
        writes them to temp files, returning their paths for downstream
        SSIM/YOLO calls. Raises ImageLoadError on any failure.
        """
        import os
        import tempfile

        golden_crop_path = self._crop_and_save(
            image_pair.golden_image_path, roi.bounding_box, suffix="golden"
        )
        inspection_crop_path = self._crop_and_save(
            image_pair.inspection_image_path, roi.bounding_box, suffix="inspection"
        )
        return golden_crop_path, inspection_crop_path

    def _crop_and_save(
        self, image_path: str, bbox: BoundingBox, suffix: str
    ) -> str:
        import os
        import tempfile

        image = cv2.imread(image_path, cv2.IMREAD_COLOR)
        if image is None:
            raise ImageLoadError(f"Could not read image for ROI crop: {image_path}")

        h, w = image.shape[:2]
        x1 = max(0, int(bbox.x))
        y1 = max(0, int(bbox.y))
        x2 = min(w, int(bbox.x + bbox.width))
        y2 = min(h, int(bbox.y + bbox.height))

        if x2 <= x1 or y2 <= y1:
            raise ImageLoadError(
                f"Invalid ROI bounding box for image {image_path}: "
                f"({x1},{y1})-({x2},{y2}) against image size {w}x{h}"
            )

        cropped = image[y1:y2, x1:x2]

        fd, temp_path = tempfile.mkstemp(suffix=f"_{suffix}_roi.png")
        os.close(fd)

        success = cv2.imwrite(temp_path, cropped)
        if not success:
            raise ImageLoadError(f"Failed to write cropped ROI image to {temp_path}")

        return temp_path

    # ----------------------------------------------------------------
    # Error evidence builder
    # ----------------------------------------------------------------

    def _build_error_evidence(
        self,
        evidence_id: str,
        input_data: StructuralAgentInput,
        processing_time_ms: float,
        error_message: str,
    ) -> Evidence:
        empty_ssim = SSIMResult(score=0.0, threshold=self._config.ssim_threshold, passed=False)
        empty_yolo = YOLOResult(
            modelPath=self._config.yolo_weights_path,
            detections=tuple(),
            componentCounts=tuple(),
            confidence=0.0,
        )
        empty_comparison = StructuralComparison(
            ssim=empty_ssim,
            yolo=empty_yolo,
            structuralAnomaly=False,
            missingComponents=tuple(),
            extraComponents=tuple(),
        )

        return Evidence(
            evidenceId=evidence_id,
            inspectionId=input_data.inspection_id,
            agent=AgentName.STRUCTURAL,
            roi=input_data.roi,
            status=EvidenceStatus.ERROR,
            confidence=0.0,
            explanation=f"Structural agent failed to produce evidence: {error_message}",
            processingTimeMs=processing_time_ms,
            comparison=empty_comparison,
            createdAt=datetime.now(timezone.utc).isoformat(),
        )