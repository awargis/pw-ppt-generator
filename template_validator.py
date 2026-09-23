import io

from pptx import Presentation


def validate_template(template_bytes: bytes):
    if not template_bytes:
        raise ValueError("The PPT template is empty.")
    try:
        prs = Presentation(io.BytesIO(template_bytes))
    except Exception as exc:
        raise ValueError(f"Unable to open PPTX template: {exc}") from exc
    if not prs.slides:
        raise ValueError("Template must contain at least one slide.")
    if prs.slide_width <= 0 or prs.slide_height <= 0:
        raise ValueError("Template has invalid slide dimensions.")
    return prs
