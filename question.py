from dataclasses import dataclass
from typing import Optional

from PIL import Image

from .document import BoundingBox


@dataclass
class QuestionRegion:
    """Canonical domain object representing one detected question."""

    number: int
    page_index: int
    column_index: int
    box: BoundingBox
    image: Optional[Image.Image] = None
    subject: str = "Unclassified"
    answer: Optional[str] = None
    ocr_text: str = ""
    confidence: float = 0.0
    needs_review: bool = False
    extraction_method: str = "native"
    end_page_index: Optional[int] = None
    included: bool = True
    question_type: str = "MCQ"
    source_section: object | None = None

    @property
    def sort_key(self) -> tuple[int, int, int]:
        return (self.page_index, self.column_index, self.box.y0)

    @property
    def question_number(self) -> int:
        """Compatibility alias for older service code."""
        return self.number

    @property
    def page_span(self) -> tuple[int, int]:
        return (self.page_index, self.end_page_index or self.page_index)
