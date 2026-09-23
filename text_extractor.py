"""Native PDF text extraction with pixel-accurate coordinates."""

from models import BoundingBox, TextBlock


def _clean(text: str) -> str:
    return " ".join(str(text).replace("\u00a0", " ").split())


def extract_native_blocks(page, page_index: int, scale: float) -> list[TextBlock]:
    """Extract line-level selectable text from PyMuPDF.

    Line-level geometry is intentionally used instead of coarse PDF blocks. It
    gives the question segmenter a reliable y-coordinate for every question
    start, while preserving the original page coordinate system.
    """
    if scale <= 0:
        raise ValueError("scale must be positive")

    blocks: list[TextBlock] = []
    page_dict = page.get_text("dict", sort=True)
    for raw_block in page_dict.get("blocks", []):
        if raw_block.get("type", 0) != 0:
            continue
        for line in raw_block.get("lines", []):
            spans = line.get("spans", [])
            text = _clean(" ".join(span.get("text", "") for span in spans))
            if not text:
                continue
            bbox = line.get("bbox") or raw_block.get("bbox")
            if not bbox:
                continue
            x0, y0, x1, y1 = (int(round(float(v) * scale)) for v in bbox)
            confidence = 1.0
            blocks.append(
                TextBlock(
                    text=text,
                    box=BoundingBox(x0, y0, x1, y1),
                    confidence=confidence,
                    page_index=page_index,
                    source="native",
                )
            )
    return blocks


def detect_columns(blocks: list[TextBlock], width: int) -> list[TextBlock]:
    """Assign stable column indices without mistaking centered titles for columns."""
    if width <= 0 or not blocks:
        return blocks

    for block in blocks:
        if block.box.width >= width * 0.70:
            block.column_index = -1  # full-width content

    candidates = [b for b in blocks if b.column_index != -1]
    if not candidates:
        return blocks

    midpoint = width / 2
    left = [b for b in candidates if b.box.center_x < midpoint]
    right = [b for b in candidates if b.box.center_x >= midpoint]
    min_width = width * 0.16
    genuine = bool(left and right) and min(
        max((b.box.width for b in left), default=0),
        max((b.box.width for b in right), default=0),
    ) >= min_width

    for block in candidates:
        block.column_index = 0 if not genuine else (0 if block.box.center_x < midpoint else 1)

    return blocks
