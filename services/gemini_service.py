import io
from google import genai
from google.genai import types

from utils.json_utils import extract_json


DETECTION_PROMPT = """
Analyze one column of a scanned examination paper.

Return only a JSON array.

For each question return:

{
  "type": "question",
  "question_number": 1,
  "box_2d": [ymin, xmin, ymax, xmax],
  "confidence": 0.95,
  "question_format": "mcq"
}

For each section header return:

{
  "type": "section_header",
  "subject": "Physics",
  "box_2d": [ymin, xmin, ymax, xmax],
  "confidence": 0.95
}

Allowed question formats:
- mcq
- numerical
- matching
- assertion_reason
- passage
- descriptive
- unknown

Rules:
- Include the full question.
- Include all options.
- Include diagrams, tables, graphs and passages.
- Stop before the next question number.
- Do not return a continuation as a new question.
- Coordinates are normalized from 0 to 1000.
"""


ANSWER_KEY_PROMPT = """
Extract the answer key from this image.

Return only JSON in this format:
{
  "1": "3",
  "2": "1",
  "3": "4"
}
"""


class GeminiService:
    def __init__(self, api_key: str, model_name: str):
        if not api_key:
            raise ValueError("Gemini API key is required.")

        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def _image_bytes(self, image) -> bytes:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    def detect_column_items(self, image, subjects: list[str]) -> list[dict]:
        prompt = DETECTION_PROMPT + (
            f"\nAllowed subjects: {', '.join(subjects)}"
        )

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Part.from_bytes(
                    data=self._image_bytes(image),
                    mime_type="image/png",
                ),
                prompt,
            ],
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )

        result = extract_json(response.text)
        return result if isinstance(result, list) else []

    def extract_answer_key(self, image) -> dict[int, str]:
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Part.from_bytes(
                    data=self._image_bytes(image),
                    mime_type="image/png",
                ),
                ANSWER_KEY_PROMPT,
            ],
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )

        raw = extract_json(response.text)

        try:
            return {
                int(number): str(answer).upper()
                for number, answer in raw.items()
            }
        except (AttributeError, TypeError, ValueError):
            return {}
