import io
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import Literal
from tenacity import retry, stop_after_attempt, wait_exponential

class DetectedBoundingBox(BaseModel):
    type: Literal["question", "section_header"]
    box_2d: list[float] = Field(description="[ymin, xmin, ymax, xmax] normalized 0-1000")
    question_number: int | None = None
    subject: str | None = None
    confidence: float = 0.95
    question_format: str = "unknown"

class PageColumnDetection(BaseModel):
    items: list[DetectedBoundingBox]

DETECTION_PROMPT = """
Analyze one column of a scanned examination paper.
Rules:
- Include the full question, all options, and diagrams.
- Stop before the next question number.
- Coordinates are normalized from 0 to 1000.
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

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def detect_column_items(self, image, subjects: list[str]) -> list[dict]:
        prompt = DETECTION_PROMPT + f"\nAllowed subjects: {', '.join(subjects)}"

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Part.from_bytes(data=self._image_bytes(image), mime_type="image/png"),
                prompt,
            ],
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=PageColumnDetection,
            ),
        )
        
        # Convert Pydantic objects back to the dict format expected by the rest of the app
        return [item.model_dump() for item in response.parsed.items]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def extract_answer_key(self, image) -> dict[int, str]:
        prompt = "Extract the answer key from this image. Return a strict JSON dictionary mapping question number (string) to option character (string)."
        
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[
                types.Part.from_bytes(data=self._image_bytes(image), mime_type="image/png"),
                prompt,
            ],
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )
        import json
        try:
            raw = json.loads(response.text)
            return {int(k): str(v).upper() for k, v in raw.items()}
        except Exception:
            return {}
