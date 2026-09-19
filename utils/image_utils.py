from PIL import Image
import numpy as np
import cv2

def apply_dark_mode(image: Image.Image) -> Image.Image:
    # Converts standard crop into high-contrast white text on black background
    img_cv = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    
    # Otsu's Binarization removes paper texture completely
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Invert text to white
    inverted = cv2.bitwise_not(binary)
    return Image.fromarray(inverted)

def validate_crop(image: Image.Image, question_number: int) -> None:
    if image is None or image.width < 80 or image.height < 40:
        raise ValueError(f"Q{question_number}: crop is too small or empty.")
