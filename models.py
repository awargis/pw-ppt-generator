from dataclasses import dataclass, field
from PIL import Image
from typing import Optional

@dataclass
class BoundingBox:
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
    def is_valid(self) -> bool:
        return self.x1 > self.x0 and self.y1 > self.y0

@dataclass
class DetectedItem:
    kind: str
    page_index: int
    column_index: int
    box: BoundingBox
    question_number: Optional[int] = None
    subject: Optional[str] = None
    confidence: float = 0.0
    question_format: str = "unknown"

    @property
    def sort_key(self):
        return (self.page_index, self.column_index, self.box.y0)

@dataclass
class QuestionCrop:
    number: int
    subject: str
    image: Image.Image
    page_index: int
    confidence: float = 0.0
    question_format: str = "unknown"

@dataclass
class ProcessingReport:
    detected_questions: int = 0
    generated_questions: int = 0
    invalid_crops: list[int] = field(default_factory=list)
    duplicate_questions: list[int] = field(default_factory=list)
    unclassified_questions: list[int] = field(default_factory=list)
    detected_subject_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
