# backend/app/utils/image_utils.py
"""
Image utility helpers shared by pipeline stages and services.
(Disha — W2 D2 will extend: crop, resize, ROI conversion functions.)
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger("app.utils.image_utils")

__all__ = ["load_pil_image", "load_pil_image_rgb", "to_numpy_bgr"]


def load_pil_image(path: str) -> Image.Image:
    """
    Load an image as an RGB PIL Image. Raises ValueError if the file is
    unreadable/corrupt — callers decide whether to fail or fall back.
    """
    try:
        img = Image.open(Path(path))
        img.load()
    except Exception as exc:
        raise ValueError(f"Cannot open image '{path}': {exc}") from exc
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def load_pil_image_rgb(path: str) -> Image.Image:
    """Alias kept for readability at call sites."""
    return load_pil_image(path)


def to_numpy_bgr(pil_img: Image.Image) -> np.ndarray:
    """Convert a PIL RGB image to an OpenCV-style BGR ndarray."""
    rgb = np.asarray(pil_img, dtype=np.uint8)
    return rgb[:, :, ::-1].copy()
