import re

def parse_answer_key_text(text: str) -> dict[int, str]:
    answer_key = {}
    if not text:
        return answer_key
        
    # Matches formats: "1: A", "1. A", "1-A", "1) A", "1 (A)", "1 A"
    pattern = r"(\d{1,3})\s*[:\.\-\)]*\s*\(?([1-4A-Da-d]+)\)?"
    
    for match in re.finditer(pattern, text):
        q_num, ans = match.groups()
        answer_key[int(q_num)] = ans.upper()
        
    return answer_key
