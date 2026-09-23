from dataclasses import dataclass


JEE_SUBJECTS = ["Physics", "Chemistry", "Mathematics"]
NEET_SUBJECTS = ["Physics", "Chemistry", "Botany", "Zoology"]
EXAMS = ["JEE Main", "JEE Advanced", "NEET UG"]
STYLES = ["Premium Light", "Premium Dark", "High Contrast"]


@dataclass(frozen=True)
class AppConfig:
    dpi: int = 240
    pad_x: int = 24
    pad_y: int = 14
    min_question_height: int = 40
    ocr_enabled: bool = True
    style: str = "Premium Light"


def get_subjects(exam_type: str) -> list[str]:
    if exam_type == "NEET UG":
        return NEET_SUBJECTS.copy()
    return JEE_SUBJECTS.copy()
