from dataclasses import dataclass, field


@dataclass
class ProcessingReport:
    pages: int = 0
    questions: int = 0
    subject_counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    low_confidence: list[int] = field(default_factory=list)
    missing_answers: list[int] = field(default_factory=list)
    exam_type: str = "Unknown"
    exam_confidence: float = 0.0
    expected_questions: int = 0
    detected_questions: int = 0
