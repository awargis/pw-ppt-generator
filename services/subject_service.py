import re

def normalize_subject(value: str | None, known_subjects: list[str]) -> str | None:
    if not value: return None
    value = re.sub(r"[^a-z\s]", " ", str(value).lower()).strip()
    for subject in known_subjects:
        if subject.lower() in value: return subject
    return None
