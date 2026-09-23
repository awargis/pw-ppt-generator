from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.util import Inches


def _usable_area(prs):
    return Inches(0.55), Inches(1.05), prs.slide_width - Inches(1.10), prs.slide_height - Inches(1.45)


def fit_box(prs, image, margin=0.0):
    left, top, width, height = _usable_area(prs)
    scale = min(float(width) / max(1, image.width), float(height) / max(1, image.height))
    w, h = int(image.width * scale), int(image.height * scale)
    return int(left) + (int(width) - w) // 2, int(top) + (int(height) - h) // 2, w, h


def find_image_placeholder(slide):
    """Find a picture/content placeholder or a named #QUESTION_IMAGE shape."""
    for shape in slide.shapes:
        name = (shape.name or "").upper()
        if "QUESTION_IMAGE" in name or "QUESTION IMAGE" in name:
            return shape
        if getattr(shape, "is_placeholder", False):
            try:
                if shape.placeholder_format.type in (18, 7):  # picture/content
                    return shape
            except Exception:
                pass
    return None
