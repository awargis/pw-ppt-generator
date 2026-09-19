from PIL import Image
import numpy as np
import cv2

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
    """Uses OpenCV Otsu thresholding for perfect high-contrast white text on black background."""
    img_cv = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    
    # Force strict black/white separation to remove paper texture
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    inverted = cv2.bitwise_not(binary)
    return Image.fromarray(inverted)

def validate_crop(image: Image.Image, question_number: int) -> None:
    if image is None:
        raise ValueError(f"Q{question_number}: crop is empty")
    if image.width < 80 or image.height < 40:
        raise ValueError(f"Q{question_number}: crop is too small ({image.width}x{image.height})")
    
    aspect_ratio = image.width / image.height
    if aspect_ratio > 12 or aspect_ratio < 0.08:
        raise ValueError(f"Q{question_number}: suspicious aspect ratio ({image.width}x{image.height})")
