from dataclasses import dataclass
from PIL import Image
from typing import Optional

@dataclass
class BoundingBox:
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def width(self) -> int: return max(0, self.x1 - self.x0)
    
    @property
    def height(self) -> int: return max(0, self.y1 - self.y0)

@dataclass
class DetectedItem:
    kind: str
    page_index: int
    column_index: int
    box: BoundingBox
    question_number: Optional[int] = None
    subject: Optional[str] = None
    confidence: float = 0.0

    @property
    def sort_key(self):
        # Enforces chronological sorting: Page -> Column (Left=0, Right=1) -> Y-Position (Top to Bottom)
        return (self.page_index, self.column_index, self.box.y0)
