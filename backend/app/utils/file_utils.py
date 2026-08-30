# backend/app/utils/file_utils.py
"""Safe file-upload handling for inspection and golden-reference images."""
from __future__ import annotations

import os
import uuid

from fastapi import UploadFile

DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MB


def validate_image_extension(filename: str | None, allowed_extensions: set[str]) -> bool:
    """Return True only if the filename has one of the allowed extensions."""
    if not filename:
        return False
    ext = os.path.splitext(filename)[1].lower()
    return ext in {e.lower() for e in allowed_extensions}


def _safe_extension(filename: str | None, fallback: str = ".jpg") -> str:
    """Extract a whitelisted, lowercased extension from the original filename."""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in {".jpg", ".jpeg", ".png"}:
        return fallback
    return ".jpg" if ext == ".jpeg" else ext


async def save_upload_file(upload_file: UploadFile, dest_dir: str) -> str:
    """
    Persist an uploaded image under dest_dir with a randomized, safe filename.
    Never trust the client-supplied filename for the on-disk path.

    Returns the absolute saved path.
    """
    os.makedirs(dest_dir, exist_ok=True)
    ext = _safe_extension(upload_file.filename)
    saved_path = os.path.join(dest_dir, f"{uuid.uuid4().hex}{ext}")

    with open(saved_path, "wb") as out:
        while chunk := await upload_file.read(DEFAULT_CHUNK_SIZE):
            out.write(chunk)

    return saved_path
