# backend/app/pipeline/stages/authenticity.py
"""
Stage 2: Image Authenticity Verification — architectural contract.
CV logic NOT implemented here (next pass). Signatures + models only.
"""
from __future__ import annotations

import time
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from app.pipeline.state import InspectionState
from app.shared.memory import PipelineStageName, StageResult, WorkingMemory


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


async def run_authenticity_stage(
    state: InspectionState,
    memory: WorkingMemory,
) -> StageResult:
    """
    Entry point called by pipeline/workflow.py.
    Reads image paths from state, writes AuthenticityStageOutput to memory,
    returns StageResult for SSE progress + Judge consumption.
    Raises NotImplementedError — CV logic pending.
    """
    start = time.perf_counter()
    raise NotImplementedError("authenticity CV logic pending — contract only")


async def _compute_ela(image_path: str) -> ELAResult:
    raise NotImplementedError


async def _validate_exif(image_path: str) -> ExifResult:
    raise NotImplementedError


async def _detect_screenshot(image_path: str) -> ScreenshotResult:
    raise NotImplementedError


async def _check_noise_consistency(image_path: str) -> NoiseConsistencyResult:
    raise NotImplementedError


async def _detect_copy_move(image_path: str) -> CopyMoveResult:
    raise NotImplementedError


def _calculate_authenticity_score(
    ela: ELAResult,
    exif: ExifResult,
    screenshot: ScreenshotResult,
    noise: NoiseConsistencyResult,
    copy_move: CopyMoveResult,
) -> tuple[float, list[AuthenticityFlag]]:
    raise NotImplementedError