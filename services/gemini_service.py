import io
import json
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

class PageColumnDetection(BaseModel):
    items: list[DetectedBoundingBox]

class GeminiService:
    def __init__(self, api_key: str, model_name: str):
        if not api_key: raise ValueError("Gemini API key is required.")
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def _image_bytes(self, image) -> bytes:
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def detect_column_items(self, image, subjects: list[str]) -> list[dict]:
        prompt = f"Analyze column. Extract questions and headers. Allowed subjects: {', '.join(subjects)}. Coordinates 0-1000."
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[types.Part.from_bytes(data=self._image_bytes(image), mime_type="image/png"), prompt],
            config=types.GenerateContentConfig(
                temperature=0, response_mime_type="application/json", response_schema=PageColumnDetection
            ),
        )
        return [item.model_dump() for item in response.parsed.items]
