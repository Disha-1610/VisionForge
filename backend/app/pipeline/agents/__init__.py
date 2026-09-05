# backend/app/pipeline/agents/__init__.py
"""Specialized evidence agents package for VisionForge AI pipeline."""

from app.pipeline.agents.base_agent import AgentResult, BaseAgent
from app.pipeline.agents.label_agent import LabelAgent

__all__ = [
    "BaseAgent",
    "AgentResult",
    "LabelAgent",
]
