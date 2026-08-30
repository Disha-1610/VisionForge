# backend/app/pipeline/workflow.py
"""
LangGraph pipeline wiring — implemented in Week 4 (see IMPLEMENTATION_PLAN.md).

This stub exists so that app.routers.inspections can be imported and wired
into main.py without an ImportError. It will be replaced by the real
8-stage LangGraph graph.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def run_inspection_pipeline(inspection_id: UUID, db: AsyncSession) -> None:
    """
    Execute the full 8-stage pipeline for one inspection.

    Stub: raises until the LangGraph workflow (Week 4) is implemented.
    The caller (routers.inspections._run_pipeline_background) already
    marks the inspection as FAILED if this raises.
    """
    logger.warning("run_inspection_pipeline called but pipeline is not implemented yet")
    raise NotImplementedError(
        "Pipeline workflow not implemented yet (Week 4 task — "
        "see pipeline/stages/ and pipeline/workflow.py in IMPLEMENTATION_PLAN.md)"
    )
