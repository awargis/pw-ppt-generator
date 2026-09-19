
from PIL import Image, ImageEnhance, ImageOps
import numpy as np

def autotrim(image: Image.Image, padding: int = 18, background_threshold: int = 245) -> Image.Image:
    if image.width < 4 or image.height < 4:
        return image

    grayscale = image.convert("L")
    array = np.asarray(grayscale)
    ink_mask = array < background_threshold
    ys, xs = np.where(ink_mask)

    if len(xs) == 0:
        return image

    x0 = max(0, int(xs.min()) - padding)
    y0 = max(0, int(ys.min()) - padding)
    x1 = min(image.width, int(xs.max()) + padding + 1)
    y1 = min(image.height, int(ys.max()) + padding + 1)

    return image.crop((x0, y0, x1, y1))

def invert_to_black_background(image: Image.Image) -> Image.Image:
    inverted = ImageOps.invert(image.convert("RGB"))
    return ImageEnhance.Contrast(inverted).enhance(1.15)

def validate_crop(image: Image.Image, question_number: int) -> None:
    if image is None:
        raise ValueError(f"Q{question_number}: crop is empty")

    if image.width < 80 or image.height < 40:
        raise ValueError(f"Q{question_number}: crop is too small ({image.width}x{image.height})")

    aspect_ratio = image.width / image.height
    if aspect_ratio > 12 or aspect_ratio < 0.08:
        raise ValueError(f"Q{question_number}: suspicious aspect ratio ({image.width}x{image.height})")

def fit_inside(image_width: int, image_height: int, box_width: int, box_height: int) -> tuple[int, int]:
    if image_width <= 0 or image_height <= 0:
        return 0, 0

    scale = min(box_width / image_width, box_height / image_height)
    return (max(1, int(image_width * scale)), max(1, int(image_height * scale)))
