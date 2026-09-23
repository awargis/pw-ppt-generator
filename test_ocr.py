import fitz
from PIL import Image, ImageDraw, ImageFont

from pipeline.ocr_engine import ocr_blocks


def test_ocr_engine_returns_line_blocks():
    image = Image.new("RGB", (900, 250), "white")
    draw = ImageDraw.Draw(image)
    draw.text((30, 80), "1. Find the value of x + 2 = 5", fill="black")
    blocks = ocr_blocks(image, 0)
    assert blocks
    assert any("Find" in block.text or "value" in block.text for block in blocks)
    assert all(block.source == "ocr" for block in blocks)
