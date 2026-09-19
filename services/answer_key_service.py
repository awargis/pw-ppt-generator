import re

def parse_answer_key_text(text: str) -> dict[int, str]:
    answer_key = {}
    for q_num, ans in re.findall(r"(\d{1,3})\s*[\.\):\-]+\s*\(?([1-4A-Da-d]+)\)?", text or ""):
        answer_key[int(q_num)] = ans.upper()
    return answer_key
