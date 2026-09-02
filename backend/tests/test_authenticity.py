from __future__ import annotations
import asyncio
import uuid
import cv2
import numpy as np
import pytest
from app.pipeline.stages import authenticity as auth
from app.pipeline.state import InspectionState
from app.shared.evidence_store import EvidenceStore
from app.shared.memory import WorkingMemory
# ── helpers ───────────────────────────────────────────────────────────────────
def make_image(path, size=(800, 600), brightness=128, noise=15.0, uniform=False):
    """Write a synthetic image. uniform=True produces flat rows/cols (screenshot-like)."""
    if uniform:
        img = np.full((size[1], size[0], 3), brightness, dtype=np.uint8)
    else:
        rng = np.random.default_rng(abs(hash(str(path))) % (2**32))
        img = np.full((size[1], size[0], 3), brightness, dtype=np.uint8)
        img = img + rng.normal(0, noise, img.shape).astype(np.int16)
        img = np.clip(img, 0, 255).astype(np.uint8)
        img[100:-100, 100:-100] = np.clip(
            img[100:-100, 100:-100].astype(int) + 60, 0, 255
        ).astype(np.uint8)
    cv2.imwrite(str(path), img)
    return str(path)

def make_ready_state(image_paths, quality_passed=True):
    memory = WorkingMemory(inspection_id=uuid.uuid4(), image_paths=image_paths)
    if quality_passed:
        asyncio.run(memory.update(quality_passed=True))
    return InspectionState(memory=memory, evidence=EvidenceStore())

def _fake_result(score, inspection_id=None):
    return auth.AuthenticityResult(
        inspection_id=inspection_id or uuid.uuid4(),
        image_id=uuid.uuid4(),
        ela=auth.ELAResult(error_map_mean=1.0, error_map_std=1.0, ela_score=0.05),
        exif=auth.ExifResult(has_exif=True, exif_score=1.0),
        screenshot=auth.ScreenshotResult(is_screenshot=False, confidence=0.0),
        noise=auth.NoiseConsistencyResult(consistency_score=1.0),
        copy_move=auth.CopyMoveResult(matched_blocks=0, copy_move_score=0.0),
        flags=[],
        authenticity_score=score,
        is_suspicious=score < 0.6,
        processing_time_ms=1.0,
    )
# ── ELA ───────────────────────────────────────────────────────────────────────
def test_ela_clean_image_low_score(tmp_path):
    p = make_image(tmp_path / "clean.jpg")
    result = asyncio.run(auth._compute_ela(p))
    assert 0.0 <= result.ela_score <= 1.0
    assert result.error_map_mean >= 0.0

def test_ela_missing_file_returns_zero_score(tmp_path):
    result = asyncio.run(auth._compute_ela(str(tmp_path / "missing.jpg")))
    assert result.ela_score == 0.0
    assert result.suspicious_regions == []
# ── EXIF ──────────────────────────────────────────────────────────────────────
def test_exif_missing_on_synthetic_image(tmp_path):
    p = make_image(tmp_path / "no_exif.jpg")
    result = asyncio.run(auth._validate_exif(p))
    assert result.has_exif is False
    assert result.exif_score == 0.0
    assert result.camera_make is None

def test_exif_unreadable_file_treated_as_missing(tmp_path):
    p = tmp_path / "corrupt.jpg"
    p.write_bytes(b"not-an-image")
    result = asyncio.run(auth._validate_exif(str(p)))
    assert result.has_exif is False
# ── Screenshot detection ────────────────────────────────────────────────────────
def test_screenshot_flat_image_detected(tmp_path):
    p = make_image(tmp_path / "flat.jpg", uniform=True)
    result = asyncio.run(auth._detect_screenshot(p))
    assert result.is_screenshot is True
    assert result.confidence > 0.0
  
def test_screenshot_noisy_photo_not_flagged(tmp_path):
    p = make_image(tmp_path / "photo.jpg", noise=25.0)
    result = asyncio.run(auth._detect_screenshot(p))
    assert result.is_screenshot is False

def test_screenshot_missing_file_returns_default(tmp_path):
    result = asyncio.run(auth._detect_screenshot(str(tmp_path / "missing.jpg")))
    assert result.is_screenshot is False
    assert result.confidence == 0.0
# ── Noise consistency ──────────────────────────────────────────────────────────
def test_noise_consistency_uniform_noise_is_consistent(tmp_path, monkeypatch):
    monkeypatch.setattr(auth.settings, "NOISE_PATCH_GRID", 4)
    monkeypatch.setattr(auth.settings, "NOISE_INCONSISTENCY_RATIO", 3.0)
    p = make_image(tmp_path / "uniform_noise.jpg", size=(800, 600), noise=15.0)
    result = asyncio.run(auth._check_noise_consistency(p))
    assert 0.0 <= result.consistency_score <= 1.0
    assert len(result.region_variances) == 16

def test_noise_consistency_too_small_image_returns_perfect_score(tmp_path, monkeypatch):
    monkeypatch.setattr(auth.settings, "NOISE_PATCH_GRID", 8)
    img = np.full((20, 20, 3), 128, dtype=np.uint8)
    p = str(tmp_path / "tiny.jpg")
    cv2.imwrite(p, img)
    result = asyncio.run(auth._check_noise_consistency(p))
    assert result.consistency_score == 1.0
    assert result.region_variances == []

def test_noise_consistency_missing_file(tmp_path):
    result = asyncio.run(auth._check_noise_consistency(str(tmp_path / "missing.jpg")))
    assert result.consistency_score == 0.0
# ── Copy-move detection ─────────────────────────────────────────────────────────
def test_copy_move_detects_pasted_block(tmp_path, monkeypatch):
    monkeypatch.setattr(auth.settings, "COPY_MOVE_BLOCK_SIZE", 32)
    monkeypatch.setattr(auth.settings, "COPY_MOVE_MATCH_THRESHOLD", 1)

    rng = np.random.default_rng(42)
    img = rng.integers(0, 255, (320, 320), dtype=np.uint8)
    # Paste a distant block copy far from its source (not trivially adjacent).
    img[0:32, 0:32] = img[288:320, 288:320]
    p = str(tmp_path / "cloned.jpg")
    cv2.imwrite(p, img)

    result = asyncio.run(auth._detect_copy_move(p))
    assert result.matched_blocks >= 1
    assert result.copy_move_score > 0.0

def test_copy_move_missing_file(tmp_path):
    result = asyncio.run(auth._detect_copy_move(str(tmp_path / "missing.jpg")))
    assert result.matched_blocks == 0
    assert result.copy_move_score == 0.0

def test_copy_move_too_small_image(tmp_path, monkeypatch):
    monkeypatch.setattr(auth.settings, "COPY_MOVE_BLOCK_SIZE", 64)
    img = np.full((32, 32), 100, dtype=np.uint8)
    p = str(tmp_path / "small.jpg")
    cv2.imwrite(p, img)
    result = asyncio.run(auth._detect_copy_move(p))
    assert result.matched_blocks == 0
# ── Score fusion ────────────────────────────────────────────────────────────────
def test_score_fusion_all_clean_signals_yields_high_score(monkeypatch):
    monkeypatch.setattr(auth.settings, "ELA_ANOMALY_STD_THRESHOLD", 10.0)
    monkeypatch.setattr(auth.settings, "COPY_MOVE_MATCH_THRESHOLD", 5)

    ela = auth.ELAResult(error_map_mean=1.0, error_map_std=1.0, ela_score=0.02)
    exif = auth.ExifResult(has_exif=True, exif_score=1.0)
    screenshot = auth.ScreenshotResult(is_screenshot=False, confidence=0.0)
    noise = auth.NoiseConsistencyResult(consistency_score=0.95)
    copy_move = auth.CopyMoveResult(matched_blocks=0, copy_move_score=0.0)

    score, flags = auth._calculate_authenticity_score(ela, exif, screenshot, noise, copy_move)
    assert score > 0.9
    assert flags == []

def test_score_fusion_flags_every_signal(monkeypatch):
    monkeypatch.setattr(auth.settings, "ELA_ANOMALY_STD_THRESHOLD", 1.0)
    monkeypatch.setattr(auth.settings, "COPY_MOVE_MATCH_THRESHOLD", 1)

    ela = auth.ELAResult(error_map_mean=50.0, error_map_std=40.0, ela_score=0.9)
    exif = auth.ExifResult(has_exif=False, exif_score=0.0)
    screenshot = auth.ScreenshotResult(is_screenshot=True, confidence=0.9)
    noise = auth.NoiseConsistencyResult(consistency_score=0.2)
    copy_move = auth.CopyMoveResult(matched_blocks=5, copy_move_score=0.8)

    score, flags = auth._calculate_authenticity_score(ela, exif, screenshot, noise, copy_move)
    assert score < 0.5
    assert set(flags) == {
        auth.AuthenticityFlag.ELA_ANOMALY,
        auth.AuthenticityFlag.EXIF_MISSING,
        auth.AuthenticityFlag.SCREENSHOT_DETECTED,
        auth.AuthenticityFlag.NOISE_INCONSISTENT,
        auth.AuthenticityFlag.COPY_MOVE_DETECTED,
    }
# ── Stage entrypoint ────────────────────────────────────────────────────────────
def test_stage_fails_when_quality_check_not_passed(tmp_path):
    p = make_image(tmp_path / "a.jpg")
    state = make_ready_state([p], quality_passed=False)
    result = asyncio.run(auth.run_authenticity_stage(state))
    assert result.status == "failed"
    assert "quality_check" in (result.error or "")

def test_stage_fails_with_no_images():
    state = make_ready_state([], quality_passed=True)
    result = asyncio.run(auth.run_authenticity_stage(state))
    assert result.status == "failed"
    assert "No images" in (result.error or "")

def test_stage_passes_when_score_above_flag_threshold(tmp_path, monkeypatch):
    monkeypatch.setattr(auth.settings, "AUTHENTICITY_FLAG_THRESHOLD", 0.6)
    monkeypatch.setattr(auth.settings, "AUTHENTICITY_HARD_BLOCK_THRESHOLD", 0.3)

    async def fake_analyze(insp_id, path):
        return _fake_result(0.95, insp_id)

    monkeypatch.setattr(auth, "_analyze_image", fake_analyze)

    p = make_image(tmp_path / "a.jpg")
    state = make_ready_state([p])
    result = asyncio.run(auth.run_authenticity_stage(state))

    assert result.status == "passed"
    assert result.error is None
    assert state.memory.authenticity_score == pytest.approx(0.95)
    assert state.memory.authenticity_flagged is False

def test_stage_flags_when_score_between_thresholds(tmp_path, monkeypatch):
    monkeypatch.setattr(auth.settings, "AUTHENTICITY_FLAG_THRESHOLD", 0.6)
    monkeypatch.setattr(auth.settings, "AUTHENTICITY_HARD_BLOCK_THRESHOLD", 0.3)

    async def fake_analyze(insp_id, path):
        return _fake_result(0.45, insp_id)

    monkeypatch.setattr(auth, "_analyze_image", fake_analyze)

    p = make_image(tmp_path / "a.jpg")
    state = make_ready_state([p])
    result = asyncio.run(auth.run_authenticity_stage(state))

    assert result.status == "flagged"
    assert state.memory.authenticity_flagged is True
    # flagged never hard-blocks the pipeline
    assert result.error is None

def test_stage_hard_blocks_when_score_below_hard_block_threshold(tmp_path, monkeypatch):
    monkeypatch.setattr(auth.settings, "AUTHENTICITY_FLAG_THRESHOLD", 0.6)
    monkeypatch.setattr(auth.settings, "AUTHENTICITY_HARD_BLOCK_THRESHOLD", 0.3)

    async def fake_analyze(insp_id, path):
        return _fake_result(0.1, insp_id)

    monkeypatch.setattr(auth, "_analyze_image", fake_analyze)

    p = make_image(tmp_path / "a.jpg")
    state = make_ready_state([p])
    result = asyncio.run(auth.run_authenticity_stage(state))

    assert result.status == "failed"
    assert "hard-block" in (result.error or "").lower()
    assert state.memory.authenticity_flagged is True

def test_stage_fails_when_analyze_image_raises(tmp_path, monkeypatch):
    async def _boom(insp_id, path):
        raise RuntimeError("cv2 exploded")

    monkeypatch.setattr(auth, "_analyze_image", _boom)
    p = make_image(tmp_path / "a.jpg")
    state = make_ready_state([p])
    result = asyncio.run(auth.run_authenticity_stage(state))

    assert result.status == "failed"
    assert "Authenticity analysis failed" in (result.error or "")

def test_stage_averages_score_across_multiple_images(tmp_path, monkeypatch):
    monkeypatch.setattr(auth.settings, "AUTHENTICITY_FLAG_THRESHOLD", 0.6)
    monkeypatch.setattr(auth.settings, "AUTHENTICITY_HARD_BLOCK_THRESHOLD", 0.3)

    scores = iter([0.9, 0.7])

    async def fake_analyze(insp_id, path):
        return _fake_result(next(scores), insp_id)

    monkeypatch.setattr(auth, "_analyze_image", fake_analyze)

    a = make_image(tmp_path / "a.jpg")
    b = make_image(tmp_path / "b.jpg", brightness=90)
    state = make_ready_state([a, b])
    result = asyncio.run(auth.run_authenticity_stage(state))

    assert result.status == "passed"
    assert state.memory.authenticity_score == pytest.approx(0.8)
    assert len(result.data["per_image"]) == 2
