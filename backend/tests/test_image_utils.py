# backend/tests/test_image_utils.py
"""
Unit tests for app.utils.image_utils (W2 D2 & D5 deliverable).

Tests image loading, conversions, resizing, bounding box operations,
paired ROI cropping, and file saving/byte serialization.
"""
from __future__ import annotations

import io
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from app.utils.image_utils import (
    BoundingBox,
    BoundingBoxError,
    ImagePair,
    ImageProcessingError,
    ImageSize,
    ImageValidationError,
    InvalidImageSourceError,
    NormalizedBoundingBox,
    convert_to_grayscale,
    convert_to_rgb,
    crop_image,
    crop_normalized_roi,
    crop_normalized_roi_pair,
    crop_roi_pair,
    cv_to_pil,
    denormalize_bounding_box,
    get_image_metadata,
    get_image_size,
    image_to_bytes,
    load_cv_image,
    load_pil_image,
    normalize_bounding_box,
    pil_to_cv,
    resize_preserve_aspect_ratio,
    resize_to_dimensions,
    save_image,
    validate_bounding_box,
    validate_image_dimensions,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_pil_rgb():
    img = Image.new("RGB", (400, 300), color=(100, 150, 200))
    return img


@pytest.fixture
def sample_cv_bgr():
    arr = np.zeros((300, 400, 3), dtype=np.uint8)
    arr[:] = (200, 150, 100)  # BGR
    return arr


# ── Loading Tests ─────────────────────────────────────────────────────────────

def test_load_pil_image_from_pil(sample_pil_rgb):
    loaded = load_pil_image(sample_pil_rgb)
    assert isinstance(loaded, Image.Image)
    assert loaded.size == (400, 300)
    assert loaded is not sample_pil_rgb  # Must be a copy


def test_load_pil_image_from_cv(sample_cv_bgr):
    loaded = load_pil_image(sample_cv_bgr)
    assert isinstance(loaded, Image.Image)
    assert loaded.size == (400, 300)
    assert loaded.mode == "RGB"


def test_load_pil_image_from_bytes(sample_pil_rgb):
    buf = io.BytesIO()
    sample_pil_rgb.save(buf, format="PNG")
    raw_bytes = buf.getvalue()

    loaded = load_pil_image(raw_bytes)
    assert isinstance(loaded, Image.Image)
    assert loaded.size == (400, 300)


def test_load_pil_image_from_path(tmp_path, sample_pil_rgb):
    path = tmp_path / "test.png"
    sample_pil_rgb.save(path)

    loaded = load_pil_image(str(path))
    assert loaded.size == (400, 300)


def test_load_pil_image_nonexistent_path_raises():
    with pytest.raises(InvalidImageSourceError):
        load_pil_image("nonexistent_path_12345.png")


def test_load_pil_image_invalid_type_raises():
    with pytest.raises(InvalidImageSourceError):
        load_pil_image(12345)  # type: ignore


def test_load_cv_image_from_cv(sample_cv_bgr):
    loaded = load_cv_image(sample_cv_bgr)
    assert isinstance(loaded, np.ndarray)
    assert loaded.shape == (300, 400, 3)
    assert loaded is not sample_cv_bgr


def test_load_cv_image_from_pil(sample_pil_rgb):
    loaded = load_cv_image(sample_pil_rgb)
    assert isinstance(loaded, np.ndarray)
    assert loaded.shape == (300, 400, 3)


def test_load_cv_image_from_path(tmp_path, sample_pil_rgb):
    path = tmp_path / "test_cv.jpg"
    sample_pil_rgb.save(path)

    loaded = load_cv_image(path)
    assert loaded.shape == (300, 400, 3)


def test_load_cv_image_nonexistent_raises():
    with pytest.raises(InvalidImageSourceError):
        load_cv_image(Path("missing_file.jpg"))


# ── Metadata & Dimensions ─────────────────────────────────────────────────────

def test_get_image_size(sample_pil_rgb, sample_cv_bgr):
    size_pil = get_image_size(sample_pil_rgb)
    assert size_pil.width == 400
    assert size_pil.height == 300

    size_cv = get_image_size(sample_cv_bgr)
    assert size_cv.width == 400
    assert size_cv.height == 300


def test_get_image_size_invalid_ndarray():
    with pytest.raises(ImageValidationError):
        get_image_size(np.array([1, 2, 3]))


def test_get_image_metadata(tmp_path, sample_pil_rgb):
    path = tmp_path / "meta.png"
    sample_pil_rgb.save(path)
    loaded = Image.open(path)

    meta = get_image_metadata(loaded)
    assert meta.width == 400
    assert meta.height == 300
    assert meta.mode == "RGB"
    assert meta.format == "PNG"


def test_validate_image_dimensions_passes(sample_pil_rgb):
    validate_image_dimensions(sample_pil_rgb, min_width=200, min_height=200)


def test_validate_image_dimensions_fails(sample_pil_rgb):
    with pytest.raises(ImageValidationError):
        validate_image_dimensions(sample_pil_rgb, min_width=500, min_height=200)

    with pytest.raises(ImageValidationError):
        validate_image_dimensions(sample_pil_rgb, min_width=-1, min_height=100)


# ── Conversions ───────────────────────────────────────────────────────────────

def test_convert_to_rgb_and_grayscale(sample_pil_rgb):
    gray = convert_to_grayscale(sample_pil_rgb)
    assert gray.image.mode == "L"
    assert gray.source_mode == "RGB"
    assert gray.target_mode == "L"

    rgb = convert_to_rgb(gray.image)
    assert rgb.image.mode == "RGB"
    assert rgb.source_mode == "L"


def test_pil_to_cv_and_cv_to_pil(sample_pil_rgb):
    cv_img = pil_to_cv(sample_pil_rgb)
    assert cv_img.shape == (300, 400, 3)

    back_pil = cv_to_pil(cv_img)
    assert back_pil.size == (400, 300)
    assert back_pil.mode == "RGB"


# ── Resizing ──────────────────────────────────────────────────────────────────

def test_resize_preserve_aspect_ratio(sample_pil_rgb):
    # 400x300 resized to max 200x200 should become 200x150
    result = resize_preserve_aspect_ratio(sample_pil_rgb, max_width=200, max_height=200)
    assert result.resized_size.width == 200
    assert result.resized_size.height == 150
    assert result.scale == pytest.approx(0.5)


def test_resize_preserve_aspect_ratio_does_not_upscale(sample_pil_rgb):
    # 400x300 with max 800x800 stays 400x300
    result = resize_preserve_aspect_ratio(sample_pil_rgb, max_width=800, max_height=800)
    assert result.resized_size.width == 400
    assert result.resized_size.height == 300
    assert result.scale == 1.0


def test_resize_to_dimensions(sample_pil_rgb):
    result = resize_to_dimensions(sample_pil_rgb, width=150, height=150)
    assert result.resized_size.width == 150
    assert result.resized_size.height == 150


# ── Bounding Box & Cropping ───────────────────────────────────────────────────

def test_validate_bounding_box_valid():
    bbox = BoundingBox(x=50, y=50, width=100, height=80)
    size = ImageSize(width=400, height=300)
    validate_bounding_box(bbox, size)


def test_validate_bounding_box_out_of_bounds():
    size = ImageSize(width=400, height=300)

    # Exceeding width
    with pytest.raises(BoundingBoxError):
        validate_bounding_box(BoundingBox(x=350, y=50, width=100, height=50), size)

    # Negative coordinates
    with pytest.raises(BoundingBoxError):
        validate_bounding_box(BoundingBox(x=-10, y=50, width=50, height=50), size)

    # Zero size
    with pytest.raises(BoundingBoxError):
        validate_bounding_box(BoundingBox(x=10, y=10, width=0, height=50), size)


def test_normalize_and_denormalize_bounding_box():
    size = ImageSize(width=400, height=200)
    bbox = BoundingBox(x=100, y=50, width=200, height=100)

    norm = normalize_bounding_box(bbox, size)
    assert norm.x == pytest.approx(0.25)
    assert norm.y == pytest.approx(0.25)
    assert norm.width == pytest.approx(0.5)
    assert norm.height == pytest.approx(0.5)

    denorm = denormalize_bounding_box(norm, size)
    assert denorm == bbox


def test_crop_image(sample_pil_rgb):
    bbox = BoundingBox(x=50, y=40, width=100, height=60)
    crop = crop_image(sample_pil_rgb, bbox)
    assert crop.image.size == (100, 60)
    assert crop.bounding_box == bbox


def test_crop_normalized_roi(sample_pil_rgb):
    norm_bbox = NormalizedBoundingBox(x=0.1, y=0.1, width=0.5, height=0.5)
    crop = crop_normalized_roi(sample_pil_rgb, norm_bbox)
    assert crop.image.size == (200, 150)


def test_crop_roi_pair(sample_pil_rgb):
    golden = sample_pil_rgb
    inspection = Image.new("RGB", (400, 300), color=(50, 50, 50))
    bbox = BoundingBox(x=20, y=20, width=80, height=80)

    pair = crop_roi_pair(golden, inspection, bbox)
    assert isinstance(pair, ImagePair)
    assert pair.golden.size == (80, 80)
    assert pair.inspection.size == (80, 80)


def test_crop_normalized_roi_pair(sample_pil_rgb):
    golden = sample_pil_rgb
    inspection = Image.new("RGB", (400, 300), color=(50, 50, 50))
    norm_bbox = NormalizedBoundingBox(x=0.0, y=0.0, width=0.5, height=0.5)

    pair = crop_normalized_roi_pair(golden, inspection, norm_bbox)
    assert pair.golden.size == (200, 150)
    assert pair.inspection.size == (200, 150)


# ── Serialization ─────────────────────────────────────────────────────────────

def test_image_to_bytes_png_and_jpeg(sample_pil_rgb):
    png_bytes = image_to_bytes(sample_pil_rgb, "PNG")
    assert len(png_bytes) > 0
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"

    jpeg_bytes = image_to_bytes(sample_pil_rgb, "JPEG", quality=85)
    assert len(jpeg_bytes) > 0


def test_image_to_bytes_rgba_to_jpeg():
    rgba = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
    jpeg_bytes = image_to_bytes(rgba, "JPEG")
    assert len(jpeg_bytes) > 0


def test_image_to_bytes_invalid_format_raises(sample_pil_rgb):
    with pytest.raises(ImageValidationError):
        image_to_bytes(sample_pil_rgb, "BMP")


def test_save_image(tmp_path, sample_pil_rgb):
    target = tmp_path / "subfolder" / "output.jpg"
    save_image(sample_pil_rgb, str(target), format="JPEG", quality=90)
    assert target.exists()
    assert target.stat().st_size > 0
