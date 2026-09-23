"""Premium question-image cleanup.

The source question is never re-rendered as typed text. The original PDF raster
is retained, then cleaned: whitespace is trimmed, near-white paper is made
transparent, and contrast/sharpness are gently improved.
"""

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter, ImageOps


def remove_white_background(image: Image.Image, white_threshold: int = 248) -> Image.Image:
    rgb = np.array(image.convert("RGB"))
    maxc = rgb.max(axis=2)
    minc = rgb.min(axis=2)
    # Only remove neutral near-white paper. Bright colored diagrams remain.
    neutral = (maxc - minc) <= 8
    white = neutral & (minc >= white_threshold)

    alpha = np.full(rgb.shape[:2], 255, dtype=np.uint8)
    grey = rgb.mean(axis=2)
    # Keep dark mathematical text/lines opaque. Fade only light neutral paper
    # and watermark pixels; this removes the PW-style background without
    # destroying diagrams.
    fade = neutral & (grey >= 95)
    alpha[fade] = np.clip((125 - grey[fade]) * 8.0, 0, 255).astype(np.uint8)
    alpha[white] = 0

    return Image.fromarray(np.dstack([rgb, alpha]), "RGBA")


def enhance(
    image: Image.Image,
    style: str = "Premium Light",
    transparent_background: bool = True,
) -> Image.Image:
    """Create a crisp presentation-ready question crop."""
    result = ImageOps.exif_transpose(image).convert("RGB")
    result = ImageOps.autocontrast(result, cutoff=0.35)
    result = ImageEnhance.Contrast(result).enhance(1.08)
    result = ImageEnhance.Sharpness(result).enhance(1.20)

    if style == "High Contrast":
        result = ImageEnhance.Contrast(result).enhance(1.18)
        result = result.filter(
            ImageFilter.UnsharpMask(radius=1.0, percent=125, threshold=3)
        )
    elif style == "Premium Dark":
        result = ImageEnhance.Contrast(result).enhance(1.04)

    if transparent_background:
        return remove_white_background(result)
    return result
