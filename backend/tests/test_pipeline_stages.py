# backend/tests/test_pipeline_stages.py
"""
Unit tests for Anil's W2 D1-D3 deliverables:
  - pipeline/stages/quality_check.py (Stage 1)
  - pipeline/state.py (InspectionState bridge)
  - pipeline/stages/reference_match.py (Stage 3, with mocked embedding service)
"""
from __future__ import annotations

import asyncio
import uuid

import cv2
import numpy as np
import pytest

from app.pipeline.stages import quality_check as qc
from app.pipeline.stages import reference_match as rm
from app.pipeline.state import STAGE_ORDER, InspectionState
from app.services.embedding_service import embedding_service
from app.shared.evidence_store import AgentType, EvidenceStore
from app.shared.memory import PipelineStageName, StageResult, WorkingMemory


# ── helpers ───────────────────────────────────────────────────────────────────

def make_image(path, size=(800, 600), brightness=128, noise=15.0):
    """Write a synthetic image with controllable noise/brightness. Returns path."""
    rng = np.random.default_rng(abs(hash(str(path))) % (2**32))
    img = np.full((size[1], size[0], 3), brightness, dtype=np.uint8)
    img = img + rng.normal(0, noise, img.shape).astype(np.int16)
    img = np.clip(img, 0, 255).astype(np.uint8)
    # add sharp edges so it isn't blurry
    img[100:-100, 100:-100] = np.clip(
        img[100:-100, 100:-100].astype(int) + 60, 0, 255
    ).astype(np.uint8)
    cv2.imwrite(str(path), img)
    return str(path)


def make_state(tmp_path, image_paths):
    memory = WorkingMemory(inspection_id=uuid.uuid4(), image_paths=image_paths)
    return InspectionState(memory=memory, evidence=EvidenceStore())


# ── quality_check ─────────────────────────────────────────────────────────────

def test_validate_image_passes_clean_sharp_image(tmp_path):
    p = make_image(tmp_path / "good.jpg")
    result = qc.validate_image(p)
    assert result["passed"] is True, result["reasons"]
    assert result["metrics"]["blur_variance"] > 0


def test_validate_image_rejects_blurry(tmp_path):
    img = np.full((600, 800, 3), 128, dtype=np.uint8)
    p = str(tmp_path / "blurry.jpg")
    cv2.imwrite(p, img)
    result = qc.validate_image(p)
    assert result["passed"] is False
    assert any("blurry" in r for r in result["reasons"])


def test_validate_image_rejects_dark_and_bright(tmp_path):
    dark = make_image(tmp_path / "dark.jpg", brightness=10, noise=3.0)
    assert qc.validate_image(dark)["passed"] is False

    bright = make_image(tmp_path / "bright.jpg", brightness=250, noise=3.0)
    res = qc.validate_image(bright)
    assert any("overexposed" in r for r in res["reasons"])


def test_validate_image_rejects_corrupt_file(tmp_path):
    p = tmp_path / "corrupt.jpg"
    p.write_bytes(b"not-an-image")
    result = qc.validate_image(str(p))
    assert result["passed"] is False
    assert any("Corrupted" in r for r in result["reasons"])


def test_validate_image_rejects_low_resolution(tmp_path):
    p = make_image(tmp_path / "small.jpg", size=(320, 240))
    result = qc.validate_image(p)
    assert any("Resolution" in r for r in result["reasons"])


def test_duplicates_detected_in_stage_run(tmp_path):
    good = make_image(tmp_path / "a.jpg")
    dup = make_image(tmp_path / "b.jpg")  # same params => near-identical
    other = make_image(tmp_path / "c.jpg", brightness=90)

    state = make_state(None, [good, dup, other])
    result = asyncio.run(qc.run_quality_check(state))

    assert result.status == "passed"
    assert len(result.data["duplicate_groups"]) >= 1
    assert dup in result.data["ignored_duplicates"]
    assert state.memory.quality_passed is True


def test_stage_fails_on_blurry_primary(tmp_path):
    img = np.full((600, 800, 3), 128, dtype=np.uint8)
    blurry = str(tmp_path / "blurry.jpg")
    cv2.imwrite(blurry, img)

    state = make_state(None, [blurry])
    result = asyncio.run(qc.run_quality_check(state))

    assert result.status == "failed"
    assert state.memory.quality_passed is False
    assert result.error and "blurry" in result.error.lower()


# ── state.py ──────────────────────────────────────────────────────────────────

def test_state_append_evidence_updates_memory_refs():
    state = make_state(None, [])

    record = asyncio.run(state.append_evidence(
        agent_type=AgentType.OCR,
        roi_id="roi-1",
        confidence=0.9,
        evidence={"text": "SN12345"},
        explanation="serial matched",
        processing_time_ms=12.5,
    ))

    assert record.sequence == 0
    assert state.memory.evidence_refs == [record.evidence_id]
    assert state.evidence.count(state.memory.inspection_id) == 1


def test_state_progress_tracks_stages():
    state = make_state(None, [])

    # nothing recorded yet -> stage 1 in_progress, progress 0
    p = state.progress()
    assert p["stage"] == 1 and p["status"] == "in_progress" and p["progress"] == 0

    # record stage 1 passed
    asyncio.run(state.record_stage(StageResult(
        stage=PipelineStageName.QUALITY_CHECK, status="passed")))
    p = state.progress()
    assert p["stage"] == 2 and p["progress"] == 1

    # fail a later stage -> progress reflects the failure
    asyncio.run(state.record_stage(StageResult(
        stage=PipelineStageName.AUTHENTICITY, status="failed", error="EXIF missing")))
    p = state.progress()
    assert p["status"] == "failed" and p["stage_name"] == "authenticity"
    assert "EXIF" in str(p["detail"])


def test_stage_order_is_complete():
    assert len(STAGE_ORDER) == 8
    assert STAGE_ORDER[0] == PipelineStageName.QUALITY_CHECK
    assert STAGE_ORDER[-1] == PipelineStageName.POLICY_ENGINE


# ── reference_match ───────────────────────────────────────────────────────────

class _FakeScalar:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeDB:
    """Minimal AsyncSession stand-in for the golden-reference lookup."""

    def __init__(self, golden):
        self._golden = golden

    async def execute(self, _query):
        return _FakeScalar(self._golden)


def _golden(part_id="PCB-MCU-V2"):
    from app.models.product import GoldenReference

    return GoldenReference(
        id=uuid.uuid4(),
        part_id=part_id,
        part_name="MCU Board V2",
        image_path="data/golden_images/mcu_front.jpg",
        view_angle="front",
    )


def test_reference_match_passes_above_threshold(tmp_path, monkeypatch):
    golden = _golden()
    img = make_image(tmp_path / "inspect.jpg")

    monkeypatch.setattr(
        embedding_service, "generate_embedding",
        lambda image, try_gemini=True: np.ones(512, dtype=np.float32) / 24,
    )
    monkeypatch.setattr(
        embedding_service, "search",
        lambda emb, k=5: [(str(golden.id), 0.93)],
    )

    state = make_state(None, [img])
    result = asyncio.run(rm.run_reference_match(state, _FakeDB(golden)))

    assert result.status == "passed", result.error
    assert state.memory.golden_reference_id == golden.id
    assert state.memory.similarity_score == pytest.approx(0.93)
    assert state.memory.golden_image_path == golden.image_path


def test_reference_match_flags_below_threshold(tmp_path, monkeypatch):
    golden = _golden()
    img = make_image(tmp_path / "inspect.jpg")

    monkeypatch.setattr(
        embedding_service, "generate_embedding",
        lambda image, try_gemini=True: np.ones(512, dtype=np.float32) / 24,
    )
    monkeypatch.setattr(
        embedding_service, "search",
        lambda emb, k=5: [(str(golden.id), 0.52)],
    )

    state = make_state(None, [img])
    result = asyncio.run(rm.run_reference_match(state, _FakeDB(golden)))

    assert result.status == "flagged"
    assert "below threshold" in (result.error or "").lower()
    assert state.memory.golden_reference_id is None


def test_reference_match_flags_when_index_empty(tmp_path, monkeypatch):
    img = make_image(tmp_path / "inspect.jpg")
    monkeypatch.setattr(
        embedding_service, "generate_embedding",
        lambda image, try_gemini=True: np.ones(512, dtype=np.float32) / 24,
    )
    monkeypatch.setattr(embedding_service, "search", lambda emb, k=5: [])

    state = make_state(None, [img])
    result = asyncio.run(rm.run_reference_match(state, _FakeDB(None)))

    assert result.status == "flagged"
    assert state.memory.golden_reference_id is None
