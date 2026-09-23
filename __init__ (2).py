from .document import BoundingBox, Document, PageInfo, TextBlock
from .question import QuestionRegion
from .report import ProcessingReport

Question = QuestionRegion

__all__ = [
    "BoundingBox",
    "Document",
    "PageInfo",
    "TextBlock",
    "Question",
    "QuestionRegion",
    "ProcessingReport",
]
