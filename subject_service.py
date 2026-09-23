import re
from typing import Optional

SUBJECT_ALIASES = {
    "physics": "Physics", "phys": "Physics", "phy": "Physics",
    "chemistry": "Chemistry", "chem": "Chemistry",
    "mathematics": "Mathematics", "maths": "Mathematics", "math": "Mathematics",
    "botany": "Botany", "bot": "Botany",
    "zoology": "Zoology", "zoo": "Zoology",
}


def normalize_subject(value: Optional[str], known_subjects: list[str]) -> Optional[str]:
    if not value:
        return None
    text = re.sub(r"[^a-zA-Z ]", " ", str(value)).lower()
    for token in text.split():
        subject = SUBJECT_ALIASES.get(token)
        if subject in known_subjects:
            return subject
    for subject in known_subjects:
        if subject.lower() in text:
            return subject
    return None


def assign_subject(q_num: int, exam_type: str, headers: list, q_page: int, q_col: int, q_y0: float) -> str:
    # Number ranges are a useful fallback, never the only mechanism.
    if exam_type == "JEE Main":
        ranges = [(1, 25, "Physics"), (26, 50, "Chemistry"), (51, 75, "Mathematics")]
    elif exam_type == "NEET UG":
        ranges = [(1, 45, "Physics"), (46, 90, "Chemistry"), (91, 135, "Botany"), (136, 180, "Zoology")]
    else:
        ranges = []
    for start, end, subject in ranges:
        if start <= q_num <= end:
            return subject

    current = "Unclassified"
    for header in sorted(headers, key=lambda h: (h["page"], h["col"], h["y0"])):
        before = (header["page"], header["col"], header["y0"]) <= (q_page, q_col, q_y0)
        if before:
            current = header["subject"] or current
    return current
