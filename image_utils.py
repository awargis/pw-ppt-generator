import io
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


def validate_crop(image: Image.Image, question_number: int) -> None:
    if image is None or image.width < 80 or image.height < 40:
        raise ValueError(f"Q{question_number}: crop is too small or empty")


def enhance_question(image: Image.Image, style: str = "Premium Light") -> Image.Image:
    validate_crop(image, 0)
    rgb = np.asarray(image.convert("RGB"))
    # Remove uneven paper illumination without destroying diagrams or formulas.
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(l)
    enhanced = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2RGB)
    enhanced = cv2.detailEnhance(enhanced, sigma_s=10, sigma_r=0.15)
    result = Image.fromarray(enhanced).filter(ImageFilter.SHARPEN)
    result = ImageEnhance.Contrast(result).enhance(1.08)
    if style == "Premium Dark":
        gray = cv2.cvtColor(np.asarray(result), cv2.COLOR_RGB2GRAY)
        mask = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 35, 11)
        # Black canvas with clean white content; retain original anti-aliased edges.
        result = Image.fromarray(255 - mask).convert("RGB")
    elif style == "High Contrast":
        gray = cv2.cvtColor(np.asarray(result), cv2.COLOR_RGB2GRAY)
        result = Image.fromarray(cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)).convert("RGB")
    return result


def apply_dark_mode(image: Image.Image) -> Image.Image:
    return enhance_question(image, "Premium Dark")
