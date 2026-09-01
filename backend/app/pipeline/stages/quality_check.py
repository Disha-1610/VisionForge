# backend/app/pipeline/stages/quality_check.py
"""
Stage 1 — Image Intake & Quality Validation (Anil, W2 D1).

Deterministic OpenCV checks, no AI. Fails fast: if any required check fails,
the inspection stops here with a retake suggestion (per VisionForge.md Stage 1).

Checks per image:
  - Loadability / format validation (corrupt files rejected)
  - Blur detection (Laplacian variance)
  - Lighting (mean brightness)
  - Resolution (minimum usable dimensions)
Duplicate detection across the uploaded set (perceptual average hash).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.core.config import settings
from app.pipeline.state import InspectionState
from app.shared.memory import PipelineStageName, StageResult

logger = logging.getLogger("app.pipeline.quality_check")

SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png"}


# ── Image loading ─────────────────────────────────────────────────────────────

def load_image(path: str) -> np.ndarray | None:
    """Load an image as BGR ndarray via imdecode (unicode-safe on Windows)."""
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        logger.warning("Cannot read image %s: %s", path, exc)
        return None
    arr = np.frombuffer(data, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


# ── Individual checks ─────────────────────────────────────────────────────────

def laplacian_variance(img: np.ndarray) -> float:
    """Blur metric: variance of the Laplacian. Low variance => blurry."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def mean_brightness(img: np.ndarray) -> float:
    """Mean pixel brightness (0-255)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray))


def average_hash(img: np.ndarray, size: int = 16) -> str:
    """Perceptual average hash for duplicate detection (hamming-comparable)."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)
    avg = resized.mean()
    bits = (resized > avg).flatten()
    return "".join("1" if b else "0" for b in bits)


def hamming_distance(h1: str, h2: str) -> int:
    return sum(c1 != c2 for c1, c2 in zip(h1, h2))


def validate_image(path: str) -> dict[str, Any]:
    """Run all quality checks on one image. Returns per-check results + reasons."""
    reasons: list[str] = []

    ext = Path(path).suffix.lower()
    if ext not in SUPPORTED_FORMATS:
        reasons.append(f"Unsupported format '{ext}'")

    img = load_image(path)
    if img is None:
        return {
            "path": path,
            "passed": False,
            "reasons": reasons + ["Corrupted or unreadable image file"],
            "metrics": {},
        }

    blur_var = laplacian_variance(img)
    brightness = mean_brightness(img)
    height, width = img.shape[:2]

    if blur_var < settings.MIN_BLUR_VARIANCE:
        reasons.append(f"Image too blurry (variance {blur_var:.1f})")
    if brightness < settings.MIN_BRIGHTNESS:
        reasons.append(f"Image too dark (brightness {brightness:.1f})")
    if brightness > settings.MAX_BRIGHTNESS:
        reasons.append(f"Image overexposed (brightness {brightness:.1f})")
    if width < settings.MIN_IMAGE_WIDTH or height < settings.MIN_IMAGE_HEIGHT:
        reasons.append(f"Resolution too low ({width}x{height})")

    return {
        "path": path,
        "passed": not reasons,
        "reasons": reasons,
        "metrics": {
            "blur_variance": round(blur_var, 2),
            "brightness": round(brightness, 2),
            "width": width,
            "height": height,
        },
    }


def detect_duplicates(paths: list[str]) -> list[list[str]]:
    """
    Group duplicate images using perceptual hash hamming distance.
    Returns list of duplicate groups (each with >= 2 paths). First image
    in each group is the keeper; the rest should be ignored.
    """
    hashes: dict[str, str] = {}
    for p in paths:
        img = load_image(p)
        if img is not None:
            hashes[p] = average_hash(img)

    assigned: set[str] = set()
    groups: list[list[str]] = []
    for p, h in hashes.items():
        if p in assigned:
            continue
        group = [p]
        assigned.add(p)
        for other, oh in hashes.items():
            if other in assigned:
                continue
            if hamming_distance(h, oh) <= settings.DUPLICATE_HASH_MAX_DISTANCE:
                group.append(other)
                assigned.add(other)
        if len(group) >= 2:
            groups.append(group)
    return groups


# ── Stage entrypoint ──────────────────────────────────────────────────────────

async def run_quality_check(state: InspectionState) -> StageResult:
    """
    Stage 1 entrypoint. Reads image paths from WorkingMemory, runs all checks,
    records the StageResult, and updates memory.quality_passed.

    Status "failed" => Stage 2+ must not run; operator gets a retake suggestion.
    Duplicate images don't fail the stage if a clean copy of the same image exists
    (the first image of each duplicate group is kept, rest ignored).
    """
    await state.memory.update(quality_passed=False)

    paths = state.memory.image_paths
    if not paths:
        return await state.record_stage(
            StageResult(
                stage=PipelineStageName.QUALITY_CHECK,
                status="failed",
                error="No images to inspect",
            )
        )

    per_image = [validate_image(p) for p in paths]
    dup_groups = detect_duplicates(paths)

    duplicates = {p for group in dup_groups for p in group[1:]}

    effective_failures = [
        r for r in per_image if not r["passed"] and r["path"] not in duplicates
    ]

    passed = not effective_failures
    detail = {
        "per_image": per_image,
        "duplicate_groups": dup_groups,
        "ignored_duplicates": sorted(duplicates),
        "effective_failures": [r["path"] for r in effective_failures],
    }

    await state.memory.update(quality_passed=passed)

    error = None
    if not passed:
        error = " | ".join(
            f"{Path(r['path']).name}: {'; '.join(r['reasons'])}"
            for r in effective_failures
        )

    return await state.record_stage(
        StageResult(
            stage=PipelineStageName.QUALITY_CHECK,
            status="passed" if passed else "failed",
            data=detail,
            error=error,
        )
    )
