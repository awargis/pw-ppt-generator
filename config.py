import os
from dataclasses import dataclass

@dataclass
class AppConfig:
    render_dpi: int = 300
    column_gap_percent: float = 1.5
    outer_margin_percent: float = 1.2
    minimum_crop_width: int = 80
    minimum_crop_height: int = 40

    @property
    def poppler_path(self) -> str | None:
        return os.getenv("POPPLER_PATH") or None

MODEL_CHOICES = ["gemini-2.5-flash","gemini-3.8-flash","gemini-3.7-flash","gemini-3.6-flash","gemini-3.5-flash", "gemini-2.5-pro"]
JEE_SUBJECTS = ["Physics", "Chemistry", "Mathematics"]
NEET_SUBJECTS = ["Physics", "Chemistry", "Botany", "Zoology"]

def get_subjects(exam_type: str) -> list[str]:
    return JEE_SUBJECTS.copy() if "JEE" in exam_type else NEET_SUBJECTS.copy()
