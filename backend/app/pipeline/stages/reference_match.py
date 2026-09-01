# backend/app/pipeline/stages/reference_match.py
"""
Stage 3 — Reference Intelligence (Anil, W2 D2).

Embedding + vector search against the Golden Reference Repository:
  1. Generate a normalized embedding for the primary inspection image
     (Gemini 1-shot -> local OpenCLIP fallback — handled by embedding_service).
  2. Search the FAISS index for the most similar golden image.
  3. Select the best match above SIMILARITY_THRESHOLD (0.75).
  4. Load the golden reference from the DB and attach it to WorkingMemory.

Outcomes: passed (pairing locked in) | flagged (below threshold / not found
-> manual review) | failed (embedding generation broke).
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.product import GoldenReference
from app.pipeline.state import InspectionState
from app.services.embedding_service import embedding_service
from app.shared.memory import PipelineStageName, StageResult
from app.utils.image_utils import load_pil_image

logger = logging.getLogger("app.pipeline.reference_match")


async def run_reference_match(state: InspectionState, db: AsyncSession) -> StageResult:
    """
    Stage 3 entrypoint. Uses the first inspection image (quality stage has
    already guaranteed all images are usable). On success, WorkingMemory holds
    golden_reference_id + golden_image_path + similarity_score for Stage 4.
    """
    inspection_id = state.memory.inspection_id
    paths = state.memory.image_paths
    if not paths:
        return await state.record_stage(
            StageResult(
                stage=PipelineStageName.REFERENCE_MATCH,
                status="failed",
                error="No inspection image available for reference matching",
            )
        )
    primary_path = paths[0]

    # 1. Generate the query embedding (dual: Gemini 1-shot -> OpenCLIP fallback)
    try:
        query_embedding = embedding_service.generate_embedding(
            load_pil_image(primary_path)
        )
    except Exception as exc:
        logger.exception("Embedding generation failed for inspection %s", inspection_id)
        return await state.record_stage(
            StageResult(
                stage=PipelineStageName.REFERENCE_MATCH,
                status="failed",
                error=f"Embedding generation failed: {exc}",
            )
        )

    # 2. Vector search against the golden index
    candidates: list[tuple[str, float]] = embedding_service.search(query_embedding, k=5)
    if not candidates:
        return await state.record_stage(
            StageResult(
                stage=PipelineStageName.REFERENCE_MATCH,
                status="flagged",
                data={"reason": "no_golden_references_indexed"},
                error="Golden reference index is empty — upload golden images first",
            )
        )

    best_id, best_score = candidates[0]
    detail: dict[str, Any] = {
        "primary_image": primary_path,
        "best_score": round(best_score, 4),
        "threshold": settings.SIMILARITY_THRESHOLD,
        "candidates": [
            {"reference_id": cid, "score": round(float(score), 4)} for cid, score in candidates
        ],
    }

    # 3. Threshold gate — below it we do NOT pair; manual review instead
    if best_score < settings.SIMILARITY_THRESHOLD:
        detail["reason"] = "below_similarity_threshold"
        return await state.record_stage(
            StageResult(
                stage=PipelineStageName.REFERENCE_MATCH,
                status="flagged",
                data=detail,
                error=(
                    f"Best golden match score {best_score:.3f} below threshold "
                    f"{settings.SIMILARITY_THRESHOLD} — marked for manual review"
                ),
            )
        )

    # 4. Resolve the golden reference record from the DB
    try:
        reference_id = uuid.UUID(best_id)
    except ValueError:
        return await state.record_stage(
            StageResult(
                stage=PipelineStageName.REFERENCE_MATCH,
                status="failed",
                data=detail,
                error=f"Malformed reference id in FAISS index: {best_id!r}",
            )
        )

    result = await db.execute(
        select(GoldenReference).where(GoldenReference.id == reference_id)
    )
    golden = result.scalar_one_or_none()
    if golden is None:
        detail["reason"] = "golden_reference_missing"
        return await state.record_stage(
            StageResult(
                stage=PipelineStageName.REFERENCE_MATCH,
                status="flagged",
                data=detail,
                error=f"Matched reference {reference_id} no longer exists in DB",
            )
        )

    # 5. Lock in the pairing
    await state.memory.update(
        similarity_score=float(best_score),
        golden_reference_id=golden.id,
        golden_image_path=golden.image_path,
    )

    detail["matched_reference"] = {
        "id": str(golden.id),
        "part_id": golden.part_id,
        "part_name": golden.part_name,
        "view_angle": golden.view_angle,
        "image_path": golden.image_path,
    }
    return await state.record_stage(
        StageResult(
            stage=PipelineStageName.REFERENCE_MATCH,
            status="passed",
            data=detail,
        )
    )
