import re


def parse_answer_key_text(text: str) -> dict[int, str]:
    if not text:
        return {}

    answer_key = {}

    pattern = (
        r"(\d{1,3})"
        r"\s*[\.\):\-]+"
        r"\s*\(?"
        r"([1-4A-Da-d]+)"
        r"\)?"
    )

    for question_number, answer in re.findall(pattern, text):
        answer_key[int(question_number)] = answer.upper()

    return answer_key
