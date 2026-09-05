# backend/app/pipeline/stages/__init__.py
"""Pipeline stages package for VisionForge AI inspection pipeline."""

from app.pipeline.stages.authenticity import run_authenticity_stage
from app.pipeline.stages.quality_check import run_quality_check
from app.pipeline.stages.reference_match import run_reference_match
from app.pipeline.stages.roi_scheduler import infer_product_type, resolve_roi_template, run_roi_scheduler

__all__ = [
    "run_quality_check",
    "run_authenticity_stage",
    "run_reference_match",
    "run_roi_scheduler",
    "resolve_roi_template",
    "infer_product_type",
]
