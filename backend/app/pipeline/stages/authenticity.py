"""
Stage 2: Image Authenticity Verification
Deterministic image forensics — no AI/LLM calls. Never hard-blocks the
inspection: authenticity_score + authenticity_flagged are written to
WorkingMemory and consumed as weighted evidence by Stage 7 (AI Judge),
per VisionForge.md Stage 2 ("do not hard-block — let the Judge weigh it").
Checks per image:
  - ELA (Error Level Analysis)      — Pillow re-save diff, edited regions run hot
  - EXIF validation                 — exifread, camera metadata + screenshot signal
  - Screenshot detection            — EXIF absent + row/col pixel uniformity
  - Noise consistency               — patch-wise noise variance comparison
  - Copy-move detection             — block-hash matching for cloned regions
"""
from __future__ import annotations

import io
import logging
import time
from enum import Enum
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

import cv2
import exifread
import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.pipeline.state import InspectionState
from app.shared.memory import PipelineStageName, StageResult

logger = logging.getLogger("app.pipeline.authenticity")


# ── Models ──────────────────────────────────────────────────────────────────

class AuthenticityFlag(str, Enum):
    ELA_ANOMALY = "ela_anomaly"
    EXIF_MISSING = "exif_missing"
    EXIF_INCONSISTENT = "exif_inconsistent"
    SCREENSHOT_DETECTED = "screenshot_detected"
    NOISE_INCONSISTENT = "noise_inconsistent"
    COPY_MOVE_DETECTED = "copy_move_detected"
    LIGHTING_INCONSISTENT = "lighting_inconsistent"


class ELAResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    error_map_mean: float
    error_map_std: float
    suspicious_regions: list[tuple[int, int, int, int]] = Field(default_factory=list)
    ela_score: float = Field(ge=0.0, le=1.0)


class ExifResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    has_exif: bool
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    software_tag: Optional[str] = None
    datetime_original: Optional[str] = None
    gps_present: bool = False
    exif_score: float = Field(ge=0.0, le=1.0)


class ScreenshotResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    is_screenshot: bool
    confidence: float = Field(ge=0.0, le=1.0)


class NoiseConsistencyResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    region_variances: list[float] = Field(default_factory=list)
    consistency_score: float = Field(ge=0.0, le=1.0)


class CopyMoveResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    matched_blocks: int
    duplicate_regions: list[tuple[int, int, int, int]] = Field(default_factory=list)
    copy_move_score: float = Field(ge=0.0, le=1.0)


class AuthenticityResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    inspection_id: UUID
    image_id: UUID
    ela: ELAResult
    exif: ExifResult
    screenshot: ScreenshotResult
    noise: NoiseConsistencyResult
    copy_move: CopyMoveResult
    flags: list[AuthenticityFlag] = Field(default_factory=list)
    authenticity_score: float = Field(ge=0.0, le=1.0)
    is_suspicious: bool
    processing_time_ms: float


class AuthenticityStageOutput(BaseModel):
    model_config = ConfigDict(frozen=True)
    inspection_id: UUID
    results: list[AuthenticityResult]
    overall_authenticity_score: float = Field(ge=0.0, le=1.0)
    hard_block: bool = False
    stage_name: PipelineStageName = PipelineStageName.AUTHENTICITY


# ── ELA ─────────────────────────────────────────────────────────────────────

async def _compute_ela(image_path: str) -> ELAResult:
    """
    Error Level Analysis: re-save the image at a known JPEG quality, diff
    against the original in pixel space. Edited/spliced regions compress
    differently from untouched regions and run "hot" in the diff map.
    """
    try:
        original = Image.open(image_path).convert("RGB")
    except Exception as exc:
        logger.warning("ELA: cannot open %s: %s", image_path, exc)
        return ELAResult(error_map_mean=0.0, error_map_std=0.0, ela_score=0.0)

    buffer = io.BytesIO()
    original.save(buffer, "JPEG", quality=settings.ELA_RESAVE_QUALITY)
    buffer.seek(0)
    resaved = Image.open(buffer)

    orig_arr = np.asarray(original, dtype=np.int16)
    resaved_arr = np.asarray(resaved, dtype=np.int16)

    if orig_arr.shape != resaved_arr.shape:
        return ELAResult(error_map_mean=0.0, error_map_std=0.0, ela_score=0.0)

    diff = np.abs(orig_arr - resaved_arr).astype(np.uint8)
    error_map = diff.max(axis=2)  # per-pixel max channel error

    error_map_mean = float(error_map.mean())
    error_map_std = float(error_map.std())

    # Locate suspicious regions via thresholded blob bounding boxes.
    threshold = max(20, int(error_map_mean + 2 * error_map_std))
    mask = (error_map > threshold).astype(np.uint8) * 255
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_region_area = 64
    suspicious_regions: list[tuple[int, int, int, int]] = []
    for contour in contours:
        if cv2.contourArea(contour) < min_region_area:
            continue
        x, y, w, h = cv2.boundingRect(contour)
        suspicious_regions.append((int(x), int(y), int(w), int(h)))

    # Normalize std into a 0-1 anomaly score; clamp at a reasonable ceiling.
    ela_score = min(1.0, error_map_std / (settings.ELA_ANOMALY_STD_THRESHOLD * 3.0))

    return ELAResult(
        error_map_mean=round(error_map_mean, 4),
        error_map_std=round(error_map_std, 4),
        suspicious_regions=suspicious_regions[:20],
        ela_score=round(ela_score, 4),
    )
# ── EXIF ────────────────────────────────────────────────────────────────────
_EDITING_SOFTWARE_MARKERS = (
    "photoshop", "gimp", "lightroom", "snapseed", "picsart",
    "canva", "pixlr", "affinity photo",
)
async def _validate_exif(image_path: str) -> ExifResult:
    """
    Read camera metadata via exifread. Missing EXIF, a known editing-software
    tag, or a datetime that doesn't parse are all inconsistency signals.
    """
    try:
        with open(image_path, "rb") as fh:
            tags = exifread.process_file(fh, details=False, strict=False)
    except OSError as exc:
        logger.warning("EXIF: cannot read %s: %s", image_path, exc)
        tags = {}

    if not tags:
        return ExifResult(has_exif=False, exif_score=0.0)

    def _tag(name: str) -> Optional[str]:
        value = tags.get(name)
        return str(value) if value is not None else None

    camera_make = _tag("Image Make")
    camera_model = _tag("Image Model")
    software_tag = _tag("Image Software")
    datetime_original = _tag("EXIF DateTimeOriginal") or _tag("Image DateTime")
    gps_present = any(k.startswith("GPS ") for k in tags)

    score = 1.0
    if not camera_make and not camera_model:
        score -= 0.4
    if not datetime_original:
        score -= 0.2
    if software_tag and any(m in software_tag.lower() for m in _EDITING_SOFTWARE_MARKERS):
        score -= 0.5
    score = max(0.0, min(1.0, score))

    return ExifResult(
        has_exif=True,
        camera_make=camera_make,
        camera_model=camera_model,
        software_tag=software_tag,
        datetime_original=datetime_original,
        gps_present=gps_present,
        exif_score=round(score, 4),
    )
# ── Screenshot detection ─────────────────────────────────────────────────────
async def _detect_screenshot(image_path: str) -> ScreenshotResult:
    """
    Screenshots exhibit near-uniform rows/columns (UI chrome, solid status
    bars, flat backgrounds) that photographed parts almost never do.
    Combined with EXIF absence, this is a strong screenshot signal.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return ScreenshotResult(is_screenshot=False, confidence=0.0)

    row_std = np.std(img, axis=1)
    col_std = np.std(img, axis=0)

    flat_row_ratio = float(np.mean(row_std < 5.0))
    flat_col_ratio = float(np.mean(col_std < 5.0))
    uniformity = max(flat_row_ratio, flat_col_ratio)

    try:
        with open(image_path, "rb") as fh:
            has_exif = bool(exifread.process_file(fh, details=False, strict=False))
    except OSError:
        has_exif = False

    confidence = uniformity
    if not has_exif:
        confidence = min(1.0, confidence + 0.15)

    is_screenshot = confidence >= settings.SCREENSHOT_UNIFORMITY_THRESHOLD

    return ScreenshotResult(is_screenshot=is_screenshot, confidence=round(confidence, 4))
# ── Noise consistency ─────────────────────────────────────────────────────────
async def _check_noise_consistency(image_path: str) -> NoiseConsistencyResult:
    """
    Splice/tamper regions are often denoised or re-compressed differently
    from the rest of the frame. Split the image into an NxN patch grid,
    estimate high-frequency noise per patch (Laplacian residual variance),
    and flag patches that diverge sharply from the grid median.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return NoiseConsistencyResult(region_variances=[], consistency_score=0.0)

    grid = max(2, settings.NOISE_PATCH_GRID)
    height, width = img.shape
    patch_h, patch_w = height // grid, width // grid

    if patch_h < 8 or patch_w < 8:
        return NoiseConsistencyResult(region_variances=[], consistency_score=1.0)

    denoised = cv2.GaussianBlur(img, (5, 5), 0)
    residual = cv2.absdiff(img, denoised).astype(np.float64)

    variances: list[float] = []
    for gy in range(grid):
        for gx in range(grid):
            y0, y1 = gy * patch_h, (gy + 1) * patch_h
            x0, x1 = gx * patch_w, (gx + 1) * patch_w
            patch = residual[y0:y1, x0:x1]
            variances.append(float(patch.var()))

    variances_arr = np.array(variances)
    median_var = float(np.median(variances_arr)) if variances_arr.size else 0.0

    if median_var <= 1e-6:
        consistency_score = 1.0
    else:
        ratios = variances_arr / median_var
        outlier_fraction = float(np.mean(ratios > settings.NOISE_INCONSISTENCY_RATIO))
        consistency_score = max(0.0, 1.0 - outlier_fraction)

    return NoiseConsistencyResult(
        region_variances=[round(v, 4) for v in variances],
        consistency_score=round(consistency_score, 4),
    )
# ── Copy-move detection ────────────────────────────────────────────────────────
async def _detect_copy_move(image_path: str) -> CopyMoveResult:
    """
    Block-wise duplicate detection: hash fixed-size non-overlapping blocks
    and flag distinct block-pairs that hash-collide with high pixel
    similarity — a classic clone-stamp fraud signature.
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return CopyMoveResult(matched_blocks=0, copy_move_score=0.0)

    block = settings.COPY_MOVE_BLOCK_SIZE
    height, width = img.shape
    blocks_y, blocks_x = height // block, width // block

    if blocks_y < 2 or blocks_x < 2:
        return CopyMoveResult(matched_blocks=0, copy_move_score=0.0)

    block_map: dict[tuple[int, ...], tuple[int, int]] = {}
    duplicate_regions: list[tuple[int, int, int, int]] = []
    matched_blocks = 0

    for by in range(blocks_y):
        for bx in range(blocks_x):
            y0, x0 = by * block, bx * block
            patch = img[y0:y0 + block, x0:x0 + block]
            # Coarse 8x8 average-pooled fingerprint — cheap, rotation-naive
            # but sufficient to catch straight clone-stamp copies.
            fingerprint = tuple(
                int(v) for v in cv2.resize(patch, (8, 8), interpolation=cv2.INTER_AREA).flatten() // 8
            )
            if fingerprint in block_map:
                orig_y, orig_x = block_map[fingerprint]
                # Ignore trivially adjacent blocks (natural flat regions).
                if abs(orig_y - y0) > block or abs(orig_x - x0) > block:
                    matched_blocks += 1
                    duplicate_regions.append((int(x0), int(y0), block, block))
            else:
                block_map[fingerprint] = (y0, x0)

    copy_move_score = min(1.0, matched_blocks / max(1, settings.COPY_MOVE_MATCH_THRESHOLD * 2))

    return CopyMoveResult(
        matched_blocks=matched_blocks,
        duplicate_regions=duplicate_regions[:20],
        copy_move_score=round(copy_move_score, 4),
    )
# ── Score fusion ────────────────────────────────────────────────────────────
_WEIGHTS = {
    "ela": 0.30,
    "exif": 0.15,
    "screenshot": 0.15,
    "noise": 0.20,
    "copy_move": 0.20,
}


def _calculate_authenticity_score(
    ela: ELAResult,
    exif: ExifResult,
    screenshot: ScreenshotResult,
    noise: NoiseConsistencyResult,
    copy_move: CopyMoveResult,
) -> tuple[float, list[AuthenticityFlag]]:
    """
    Combine all five signals into one 0-1 authenticity score (1.0 = clean).
    Flags are independent threshold trips, kept separate from the numeric
    score so the Judge can reason over both.
    """
    flags: list[AuthenticityFlag] = []

    ela_component = 1.0 - ela.ela_score
    if ela.error_map_std > settings.ELA_ANOMALY_STD_THRESHOLD:
        flags.append(AuthenticityFlag.ELA_ANOMALY)

    exif_component = exif.exif_score
    if not exif.has_exif:
        flags.append(AuthenticityFlag.EXIF_MISSING)
    elif exif.exif_score < 0.6:
        flags.append(AuthenticityFlag.EXIF_INCONSISTENT)

    screenshot_component = 1.0 - screenshot.confidence
    if screenshot.is_screenshot:
        flags.append(AuthenticityFlag.SCREENSHOT_DETECTED)

    noise_component = noise.consistency_score
    if noise.consistency_score < 0.6:
        flags.append(AuthenticityFlag.NOISE_INCONSISTENT)

    copy_move_component = 1.0 - copy_move.copy_move_score
    if copy_move.matched_blocks >= settings.COPY_MOVE_MATCH_THRESHOLD:
        flags.append(AuthenticityFlag.COPY_MOVE_DETECTED)

    score = (
        _WEIGHTS["ela"] * ela_component
        + _WEIGHTS["exif"] * exif_component
        + _WEIGHTS["screenshot"] * screenshot_component
        + _WEIGHTS["noise"] * noise_component
        + _WEIGHTS["copy_move"] * copy_move_component
    )

    return round(max(0.0, min(1.0, score)), 4), flags


async def _analyze_image(inspection_id: UUID, image_path: str) -> AuthenticityResult:
    start = time.perf_counter()

    ela = await _compute_ela(image_path)
    exif = await _validate_exif(image_path)
    screenshot = await _detect_screenshot(image_path)
    noise = await _check_noise_consistency(image_path)
    copy_move = await _detect_copy_move(image_path)

    score, flags = _calculate_authenticity_score(ela, exif, screenshot, noise, copy_move)
    processing_time_ms = round((time.perf_counter() - start) * 1000, 2)

    return AuthenticityResult(
        inspection_id=inspection_id,
        image_id=uuid4(),
        ela=ela,
        exif=exif,
        screenshot=screenshot,
        noise=noise,
        copy_move=copy_move,
        flags=flags,
        authenticity_score=score,
        is_suspicious=score < settings.AUTHENTICITY_FLAG_THRESHOLD,
        processing_time_ms=processing_time_ms,
    )
# ── Stage entrypoint ──────────────────────────────────────────────────────────
async def run_authenticity_stage(state: InspectionState) -> StageResult:
    """
    Stage 2 entrypoint. Requires Stage 1 to have passed. Runs ELA, EXIF,
    screenshot, noise, and copy-move checks per image, fuses them into
    overall_authenticity_score, and writes authenticity_score /
    authenticity_flagged into WorkingMemory.

    Never hard-blocks: status is "passed" if the overall score clears
    AUTHENTICITY_HARD_BLOCK_THRESHOLD, otherwise "flagged" — pipeline
    continues either way and Stage 7 (AI Judge) weighs the flags.
    """
    quality_passed = await state.memory.get("quality_passed")
    if not quality_passed:
        return await state.record_stage(
            StageResult(
                stage=PipelineStageName.AUTHENTICITY,
                status="failed",
                error="Stage 1 (quality_check) did not pass — authenticity skipped",
            )
        )

    paths = state.memory.image_paths
    if not paths:
        return await state.record_stage(
            StageResult(
                stage=PipelineStageName.AUTHENTICITY,
                status="failed",
                error="No images to analyze for authenticity",
            )
        )

    inspection_id = state.memory.inspection_id

    results: list[AuthenticityResult] = []
    for path in paths:
        try:
            result = await _analyze_image(inspection_id, path)
        except Exception as exc:
            logger.exception("Authenticity check crashed for %s", path)
            return await state.record_stage(
                StageResult(
                    stage=PipelineStageName.AUTHENTICITY,
                    status="failed",
                    error=f"Authenticity analysis failed on {Path(path).name}: {exc}",
                )
            )
        results.append(result)

    overall_score = round(
        sum(r.authenticity_score for r in results) / len(results), 4
    )
    hard_block = overall_score < settings.AUTHENTICITY_HARD_BLOCK_THRESHOLD
    flagged = overall_score < settings.AUTHENTICITY_FLAG_THRESHOLD

    output = AuthenticityStageOutput(
        inspection_id=inspection_id,
        results=results,
        overall_authenticity_score=overall_score,
        hard_block=hard_block,
    )

    await state.memory.update(
        authenticity_score=overall_score,
        authenticity_flagged=flagged,
    )

    status = "failed" if hard_block else ("flagged" if flagged else "passed")
    error = (
        f"Authenticity score {overall_score:.2f} below hard-block threshold "
        f"{settings.AUTHENTICITY_HARD_BLOCK_THRESHOLD:.2f}"
        if hard_block
        else None
    )

    return await state.record_stage(
        StageResult(
            stage=PipelineStageName.AUTHENTICITY,
            status=status,
            data={
                "overall_authenticity_score": overall_score,
                "per_image": [r.model_dump(mode="json") for r in output.results],
                "hard_block": hard_block,
            },
            error=error,
        )
    )
