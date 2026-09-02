"""
app/utils/roi_templates.py

ROI Template data contract + loader/validator/execution-plan utilities.

Consumed by:
    - app/pipeline/stages/roi_scheduler.py (Stage 4)
    - app/pipeline/stages/evidence_execution.py (Stage 5, via ROIExecutionPlan)

Rule enforced: one ROI region maps to exactly one agent. ROIs assigned to the
same agent are grouped into a single execution batch. Critical-priority ROIs
are ordered first within and across batches.
"""

from __future__ import annotations

import json
import logging
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

DEFAULT_ROI_TEMPLATE_DIR = Path("data/roi_templates")

_PRIORITY_ORDER: dict[str, int] = {"critical": 0, "high": 1, "normal": 2}


class ROITemplateError(Exception):
    """Base exception for ROI template loading/validation failures."""


class ROITemplateNotFoundError(ROITemplateError):
    """Raised when no template file matches (product_type, part_code)."""


class ROITemplateValidationError(ROITemplateError):
    """Raised when a template fails structural or semantic validation."""


class ProductType(str, Enum):
    MOTHERBOARD = "motherboard"
    BATTERY = "battery"
    RAM = "ram"


class ROIType(str, Enum):
    TEXT = "text"
    LABEL = "label"
    STRUCTURAL = "structural"
    VISUAL = "visual"


class AgentType(str, Enum):
    OCR = "ocr"
    LABEL = "label"
    STRUCTURAL = "structural"
    VLM = "vlm"


class ROIPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"


class CoordinateSystem(str, Enum):
    PIXEL = "pixel"
    NORMALIZED = "normalized"


# ROIType -> AgentType routing table, per VisionForge.md Stage 4 spec.
ROI_TYPE_TO_AGENT: dict[ROIType, AgentType] = {
    ROIType.TEXT: AgentType.OCR,
    ROIType.LABEL: AgentType.LABEL,
    ROIType.STRUCTURAL: AgentType.STRUCTURAL,
    ROIType.VISUAL: AgentType.VLM,
}


class BoundingBox(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    x: float = Field(..., ge=0)
    y: float = Field(..., ge=0)
    width: float = Field(..., gt=0)
    height: float = Field(..., gt=0)

    def to_pixel(self, image_width: int, image_height: int) -> "BoundingBox":
        """Convert a normalized bbox to pixel coordinates. No-op if already >1 scale."""
        if self.x > 1 or self.y > 1 or self.width > 1 or self.height > 1:
            return self
        return BoundingBox(
            x=round(self.x * image_width, 2),
            y=round(self.y * image_height, 2),
            width=round(self.width * image_width, 2),
            height=round(self.height * image_height, 2),
        )


class ROIExpectedComponent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    class_name: str = Field(..., min_length=1, alias="className")
    expected_count: int = Field(..., ge=0, alias="expectedCount")
    required: bool = True


class ROICheckpoint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    expected_value: Optional[str | float | int] = Field(default=None, alias="expectedValue")
    tolerance: Optional[float] = Field(default=None, ge=0)


class ROITemplateRegion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    type: ROIType
    bbox: BoundingBox
    agent: AgentType
    priority: ROIPriority
    expected_components: list[ROIExpectedComponent] = Field(
        default_factory=list, alias="expectedComponents"
    )
    checkpoints: list[ROICheckpoint] = Field(default_factory=list)

    @model_validator(mode="after")
    def _agent_matches_roi_type(self) -> "ROITemplateRegion":
        expected_agent = ROI_TYPE_TO_AGENT[self.type]
        if self.agent != expected_agent:
            raise ValueError(
                f"ROI '{self.id}': type='{self.type.value}' must route to "
                f"agent='{expected_agent.value}', got agent='{self.agent.value}'"
            )
        return self


class ROITemplate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    id: str = Field(..., min_length=1)
    product_type: ProductType = Field(..., alias="productType")
    part_code: str = Field(..., min_length=1, alias="partCode")
    version: int = Field(..., ge=1)
    coordinate_system: CoordinateSystem = Field(..., alias="coordinateSystem")
    reference_image_width: int = Field(..., gt=0, alias="referenceImageWidth")
    reference_image_height: int = Field(..., gt=0, alias="referenceImageHeight")
    regions: list[ROITemplateRegion] = Field(..., min_length=1)

    @field_validator("part_code")
    @classmethod
    def _normalize_part_code(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def _unique_region_ids(self) -> "ROITemplate":
        seen: set[str] = set()
        for region in self.regions:
            if region.id in seen:
                raise ValueError(f"Duplicate ROI region id '{region.id}' in template '{self.id}'")
            seen.add(region.id)
        return self

    @model_validator(mode="after")
    def _bbox_within_reference_image(self) -> "ROITemplate":
        if self.coordinate_system != CoordinateSystem.PIXEL:
            return self
        for region in self.regions:
            box = region.bbox
            if box.x + box.width > self.reference_image_width or box.y + box.height > self.reference_image_height:
                raise ValueError(
                    f"ROI '{region.id}' bbox exceeds reference image bounds "
                    f"({self.reference_image_width}x{self.reference_image_height})"
                )
        return self

    @model_validator(mode="after")
    def _at_least_one_critical_for_text_or_label(self) -> "ROITemplate":
        critical_types = {ROIType.TEXT, ROIType.LABEL}
        has_critical_signal_region = any(r.type in critical_types for r in self.regions)
        has_critical_priority = any(r.priority == ROIPriority.CRITICAL for r in self.regions)
        if has_critical_signal_region and not has_critical_priority:
            logger.warning(
                "Template '%s' has text/label ROIs but none marked priority='critical'. "
                "Verify this is intentional.",
                self.id,
            )
        return self


class ROIExecutionItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    roi_id: str
    agent: AgentType
    priority: ROIPriority
    bbox: BoundingBox


class ROIExecutionBatch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    agent: AgentType
    roi_ids: list[str]
    priority: ROIPriority


class ROIExecutionPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    template_id: str
    items: list[ROIExecutionItem]
    batches: list[ROIExecutionBatch]


def _template_file_path(product_type: ProductType, part_code: str, base_dir: Path) -> Path:
    raw = part_code.strip()
    underscore_code = raw.replace(" ", "_").replace("-", "_")
    hyphen_code = raw.replace(" ", "_")
    prefix = f"{product_type.value}_"
    stripped_underscore = (
        underscore_code[len(prefix):]
        if underscore_code.lower().startswith(prefix)
        else underscore_code
    )

    candidates = [
        base_dir / f"{product_type.value}_{underscore_code.lower()}.json",
        base_dir / f"{product_type.value}_{stripped_underscore.lower()}.json",
        base_dir / f"{product_type.value}_{underscore_code.upper()}.json",
        base_dir / f"{product_type.value}_{hyphen_code.lower()}.json",
        base_dir / f"{product_type.value}_{hyphen_code.upper()}.json",
        base_dir / f"{product_type.value}_{raw}.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


@lru_cache(maxsize=256)
def _load_and_validate_cached(file_path_str: str) -> ROITemplate:
    file_path = Path(file_path_str)
    try:
        raw_text = file_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ROITemplateNotFoundError(f"ROI template file not found: {file_path}") from exc
    except OSError as exc:
        raise ROITemplateError(f"Failed reading ROI template '{file_path}': {exc}") from exc

    try:
        raw_data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ROITemplateValidationError(
            f"Malformed JSON in ROI template '{file_path}': {exc}"
        ) from exc

    try:
        template = ROITemplate.model_validate(raw_data)
    except Exception as exc:  # pydantic ValidationError + our ValueError-raising validators
        raise ROITemplateValidationError(
            f"ROI template '{file_path}' failed validation: {exc}"
        ) from exc

    return template


async def load_roi_template(
    product_type: ProductType,
    part_code: str,
    base_dir: Path = DEFAULT_ROI_TEMPLATE_DIR,
) -> ROITemplate:
    """
    Load and validate an ROI template for the given (product_type, part_code).

    Runs sync file IO on the default thread pool to keep this awaitable-safe
    for use inside async pipeline stages, without blocking the event loop.
    """
    import asyncio

    file_path = _template_file_path(product_type, part_code, base_dir)
    loop = asyncio.get_running_loop()
    try:
        template = await loop.run_in_executor(None, _load_and_validate_cached, str(file_path))
    except ROITemplateError:
        raise
    except Exception as exc:
        raise ROITemplateError(f"Unexpected error loading ROI template '{file_path}': {exc}") from exc

    logger.info(
        "Loaded ROI template id=%s product_type=%s part_code=%s regions=%d",
        template.id,
        template.product_type.value,
        template.part_code,
        len(template.regions),
    )
    return template


def validate_roi_template(template: ROITemplate) -> None:
    """
    Re-run semantic validation on an already-constructed template instance.

    Pydantic validators already run on construction; this exists as an
    explicit entry point for callers (e.g. an admin upload endpoint) that
    build a ROITemplate programmatically and want a dedicated validation
    step before persisting it.
    """
    try:
        ROITemplate.model_validate(template.model_dump(by_alias=True))
    except Exception as exc:
        raise ROITemplateValidationError(f"ROI template '{template.id}' failed validation: {exc}") from exc


def get_rois_by_priority(template: ROITemplate) -> list[ROITemplateRegion]:
    return sorted(
        template.regions,
        key=lambda r: (_PRIORITY_ORDER[r.priority.value], r.id),
    )


def get_rois_by_agent(template: ROITemplate, agent: AgentType) -> list[ROITemplateRegion]:
    return [r for r in template.regions if r.agent == agent]


def get_roi_by_id(template: ROITemplate, roi_id: str) -> Optional[ROITemplateRegion]:
    for region in template.regions:
        if region.id == roi_id:
            return region
    return None


def create_execution_plan(template: ROITemplate) -> ROIExecutionPlan:
    """
    Build the Stage 4 (ROI Scheduler) output consumed by Stage 5.

    Contract:
      - Each ROI maps to exactly one agent (enforced at model-validation time).
      - ROIs sharing an agent are grouped into a single ROIExecutionBatch.
      - Items and batches are ordered critical -> high -> normal.
      - A batch's priority is the highest-priority (lowest ordinal) ROI it contains.
    """
    ordered_regions = get_rois_by_priority(template)

    items = [
        ROIExecutionItem(
            roi_id=region.id,
            agent=region.agent,
            priority=region.priority,
            bbox=region.bbox,
        )
        for region in ordered_regions
    ]

    batch_map: dict[AgentType, list[ROITemplateRegion]] = {}
    for region in ordered_regions:
        batch_map.setdefault(region.agent, []).append(region)

    batches: list[ROIExecutionBatch] = []
    for agent, regions in batch_map.items():
        batch_priority = min(regions, key=lambda r: _PRIORITY_ORDER[r.priority.value]).priority
        batches.append(
            ROIExecutionBatch(
                agent=agent,
                roi_ids=[r.id for r in regions],
                priority=batch_priority,
            )
        )

    batches.sort(key=lambda b: (_PRIORITY_ORDER[b.priority.value], b.agent.value))

    plan = ROIExecutionPlan(template_id=template.id, items=items, batches=batches)

    logger.info(
        "Built execution plan template_id=%s items=%d batches=%d",
        plan.template_id,
        len(plan.items),
        len(plan.batches),
    )
    return plan


def clear_roi_template_cache() -> None:
    """Evict the lru_cache — call after an admin template upload/edit."""
    _load_and_validate_cached.cache_clear()