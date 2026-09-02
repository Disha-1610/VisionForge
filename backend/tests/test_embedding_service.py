# backend/tests/test_embedding_service.py
"""
Unit tests for embedding_service (W2 D4 + D5 coverage).

Uses a fresh EmbeddingService instance (NOT the global singleton) and
monkeypatched embedding generators — no model downloads, no network.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.services.embedding_service import (
    EmbeddingDimensionMismatch,
    EmbeddingService,
)

DIM = 512


def _unit_vec(seed: int, dim: int = DIM) -> np.ndarray:
    rng = np.random.default_rng(seed)
    vec = rng.normal(size=dim).astype(np.float32)
    return vec / np.linalg.norm(vec)


@pytest.fixture()
def service(monkeypatch):
    """Fresh EmbeddingService with CLIP generation stubbed to deterministic vectors."""
    svc = EmbeddingService()

    def fake_clip(image):
        seed = (image.size[0] * 7 + image.size[1] * 13) % 1000
        return _unit_vec(seed)

    monkeypatch.setattr(svc, "_generate_clip_embedding", fake_clip)
    monkeypatch.setattr(
        svc, "_generate_gemini_embedding",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no gemini in tests")),
    )
    return svc


class _FakeImage:
    """Just enough of a PIL image for the stubbed generator (needs .size)."""

    def __init__(self, w=100, h=100):
        self.size = (w, h)


# ── build + search ────────────────────────────────────────────────────────────

def test_build_and_search_returns_best_match(service):
    embeddings = np.vstack([_unit_vec(1), _unit_vec(2), _unit_vec(3)])
    service.build_index(embeddings, ["golden-a", "golden-b", "golden-c"], provider="clip")

    assert service.index_size == 3
    assert service.provider == "clip"

    results = service.search(_unit_vec(2), k=1)
    assert results[0][0] == "golden-b"
    assert results[0][1] > 0.99  # cosine of a vector with itself


def test_add_to_index_then_search(service):
    service.build_index(np.vstack([_unit_vec(1), _unit_vec(2)]), ["a", "b"], provider="clip")
    service.add_to_index(_unit_vec(3), "c", provider="clip")

    assert service.index_size == 3
    top = service.search(_unit_vec(3), k=1)[0]
    assert top[0] == "c" and top[1] > 0.99


def test_search_on_empty_index_returns_empty(service):
    assert service.search(_unit_vec(1)) == []


# ── dimension guards (W2 D4 — the Gemini/CLIP mismatch bug) ──────────────────

def test_search_with_wrong_dim_raises(service):
    service.build_index(np.vstack([_unit_vec(1)]), ["a"], provider="clip")
    with pytest.raises(EmbeddingDimensionMismatch):
        service.search(_unit_vec(1, dim=3072))


def test_add_with_wrong_dim_raises(service):
    service.build_index(np.vstack([_unit_vec(1)]), ["a"], provider="clip")
    with pytest.raises(EmbeddingDimensionMismatch):
        service.add_to_index(_unit_vec(2, dim=3072), "b")


# ── remove_from_index (golden deletion rule) ─────────────────────────────────

def test_remove_from_index_rebuilds(service):
    service.build_index(
        np.vstack([_unit_vec(1), _unit_vec(2), _unit_vec(3)]),
        ["a", "b", "c"], provider="clip",
    )
    assert service.remove_from_index("b") is True

    assert service.index_size == 2
    remaining = [iid for iid, _ in service.search(_unit_vec(1), k=3)]
    assert "b" not in remaining
    assert set(remaining) == {"a", "c"}


def test_remove_from_index_unknown_id_returns_false(service):
    service.build_index(np.vstack([_unit_vec(1)]), ["a"], provider="clip")
    assert service.remove_from_index("nope") is False
    assert service.index_size == 1


def test_remove_last_vector_empties_index(service):
    service.build_index(np.vstack([_unit_vec(1)]), ["a"], provider="clip")
    assert service.remove_from_index("a") is True
    assert service.index_size == 0
    assert service.search(_unit_vec(1)) == []


# ── save / load roundtrip ─────────────────────────────────────────────────────

def test_save_and_load_roundtrip(service, tmp_path):
    service.build_index(np.vstack([_unit_vec(1), _unit_vec(2)]), ["a", "b"], provider="clip")
    path = tmp_path / "golden.index"
    service.save_index(path)

    fresh = EmbeddingService()
    assert fresh.load_index(path) is True
    assert fresh.provider == "clip"
    assert fresh.index_size == 2
    top = fresh.search(_unit_vec(2), k=1)[0]
    assert top[0] == "b" and top[1] > 0.99


def test_load_missing_index_returns_false(service, tmp_path):
    assert service.load_index(tmp_path / "missing.index") is False


# ── rebuild_index ─────────────────────────────────────────────────────────────

def test_rebuild_index_bulk(service, monkeypatch):
    service.rebuild_index([])  # clears everything
    assert service.index_size == 0

    calls = {"n": 0}

    def fake_gen(image):
        calls["n"] += 1
        return _unit_vec(calls["n"]), "clip"

    import app.utils.image_utils as image_utils
    monkeypatch.setattr(image_utils, "load_pil_image", lambda path: _FakeImage())
    monkeypatch.setattr(service, "generate_embedding_for_index", fake_gen)
    refs = [(f"img_{i}.jpg", f"g{i}") for i in range(1, 4)]
    provider = service.rebuild_index(refs)

    assert provider == "clip"
    assert service.index_size == 3
    assert service.provider == "clip"


# ── generate_embedding_for_index provider selection ──────────────────────────

def test_generate_for_index_clip_provider_stays_clip(service, monkeypatch):
    service.build_index(np.vstack([_unit_vec(1)]), ["a"], provider="clip")
    vec, provider = service.generate_embedding_for_index(_FakeImage(200, 150))
    assert provider == "clip" and vec.shape[0] == DIM


def test_generate_for_index_gemini_index_requires_gemini(service, monkeypatch):
    # Gemini-built index: when Gemini fails, must NOT silently fall back to CLIP
    service.build_index(np.ones((1, 3072), dtype=np.float32), ["a"], provider="gemini")

    with pytest.raises(RuntimeError):  # our stubbed gemini generator raises
        service.generate_embedding_for_index(_FakeImage())


def test_generate_for_index_empty_index_falls_to_clip(service):
    # No Gemini key configured in tests -> dual logic lands on CLIP
    vec, provider = service.generate_embedding_for_index(_FakeImage())
    assert provider == "clip" and vec.shape[0] == DIM

