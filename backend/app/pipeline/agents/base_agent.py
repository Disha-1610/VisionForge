# backend/app/pipeline/agents/base_agent.py
"""Abstract base agent and evidence agent contracts for VisionForge pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional
from pydantic import BaseModel, Field


class BaseAgent(ABC):
    """Abstract base class for all domain evidence agents (OCR, Structural, VLM, etc.)."""

    def __init__(self, name: str = "BaseAgent", **kwargs: Any) -> None:
        self.name = name

    @abstractmethod
    async def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute agent inspection pass over image ROI pairs."""
        raise NotImplementedError

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Alias for run method to support evidence orchestrator contract."""
        return await self.run(*args, **kwargs)


class EvidenceAgent(BaseAgent):
    """Specialized base class for stage 5 evidence execution agents."""

    async def run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

