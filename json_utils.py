import json
import re

def extract_json(text: str):
    text = str(text or "").strip()
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    if not text:
        raise ValueError("Empty JSON response")
    return json.loads(text)
