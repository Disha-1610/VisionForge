# backend/app/pipeline/agents/base_agent.py
"""
Base Evidence Agent contract and abstract class (Anil, W3 D2).

Per VisionForge.md Section 4 & 5:
  - Standardized AgentResult Pydantic contract.
  - Standardized execution interface with execution timing and error isolation.
  - Standardized confidence normalization (clamped 0.0 to 1.0).
  - Robust failure reporting: agents report failures rather than fabricating results
    or raising uncaught exceptions that crash the pipeline.
"""
from __future__ import annotations

import abc
import logging
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.evidence_store import AgentType
from app.utils.image_utils import (
    ImageSource,
    load_cv_image,
    load_pil_image,
)

logger = logging.getLogger("app.pipeline.agents.base")


class AgentResult(BaseModel):
    """
    Standardized result contract returned by every evidence agent.
    Conforms to VisionForge.md Stage 5 specification and EvidenceStore record layout.
    """
    model_config = ConfigDict(frozen=True, extra="ignore")

    agent_type: AgentType
    detector_name: str
    roi_id: str
    roi_type: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    has_defect: bool = False
    evidence: dict[str, Any] = Field(default_factory=dict)
    explanation: str = ""
    bounding_box: list[float] | dict[str, Any] | None = None
    processing_time_ms: float = 0.0
    failed: bool = False
    failure_reason: str | None = None
    raw_output: dict[str, Any] | None = None

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v: Any) -> float:
        try:
            val = float(v)
            return max(0.0, min(1.0, val))
        except (TypeError, ValueError):
            return 0.0

    def to_evidence_dict(self) -> dict[str, Any]:
        """Convert result to dictionary suitable for state.append_evidence()."""
        return {
            "agent_type": self.agent_type,
            "roi_id": self.roi_id,
            "confidence": self.confidence,
            "evidence": {
                **self.evidence,
                "detector_name": self.detector_name,
                "has_defect": self.has_defect,
                "roi_type": self.roi_type,
            },
            "explanation": self.explanation,
            "processing_time_ms": self.processing_time_ms,
            "bounding_box": (
                self.bounding_box
                if isinstance(self.bounding_box, list)
                else None
            ),
            "failed": self.failed,
            "failure_reason": self.failure_reason,
        }


class BaseAgent(abc.ABC):
    """
    Abstract base class for all specialized evidence agents.
    Subclasses implement `_analyze`.
    """

    agent_type: AgentType
    detector_name: str

    def __init__(self, detector_name: str | None = None) -> None:
        if detector_name:
            self.detector_name = detector_name

    @abc.abstractmethod
    async def _analyze(
        self,
        golden_roi: Any,
        inspection_roi: Any,
        roi_data: dict[str, Any],
    ) -> AgentResult:
        """
        Agent-specific analysis logic.
        Must be implemented by subclasses.
        """
        raise NotImplementedError

    async def run(
        self,
        golden_roi: ImageSource,
        inspection_roi: ImageSource,
        roi_data: dict[str, Any] | None = None,
    ) -> AgentResult:
        """
        Public entrypoint for running an agent on a paired ROI crop.
        Handles execution timing, input preparation, error isolation, and validation.
        """
        roi_info = roi_data or {}
        roi_id = str(roi_info.get("roi_id") or roi_info.get("id") or "unknown_roi")
        roi_type = roi_info.get("type") or roi_info.get("roi_type")
        if roi_type is not None:
            roi_type = str(roi_type)

        start_time = time.perf_counter()
        try:
            # Pre-validate / verify images can be loaded
            if golden_roi is None or inspection_roi is None:
                raise ValueError("Both golden_roi and inspection_roi must be provided")

            result = await self._analyze(golden_roi, inspection_roi, roi_info)
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Ensure processing time, roi_id, agent_type, detector_name are set
            return AgentResult(
                agent_type=self.agent_type,
                detector_name=self.detector_name,
                roi_id=roi_id,
                roi_type=roi_type or result.roi_type,
                confidence=result.confidence,
                has_defect=result.has_defect,
                evidence=result.evidence,
                explanation=result.explanation,
                bounding_box=result.bounding_box or roi_info.get("bbox") or roi_info.get("bounding_box"),
                processing_time_ms=round(elapsed_ms, 2),
                failed=result.failed,
                failure_reason=result.failure_reason,
                raw_output=result.raw_output,
            )

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "Agent %s failed on roi_id=%s: %s",
                self.detector_name,
                roi_id,
                exc,
                exc_info=True,
            )
            return AgentResult(
                agent_type=self.agent_type,
                detector_name=self.detector_name,
                roi_id=roi_id,
                roi_type=roi_type,
                confidence=0.0,
                has_defect=False,
                evidence={"error": str(exc)},
                explanation=f"Agent analysis failed: {exc}",
                bounding_box=roi_info.get("bbox") or roi_info.get("bounding_box"),
                processing_time_ms=round(elapsed_ms, 2),
                failed=True,
                failure_reason=str(exc),
            )
