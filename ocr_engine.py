from collections import defaultdict
import os

from PIL import Image
import pytesseract
from pytesseract import Output

if os.getenv("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]

from models import BoundingBox, TextBlock


def ocr_blocks(image: Image.Image, page_index: int) -> list[TextBlock]:
    """Run local Tesseract and return line-level pixel coordinates."""
    data = pytesseract.image_to_data(
        image.convert("RGB"),
        config="--oem 3 --psm 3",
        output_type=Output.DICT,
    )
    lines = defaultdict(list)
    total = len(data.get("text", []))
    for i in range(total):
        value = (data["text"][i] or "").strip()
        try:
            confidence = float(data["conf"][i])
        except (TypeError, ValueError):
            confidence = -1
        if value and confidence >= 0:
            key = (
                data["block_num"][i],
                data["par_num"][i],
                data["line_num"][i],
            )
            lines[key].append(i)

    result: list[TextBlock] = []
    for indexes in lines.values():
        text = " ".join(data["text"][i].strip() for i in indexes if data["text"][i].strip())
        if not text:
            continue
        x0 = min(int(data["left"][i]) for i in indexes)
        y0 = min(int(data["top"][i]) for i in indexes)
        x1 = max(int(data["left"][i]) + int(data["width"][i]) for i in indexes)
        y1 = max(int(data["top"][i]) + int(data["height"][i]) for i in indexes)
        conf_values = []
        for i in indexes:
            try:
                value = float(data["conf"][i])
            except (TypeError, ValueError):
                value = -1
            if value >= 0:
                conf_values.append(value)
        confidence = (sum(conf_values) / len(conf_values) / 100) if conf_values else 0.0
        result.append(
            TextBlock(
                text=text,
                box=BoundingBox(x0, y0, x1, y1),
                confidence=max(0.0, min(1.0, confidence)),
                page_index=page_index,
                source="ocr",
            )
        )
    return result
