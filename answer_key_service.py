from answer_key.parser import parse


def parse_answer_key_text(text: str) -> dict[int, str]:
    return parse(text)
