import re


SUBJECT_ALIASES = {
    "physics": "Physics",
    "phy": "Physics",
    "chemistry": "Chemistry",
    "chem": "Chemistry",
    "mathematics": "Mathematics",
    "math": "Mathematics",
    "maths": "Mathematics",
    "botany": "Botany",
    "zoology": "Zoology",
}


def normalize_subject(
    value: str | None,
    known_subjects: list[str],
) -> str | None:
    if not value:
        return None

    value = str(value).lower()
    value = value.replace("section", " ")
    value = re.sub(r"[^a-z\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()

    if value in SUBJECT_ALIASES:
        candidate = SUBJECT_ALIASES[value]
        return candidate if candidate in known_subjects else None

    for subject in known_subjects:
        normalized = subject.lower()

        if normalized in value or value in normalized:
            return subject

    return None


def assign_subjects(
    questions,
    headers,
    known_subjects: list[str],
):
    questions = sorted(questions, key=lambda item: item.sort_key)
    headers = sorted(headers, key=lambda item: item.sort_key)

    current_subject = None
    header_index = 0

    for question in questions:
        while (
            header_index < len(headers)
            and headers[header_index].sort_key <= question.sort_key
        ):
            current_subject = normalize_subject(
                headers[header_index].subject,
                known_subjects,
            )
            header_index += 1

        question.subject = current_subject

    return questions
