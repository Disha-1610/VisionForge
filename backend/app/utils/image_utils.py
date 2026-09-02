# backend/app/utils/image_utils.py
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import cv2
import numpy as np
from PIL import Image, UnidentifiedImageError

ImageSource = Union[str, Path, bytes, Image.Image, np.ndarray]
ImageFormat = str  # "JPEG" | "PNG"


class ImageProcessingError(Exception):
    pass


class InvalidImageSourceError(ImageProcessingError):
    pass


class ImageValidationError(ImageProcessingError):
    pass


class BoundingBoxError(ImageProcessingError):
    pass


@dataclass(frozen=True)
class BoundingBox:
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class NormalizedBoundingBox:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class ImageSize:
    width: int
    height: int


@dataclass(frozen=True)
class ResizeResult:
    image: Image.Image
    original_size: ImageSize
    resized_size: ImageSize
    scale: float


@dataclass(frozen=True)
class ImageConversionResult:
    image: Image.Image
    source_mode: str
    target_mode: str


@dataclass(frozen=True)
class ImageMetadata:
    width: int
    height: int
    mode: str
    format: str | None


@dataclass(frozen=True)
class CropResult:
    image: Image.Image
    bounding_box: BoundingBox
    source_size: ImageSize


@dataclass(frozen=True)
class ImagePair:
    golden: Image.Image
    inspection: Image.Image


VALID_FORMATS = {"JPEG", "PNG"}
VALID_MODES = {"1", "L", "LA", "P", "RGB", "RGBA", "CMYK"}


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------

def load_pil_image(source: ImageSource) -> Image.Image:
    try:
        if isinstance(source, Image.Image):
            return source.copy()
        if isinstance(source, np.ndarray):
            return cv_to_pil(source)
        if isinstance(source, bytes):
            img = Image.open(io.BytesIO(source))
            img.load()
            return img
        if isinstance(source, (str, Path)):
            path = Path(source)
            if not path.exists():
                raise InvalidImageSourceError(f"Image path does not exist: {path}")
            img = Image.open(path)
            img.load()
            return img
        raise InvalidImageSourceError(f"Unsupported image source type: {type(source)}")
    except UnidentifiedImageError as exc:
        raise InvalidImageSourceError(f"Cannot identify image data: {exc}") from exc
    except (OSError, ValueError) as exc:
        raise InvalidImageSourceError(f"Failed to load image: {exc}") from exc


def load_cv_image(source: ImageSource) -> np.ndarray:
    try:
        if isinstance(source, np.ndarray):
            return source.copy()
        if isinstance(source, Image.Image):
            return pil_to_cv(source)
        if isinstance(source, bytes):
            arr = np.frombuffer(source, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_UNCHANGED)
            if img is None:
                raise InvalidImageSourceError("Failed to decode image bytes with OpenCV")
            return img
        if isinstance(source, (str, Path)):
            path = Path(source)
            if not path.exists():
                raise InvalidImageSourceError(f"Image path does not exist: {path}")
            img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if img is None:
                raise InvalidImageSourceError(f"OpenCV failed to read image: {path}")
            return img
        raise InvalidImageSourceError(f"Unsupported image source type: {type(source)}")
    except InvalidImageSourceError:
        raise
    except (OSError, ValueError, cv2.error) as exc:
        raise InvalidImageSourceError(f"Failed to load image with OpenCV: {exc}") from exc


# --------------------------------------------------------------------------
# Metadata / Validation
# --------------------------------------------------------------------------

def get_image_size(image: Image.Image | np.ndarray) -> ImageSize:
    if isinstance(image, Image.Image):
        w, h = image.size
        return ImageSize(width=w, height=h)
    if isinstance(image, np.ndarray):
        if image.ndim < 2:
            raise ImageValidationError("Invalid ndarray: expected at least 2 dimensions")
        h, w = image.shape[:2]
        return ImageSize(width=w, height=h)
    raise ImageValidationError(f"Unsupported image type: {type(image)}")


def get_image_metadata(image: Image.Image) -> ImageMetadata:
    if not isinstance(image, Image.Image):
        raise ImageValidationError("get_image_metadata requires a PIL Image")
    w, h = image.size
    return ImageMetadata(width=w, height=h, mode=image.mode, format=image.format)


def validate_image_dimensions(
    image: Image.Image | np.ndarray,
    min_width: int,
    min_height: int,
) -> None:
    if min_width < 0 or min_height < 0:
        raise ImageValidationError("min_width and min_height must be non-negative")
    size = get_image_size(image)
    if size.width < min_width or size.height < min_height:
        raise ImageValidationError(
            f"Image dimensions {size.width}x{size.height} below minimum "
            f"{min_width}x{min_height}"
        )


# --------------------------------------------------------------------------
# Format / Color Conversion
# --------------------------------------------------------------------------

def convert_to_rgb(image: Image.Image) -> ImageConversionResult:
    if not isinstance(image, Image.Image):
        raise ImageValidationError("convert_to_rgb requires a PIL Image")
    source_mode = image.mode
    if source_mode == "RGB":
        converted = image.copy()
    else:
        try:
            converted = image.convert("RGB")
        except (OSError, ValueError) as exc:
            raise ImageProcessingError(f"Failed to convert image to RGB: {exc}") from exc
    return ImageConversionResult(image=converted, source_mode=source_mode, target_mode="RGB")


def convert_to_grayscale(image: Image.Image) -> ImageConversionResult:
    if not isinstance(image, Image.Image):
        raise ImageValidationError("convert_to_grayscale requires a PIL Image")
    source_mode = image.mode
    if source_mode == "L":
        converted = image.copy()
    else:
        try:
            converted = image.convert("L")
        except (OSError, ValueError) as exc:
            raise ImageProcessingError(f"Failed to convert image to grayscale: {exc}") from exc
    return ImageConversionResult(image=converted, source_mode=source_mode, target_mode="L")


def pil_to_cv(image: Image.Image) -> np.ndarray:
    if not isinstance(image, Image.Image):
        raise ImageValidationError("pil_to_cv requires a PIL Image")
    try:
        mode = image.mode
        if mode == "RGB":
            arr = np.array(image)
            return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        if mode == "RGBA":
            arr = np.array(image)
            return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGRA)
        if mode == "L":
            return np.array(image)
        rgb = image.convert("RGB")
        arr = np.array(rgb)
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    except (ValueError, cv2.error) as exc:
        raise ImageProcessingError(f"Failed to convert PIL image to OpenCV: {exc}") from exc


def cv_to_pil(image: np.ndarray) -> Image.Image:
    if not isinstance(image, np.ndarray):
        raise ImageValidationError("cv_to_pil requires a numpy ndarray")
    try:
        if image.ndim == 2:
            return Image.fromarray(image)
        if image.ndim == 3:
            channels = image.shape[2]
            if channels == 3:
                rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                return Image.fromarray(rgb)
            if channels == 4:
                rgba = cv2.cvtColor(image, cv2.COLOR_BGRA2RGBA)
                return Image.fromarray(rgba)
        raise ImageValidationError(f"Unsupported ndarray shape for conversion: {image.shape}")
    except cv2.error as exc:
        raise ImageProcessingError(f"Failed to convert OpenCV image to PIL: {exc}") from exc


# --------------------------------------------------------------------------
# Resizing
# --------------------------------------------------------------------------

def resize_preserve_aspect_ratio(
    image: Image.Image,
    max_width: int,
    max_height: int,
) -> ResizeResult:
    if not isinstance(image, Image.Image):
        raise ImageValidationError("resize_preserve_aspect_ratio requires a PIL Image")
    if max_width <= 0 or max_height <= 0:
        raise ImageValidationError("max_width and max_height must be positive")

    original_size = get_image_size(image)
    scale = min(max_width / original_size.width, max_height / original_size.height)
    scale = min(scale, 1.0) if scale > 1.0 else scale
    new_width = max(1, round(original_size.width * scale))
    new_height = max(1, round(original_size.height * scale))

    try:
        resized = image.resize((new_width, new_height), Image.LANCZOS)
    except (OSError, ValueError) as exc:
        raise ImageProcessingError(f"Failed to resize image: {exc}") from exc

    return ResizeResult(
        image=resized,
        original_size=original_size,
        resized_size=ImageSize(width=new_width, height=new_height),
        scale=scale,
    )


def resize_to_dimensions(
    image: Image.Image,
    width: int,
    height: int,
) -> ResizeResult:
    if not isinstance(image, Image.Image):
        raise ImageValidationError("resize_to_dimensions requires a PIL Image")
    if width <= 0 or height <= 0:
        raise ImageValidationError("width and height must be positive")

    original_size = get_image_size(image)
    try:
        resized = image.resize((width, height), Image.LANCZOS)
    except (OSError, ValueError) as exc:
        raise ImageProcessingError(f"Failed to resize image: {exc}") from exc

    scale_x = width / original_size.width
    scale_y = height / original_size.height
    scale = (scale_x + scale_y) / 2

    return ResizeResult(
        image=resized,
        original_size=original_size,
        resized_size=ImageSize(width=width, height=height),
        scale=scale,
    )


# --------------------------------------------------------------------------
# ROI / Bounding-Box Operations
# --------------------------------------------------------------------------

def normalize_bounding_box(
    bounding_box: BoundingBox,
    image_size: ImageSize,
) -> NormalizedBoundingBox:
    if image_size.width <= 0 or image_size.height <= 0:
        raise BoundingBoxError("image_size dimensions must be positive")
    validate_bounding_box(bounding_box, image_size)
    return NormalizedBoundingBox(
        x=bounding_box.x / image_size.width,
        y=bounding_box.y / image_size.height,
        width=bounding_box.width / image_size.width,
        height=bounding_box.height / image_size.height,
    )


def denormalize_bounding_box(
    bounding_box: NormalizedBoundingBox,
    image_size: ImageSize,
) -> BoundingBox:
    if image_size.width <= 0 or image_size.height <= 0:
        raise BoundingBoxError("image_size dimensions must be positive")
    for field_name, value in (
        ("x", bounding_box.x),
        ("y", bounding_box.y),
        ("width", bounding_box.width),
        ("height", bounding_box.height),
    ):
        if not (0.0 <= value <= 1.0):
            raise BoundingBoxError(
                f"Normalized bounding box field '{field_name}' out of range [0,1]: {value}"
            )

    denorm = BoundingBox(
        x=round(bounding_box.x * image_size.width),
        y=round(bounding_box.y * image_size.height),
        width=round(bounding_box.width * image_size.width),
        height=round(bounding_box.height * image_size.height),
    )
    validate_bounding_box(denorm, image_size)
    return denorm


def validate_bounding_box(
    bounding_box: BoundingBox,
    image_size: ImageSize,
) -> None:
    if bounding_box.width <= 0 or bounding_box.height <= 0:
        raise BoundingBoxError(
            f"Bounding box width/height must be positive: "
            f"got width={bounding_box.width}, height={bounding_box.height}"
        )
    if bounding_box.x < 0 or bounding_box.y < 0:
        raise BoundingBoxError(
            f"Bounding box x/y must be non-negative: "
            f"got x={bounding_box.x}, y={bounding_box.y}"
        )
    if bounding_box.x + bounding_box.width > image_size.width:
        raise BoundingBoxError(
            f"Bounding box exceeds image width: "
            f"x={bounding_box.x} + width={bounding_box.width} > {image_size.width}"
        )
    if bounding_box.y + bounding_box.height > image_size.height:
        raise BoundingBoxError(
            f"Bounding box exceeds image height: "
            f"y={bounding_box.y} + height={bounding_box.height} > {image_size.height}"
        )


def crop_image(
    image: Image.Image,
    bounding_box: BoundingBox,
) -> CropResult:
    if not isinstance(image, Image.Image):
        raise ImageValidationError("crop_image requires a PIL Image")
    source_size = get_image_size(image)
    validate_bounding_box(bounding_box, source_size)

    try:
        cropped = image.crop(
            (
                bounding_box.x,
                bounding_box.y,
                bounding_box.x + bounding_box.width,
                bounding_box.y + bounding_box.height,
            )
        )
    except (OSError, ValueError) as exc:
        raise ImageProcessingError(f"Failed to crop image: {exc}") from exc

    return CropResult(image=cropped, bounding_box=bounding_box, source_size=source_size)


def crop_normalized_roi(
    image: Image.Image,
    bounding_box: NormalizedBoundingBox,
) -> CropResult:
    if not isinstance(image, Image.Image):
        raise ImageValidationError("crop_normalized_roi requires a PIL Image")
    source_size = get_image_size(image)
    denorm = denormalize_bounding_box(bounding_box, source_size)
    return crop_image(image, denorm)


# --------------------------------------------------------------------------
# Paired Golden / Inspection ROI Processing
# --------------------------------------------------------------------------

def crop_roi_pair(
    golden_image: Image.Image,
    inspection_image: Image.Image,
    bounding_box: BoundingBox,
) -> ImagePair:
    golden_crop = crop_image(golden_image, bounding_box)
    inspection_crop = crop_image(inspection_image, bounding_box)
    return ImagePair(golden=golden_crop.image, inspection=inspection_crop.image)


def crop_normalized_roi_pair(
    golden_image: Image.Image,
    inspection_image: Image.Image,
    bounding_box: NormalizedBoundingBox,
) -> ImagePair:
    golden_crop = crop_normalized_roi(golden_image, bounding_box)
    inspection_crop = crop_normalized_roi(inspection_image, bounding_box)
    return ImagePair(golden=golden_crop.image, inspection=inspection_crop.image)


# --------------------------------------------------------------------------
# Serialization
# --------------------------------------------------------------------------

def image_to_bytes(
    image: Image.Image,
    format: ImageFormat,
    quality: int | None = None,
) -> bytes:
    if not isinstance(image, Image.Image):
        raise ImageValidationError("image_to_bytes requires a PIL Image")
    fmt = format.upper()
    if fmt not in VALID_FORMATS:
        raise ImageValidationError(f"Unsupported format: {format}. Must be one of {VALID_FORMATS}")

    save_image_obj = image
    if fmt == "JPEG" and image.mode in ("RGBA", "P", "LA"):
        save_image_obj = image.convert("RGB")

    buffer = io.BytesIO()
    try:
        save_kwargs: dict = {"format": fmt}
        if quality is not None:
            if not (1 <= quality <= 100):
                raise ImageValidationError("quality must be between 1 and 100")
            save_kwargs["quality"] = quality
        save_image_obj.save(buffer, **save_kwargs)
    except (OSError, ValueError) as exc:
        raise ImageProcessingError(f"Failed to encode image to bytes: {exc}") from exc

    return buffer.getvalue()


def save_image(
    image: Image.Image,
    destination: str,
    format: ImageFormat | None = None,
    quality: int | None = None,
) -> None:
    if not isinstance(image, Image.Image):
        raise ImageValidationError("save_image requires a PIL Image")

    dest_path = Path(destination)
    fmt = format.upper() if format else None
    if fmt is not None and fmt not in VALID_FORMATS:
        raise ImageValidationError(f"Unsupported format: {format}. Must be one of {VALID_FORMATS}")

    save_image_obj = image
    if fmt == "JPEG" and image.mode in ("RGBA", "P", "LA"):
        save_image_obj = image.convert("RGB")

    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        save_kwargs: dict = {}
        if fmt is not None:
            save_kwargs["format"] = fmt
        if quality is not None:
            if not (1 <= quality <= 100):
                raise ImageValidationError("quality must be between 1 and 100")
            save_kwargs["quality"] = quality
        save_image_obj.save(dest_path, **save_kwargs)
    except (OSError, ValueError) as exc:
        raise ImageProcessingError(f"Failed to save image to {dest_path}: {exc}") from exc