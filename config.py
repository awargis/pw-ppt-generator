Keep all application settings in one place.

```python
from dataclasses import dataclass, field
import os


@dataclass
class AppConfig:
    render_dpi: int = 300
    crop_padding: int = 18
    column_gap_percent: float = 1.5
    outer_margin_percent: float = 1.2
    invert_images: bool = False
    minimum_crop_width: int = 80
    minimum_crop_height: int = 40
    output_directory: str = "output_processing"

    @property
    def poppler_path(self) -> str | None:
        return os.getenv("POPPLER_PATH") or None


MODEL_CHOICES = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
]

JEE_SUBJECTS = [
    "Physics",
    "Chemistry",
    "Mathematics",
]

NEET_SUBJECTS = [
    "Physics",
    "Chemistry",
    "Botany",
    "Zoology",
]


def get_subjects(exam_type: str) -> list[str]:
    return JEE_SUBJECTS.copy() if "JEE" in exam_type else NEET_SUBJECTS.copy()
```

---

## 2. `models.py`

Put all shared data structures here.

```python
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
        return (
            self.page_index,
            self.column_index,
            self.box.y0,
        )


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
```

