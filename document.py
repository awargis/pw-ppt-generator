from dataclasses import dataclass, field
from typing import Optional

from PIL import Image


@dataclass(frozen=True)
class BoundingBox:
    """Pixel-space bounding box: left, top, right, bottom."""

    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int:
        return max(0, self.x1 - self.x0)

    @property
    def height(self) -> int:
        return max(0, self.y1 - self.y0)

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2

    def clamp(self, width: int, height: int) -> "BoundingBox":
        x0 = max(0, min(self.x0, width))
        y0 = max(0, min(self.y0, height))
        x1 = max(x0, min(self.x1, width))
        y1 = max(y0, min(self.y1, height))
        return BoundingBox(x0, y0, x1, y1)


@dataclass
class TextBlock:
    """A line/block of text with coordinates in rendered-image pixels."""

    text: str
    box: BoundingBox
    confidence: float = 1.0
    page_index: int = 0
    column_index: int = 0
    block_type: str = "text"
    source: str = "native"


@dataclass
class PageInfo:
    """Stable metadata for one source PDF page."""

    page_index: int
    width: int
    height: int
    pdf_width: float
    pdf_height: float
    rotation: int = 0
    dpi: int = 240
    extraction_method: str = "native"
    native_text_chars: int = 0
    text_blocks: int = 0
    column_count: int = 1


@dataclass
class Document:
    pages: list[Image.Image] = field(default_factory=list)
    page_info: list[PageInfo] = field(default_factory=list)
    questions: list["Question"] = field(default_factory=list)
    headers: list[TextBlock] = field(default_factory=list)


try:
    from .question import QuestionRegion as Question
except ImportError:  # pragma: no cover
    Question = object
