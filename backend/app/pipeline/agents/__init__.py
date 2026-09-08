# backend/app/pipeline/agents/__init__.py
"""Specialized evidence agents package for VisionForge AI pipeline."""

from app.pipeline.agents.base_agent import AgentResult, BaseAgent
from app.pipeline.agents.label_agent import LabelAgent
from app.pipeline.agents.ocr_agent import OCRAgent
from app.pipeline.agents.structural_agent import StructuralAgent

__all__ = [
    "BaseAgent",
    "AgentResult",
    "LabelAgent",
    "OCRAgent",
    "StructuralAgent",
]

