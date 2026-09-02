# backend/tests/test_integration_stages_1_2_3.py
"""
Integration test — Stages 1 → 2 → 3 end-to-end (Anil + Disha, W2 D6).

Verifies the full pre-agent pipeline flow:
  1. Quality check on synthetic images
  2. Authenticity verification (ELA, EXIF, noise, copy-move, screenshot)
  3. Reference matching against a mock FAISS index

Uses monkeypatched embedding service (no network, no model downloads).
No real golden references needed — the DB lookup is faked.
"""
from __future__ import annotations

import asyncio
import uuid

import cv2
import numpy as np
import pytest

from app.pipeline.stages import authenticity as auth
from app.pipeline.stages import quality_check as qc
from app.pipeline.stages import reference_match as rm
from app.pipeline.state import STAGE_ORDER, InspectionState
from app.services.embedding_service import embedding_service
from app.shared.evidence_store import EvidenceStore
from app.shared.memory import PipelineStageName, StageResult, WorkingMemory


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_image(path, size=(800, 600), brightness=128, noise=15.0):
    """Write a synthetic image with controllable noise/brightness."""
    rng = np.random.default_rng(abs(hash(str(path))) % (2**32))
    img = np.full((size[1], size[0], 3), brightness, dtype=np.uint8)
    img = img + rng.normal(0, noise, img.shape).astype(np.int16)
    img = np.clip(img, 0, 255).astype(np.uint8)
    img[100:-100, 100:-100] = np.clip(
        img[100:-100, 100:-100].astype(int) + 60, 0, 255
    ).astype(np.uint8)
    cv2.imwrite(str(path), img)
    return str(path)


def make_state(tmp_path, image_paths):
    memory = WorkingMemory(inspection_id=uuid.uuid4(), image_paths=image_paths)
    return InspectionState(memory=memory, evidence=EvidenceStore())


class _FakeScalar:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeDB:
    """Minimal AsyncSession stand-in for golden-reference lookup."""

    def __init__(self, golden):
        self._golden = golden

    async def execute(self, _query):
        return _FakeScalar(self._golden)


# ── Integration: Stage 1 → 2 → 3 on a clean image ────────────────────────────

def test_stages_1_2_3_clean_image_end_to_end(tmp_path, monkeypatch):
    """
    Full pipeline on a clean, sharp, well-lit image:
      - Stage 1 (quality) must PASS
      - Stage 2 (authenticity) must PASS (no flags)
      - Stage 3 (reference match) must PASS with golden pairing
    """
    from app.models.product import GoldenReference

    img_path = make_image(tmp_path / "clean.jpg")
    golden = GoldenReference(
        id=uuid.uuid4(),
        part_id="PCB-MCU-V2",
        part_name="MCU Board V2",
        image_path="data/golden_images/mcu_front.jpg",
        view_angle="front",
    )

    # --- Stage 1: Quality Check ---
    state = make_state(tmp_path, [img_path])
    stage1 = asyncio.run(qc.run_quality_check(state))

    assert stage1.status == "passed", f"Stage 1 failed: {stage1.error}"
    assert state.memory.quality_passed is True

    # --- Stage 2: Authenticity ---
    stage2 = asyncio.run(auth.run_authenticity_stage(state))

    assert stage2.status in ("passed", "flagged"), f"Stage 2 failed: {stage2.error}"
    assert state.memory.authenticity_score is not None

    # --- Stage 3: Reference Match (mocked embedding) ---
    monkeypatch.setattr(
        embedding_service, "generate_embedding",
        lambda image, try_gemini=True: np.ones(512, dtype=np.float32) / 24,
    )
    monkeypatch.setattr(
        embedding_service, "search",
        lambda emb, k=5: [(str(golden.id), 0.92)],
    )

    stage3 = asyncio.run(rm.run_reference_match(state, _FakeDB(golden)))

    assert stage3.status == "passed", f"Stage 3 failed: {stage3.error}"
    assert state.memory.golden_reference_id == golden.id
    assert state.memory.similarity_score == pytest.approx(0.92)
    assert state.memory.golden_image_path == golden.image_path

    # Verify all stages recorded in memory
    assert len(state.memory.stage_history) == 3
    stage_names = [r.stage for r in state.memory.stage_history]
    assert PipelineStageName.QUALITY_CHECK in stage_names
    assert PipelineStageName.AUTHENTICITY in stage_names
    assert PipelineStageName.REFERENCE_MATCH in stage_names


# ── Integration: Stage 1 fails → Stages 2 and 3 skip ─────────────────────────

def test_stage1_failure_halts_pipeline(tmp_path):
    """
    Blurry image → Stage 1 FAILS → Stage 2 must skip (quality gate),
    Stage 3 must not be reached.
    """
    img = np.full((600, 800, 3), 128, dtype=np.uint8)  # flat = blurry
    blurry = str(tmp_path / "blurry.jpg")
    cv2.imwrite(blurry, img)

    state = make_state(tmp_path, [blurry])
    stage1 = asyncio.run(qc.run_quality_check(state))

    assert stage1.status == "failed"
    assert state.memory.quality_passed is False

    # Stage 2 must fail because quality didn't pass
    stage2 = asyncio.run(auth.run_authenticity_stage(state))
    assert stage2.status == "failed"
    assert "quality_check" in (stage2.error or "").lower()


# ── Integration: Stage 2 flags but does not block ─────────────────────────────

def test_stage2_flagged_does_not_block_stage3(tmp_path, monkeypatch):
    """
    Authenticity score is low (flagged) but above hard-block threshold →
    Stage 2 status = 'flagged', pipeline continues to Stage 3.
    """
    from app.models.product import GoldenReference

    img_path = make_image(tmp_path / "suspicious.jpg")
    golden = GoldenReference(
        id=uuid.uuid4(),
        part_id="BAT-STD-V1",
        part_name="Battery Standard",
        image_path="data/golden_images/battery.jpg",
        view_angle="front",
    )

    state = make_state(tmp_path, [img_path])

    # Stage 1 passes
    stage1 = asyncio.run(qc.run_quality_check(state))
    assert stage1.status == "passed"

    # Stage 2: fake a flagged-but-not-blocked result
    monkeypatch.setattr(auth.settings, "AUTHENTICITY_FLAG_THRESHOLD", 0.6)
    monkeypatch.setattr(auth.settings, "AUTHENTICITY_HARD_BLOCK_THRESHOLD", 0.3)

    async def fake_analyze(insp_id, path):
        return auth.AuthenticityResult(
            inspection_id=insp_id,
            image_id=uuid.uuid4(),
            ela=auth.ELAResult(error_map_mean=1.0, error_map_std=1.0, ela_score=0.05),
            exif=auth.ExifResult(has_exif=True, exif_score=1.0),
            screenshot=auth.ScreenshotResult(is_screenshot=False, confidence=0.0),
            noise=auth.NoiseConsistencyResult(consistency_score=1.0),
            copy_move=auth.CopyMoveResult(matched_blocks=0, copy_move_score=0.0),
            flags=[],
            authenticity_score=0.45,
            is_suspicious=True,
            processing_time_ms=1.0,
        )

    monkeypatch.setattr(auth, "_analyze_image", fake_analyze)
    stage2 = asyncio.run(auth.run_authenticity_stage(state))

    assert stage2.status == "flagged"
    assert state.memory.authenticity_flagged is True

    # Stage 3 still runs (authenticity never hard-blocks)
    monkeypatch.setattr(
        embedding_service, "generate_embedding",
        lambda image, try_gemini=True: np.ones(512, dtype=np.float32) / 24,
    )
    monkeypatch.setattr(
        embedding_service, "search",
        lambda emb, k=5: [(str(golden.id), 0.85)],
    )

    stage3 = asyncio.run(rm.run_reference_match(state, _FakeDB(golden)))
    assert stage3.status == "passed"
    assert state.memory.golden_reference_id == golden.id


# ── Integration: Stage 3 flags when similarity is below threshold ─────────────

def test_stage3_below_threshold_flags_for_manual_review(tmp_path, monkeypatch):
    """
    Reference match score below SIMILARITY_THRESHOLD → flagged for manual review.
    """
    from app.models.product import GoldenReference

    img_path = make_image(tmp_path / "unknown_part.jpg")
    golden = GoldenReference(
        id=uuid.uuid4(),
        part_id="PCB-UNKNOWN",
        part_name="Unknown Part",
        image_path="data/golden_images/unknown.jpg",
        view_angle="front",
    )

    state = make_state(tmp_path, [img_path])

    # Stage 1 passes
    stage1 = asyncio.run(qc.run_quality_check(state))
    assert stage1.status == "passed"

    # Stage 2 passes (skip heavy analysis)
    monkeypatch.setattr(auth.settings, "AUTHENTICITY_FLAG_THRESHOLD", 0.6)
    monkeypatch.setattr(auth.settings, "AUTHENTICITY_HARD_BLOCK_THRESHOLD", 0.3)

    async def fake_analyze(insp_id, path):
        return auth.AuthenticityResult(
            inspection_id=insp_id,
            image_id=uuid.uuid4(),
            ela=auth.ELAResult(error_map_mean=1.0, error_map_std=1.0, ela_score=0.01),
            exif=auth.ExifResult(has_exif=True, exif_score=1.0),
            screenshot=auth.ScreenshotResult(is_screenshot=False, confidence=0.0),
            noise=auth.NoiseConsistencyResult(consistency_score=1.0),
            copy_move=auth.CopyMoveResult(matched_blocks=0, copy_move_score=0.0),
            flags=[],
            authenticity_score=0.95,
            is_suspicious=False,
            processing_time_ms=1.0,
        )

    monkeypatch.setattr(auth, "_analyze_image", fake_analyze)
    stage2 = asyncio.run(auth.run_authenticity_stage(state))
    assert stage2.status == "passed"

    # Stage 3: low similarity score
    monkeypatch.setattr(
        embedding_service, "generate_embedding",
        lambda image, try_gemini=True: np.ones(512, dtype=np.float32) / 24,
    )
    monkeypatch.setattr(
        embedding_service, "search",
        lambda emb, k=5: [(str(golden.id), 0.45)],
    )

    stage3 = asyncio.run(rm.run_reference_match(state, _FakeDB(golden)))
    assert stage3.status == "flagged"
    assert "below threshold" in (stage3.error or "").lower()
    assert state.memory.golden_reference_id is None


# ── Integration: Golden reference deleted from DB after FAISS match ────────────

def test_stage3_flags_when_golden_deleted(tmp_path, monkeypatch):
    """
    FAISS finds a match but the golden reference no longer exists in DB → flagged.
    """
    img_path = make_image(tmp_path / "orphan.jpg")

    state = make_state(tmp_path, [img_path])

    # Stage 1 passes
    stage1 = asyncio.run(qc.run_quality_check(state))
    assert stage1.status == "passed"

    # Stage 2 passes
    monkeypatch.setattr(auth.settings, "AUTHENTICITY_FLAG_THRESHOLD", 0.6)
    monkeypatch.setattr(auth.settings, "AUTHENTICITY_HARD_BLOCK_THRESHOLD", 0.3)

    async def fake_analyze(insp_id, path):
        return auth.AuthenticityResult(
            inspection_id=insp_id,
            image_id=uuid.uuid4(),
            ela=auth.ELAResult(error_map_mean=1.0, error_map_std=1.0, ela_score=0.01),
            exif=auth.ExifResult(has_exif=True, exif_score=1.0),
            screenshot=auth.ScreenshotResult(is_screenshot=False, confidence=0.0),
            noise=auth.NoiseConsistencyResult(consistency_score=1.0),
            copy_move=auth.CopyMoveResult(matched_blocks=0, copy_move_score=0.0),
            flags=[],
            authenticity_score=0.95,
            is_suspicious=False,
            processing_time_ms=1.0,
        )

    monkeypatch.setattr(auth, "_analyze_image", fake_analyze)
    stage2 = asyncio.run(auth.run_authenticity_stage(state))
    assert stage2.status == "passed"

    # Stage 3: FAISS finds match but DB says it's gone
    fake_id = str(uuid.uuid4())
    monkeypatch.setattr(
        embedding_service, "generate_embedding",
        lambda image, try_gemini=True: np.ones(512, dtype=np.float32) / 24,
    )
    monkeypatch.setattr(
        embedding_service, "search",
        lambda emb, k=5: [(fake_id, 0.90)],
    )

    stage3 = asyncio.run(rm.run_reference_match(state, _FakeDB(None)))
    assert stage3.status == "flagged"
    assert state.memory.golden_reference_id is None


# ── Integration: Multi-image inspection ───────────────────────────────────────

def test_stages_1_2_3_multi_image(tmp_path, monkeypatch):
    """
    Two clean images uploaded — quality check validates both, authenticity
    averages scores, reference match uses the first image.
    """
    from app.models.product import GoldenReference

    img_a = make_image(tmp_path / "angle_a.jpg")
    img_b = make_image(tmp_path / "angle_b.jpg", brightness=90)
    golden = GoldenReference(
        id=uuid.uuid4(),
        part_id="RAM-DDR4-V1",
        part_name="DDR4 Module",
        image_path="data/golden_images/ram_front.jpg",
        view_angle="front",
    )

    state = make_state(tmp_path, [img_a, img_b])

    # Stage 1: both images pass quality
    stage1 = asyncio.run(qc.run_quality_check(state))
    assert stage1.status == "passed"
    assert len(stage1.data["per_image"]) == 2

    # Stage 2: both images analyzed, score averaged
    stage2 = asyncio.run(auth.run_authenticity_stage(state))
    assert stage2.status in ("passed", "flagged")
    assert len(stage2.data["per_image"]) == 2

    # Stage 3: uses first image for embedding
    monkeypatch.setattr(
        embedding_service, "generate_embedding",
        lambda image, try_gemini=True: np.ones(512, dtype=np.float32) / 24,
    )
    monkeypatch.setattr(
        embedding_service, "search",
        lambda emb, k=5: [(str(golden.id), 0.88)],
    )

    stage3 = asyncio.run(rm.run_reference_match(state, _FakeDB(golden)))
    assert stage3.status == "passed"
    assert state.memory.golden_reference_id == golden.id

    # All 3 stages recorded
    assert len(state.memory.stage_history) == 3


# ── Integration: Progress tracking across stages ──────────────────────────────

def test_progress_tracks_through_all_stages(tmp_path, monkeypatch):
    """
    Verify the SSE progress payload updates correctly as stages complete.
    """
    from app.models.product import GoldenReference

    img_path = make_image(tmp_path / "progress.jpg")
    golden = GoldenReference(
        id=uuid.uuid4(),
        part_id="PCB-MCU-V2",
        part_name="MCU Board V2",
        image_path="data/golden_images/mcu.jpg",
        view_angle="front",
    )

    state = make_state(tmp_path, [img_path])

    # Before any stage
    p = state.progress()
    assert p["stage"] == 1 and p["status"] == "in_progress" and p["progress"] == 0

    # After Stage 1
    asyncio.run(qc.run_quality_check(state))
    p = state.progress()
    assert p["stage"] == 2 and p["progress"] == 1

    # After Stage 2
    monkeypatch.setattr(auth.settings, "AUTHENTICITY_FLAG_THRESHOLD", 0.6)
    monkeypatch.setattr(auth.settings, "AUTHENTICITY_HARD_BLOCK_THRESHOLD", 0.3)

    async def fake_analyze(insp_id, path):
        return auth.AuthenticityResult(
            inspection_id=insp_id,
            image_id=uuid.uuid4(),
            ela=auth.ELAResult(error_map_mean=1.0, error_map_std=1.0, ela_score=0.01),
            exif=auth.ExifResult(has_exif=True, exif_score=1.0),
            screenshot=auth.ScreenshotResult(is_screenshot=False, confidence=0.0),
            noise=auth.NoiseConsistencyResult(consistency_score=1.0),
            copy_move=auth.CopyMoveResult(matched_blocks=0, copy_move_score=0.0),
            flags=[],
            authenticity_score=0.90,
            is_suspicious=False,
            processing_time_ms=1.0,
        )

    monkeypatch.setattr(auth, "_analyze_image", fake_analyze)
    asyncio.run(auth.run_authenticity_stage(state))
    p = state.progress()
    assert p["stage"] == 3 and p["progress"] == 2

    # After Stage 3
    monkeypatch.setattr(
        embedding_service, "generate_embedding",
        lambda image, try_gemini=True: np.ones(512, dtype=np.float32) / 24,
    )
    monkeypatch.setattr(
        embedding_service, "search",
        lambda emb, k=5: [(str(golden.id), 0.95)],
    )
    asyncio.run(rm.run_reference_match(state, _FakeDB(golden)))
    p = state.progress()
    assert p["stage"] == 4 and p["progress"] == 3


# ── Integration: Evidence store accumulates across stages ─────────────────────

def test_evidence_store_accumulates_across_stages(tmp_path):
    """
    Verify the EvidenceStore is populated as InspectionState bridges evidence
    from agents into the append-only store.
    """
    state = make_state(tmp_path, [])

    # Simulate agent evidence writes
    asyncio.run(state.append_evidence(
        agent_type="ocr",
        roi_id="serial_label",
        confidence=0.95,
        evidence={"text": "SN12345"},
        explanation="Serial number matches golden reference",
        processing_time_ms=12.5,
    ))

    asyncio.run(state.append_evidence(
        agent_type="structural",
        roi_id="capacitor_bank_1",
        confidence=0.82,
        evidence={"detected": 4, "expected": 4},
        explanation="All 4 capacitors detected",
        processing_time_ms=45.0,
    ))

    count = state.evidence.count(state.memory.inspection_id)
    assert count == 2
    assert len(state.memory.evidence_refs) == 2
