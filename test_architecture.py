import importlib
from pathlib import Path


def test_canonical_models_package_is_used():
    models = importlib.import_module("models")
    question = importlib.import_module("models.question")
    assert models.__file__.endswith("models/__init__.py")
    assert question.QuestionRegion is models.QuestionRegion


def test_gemini_and_legacy_duplicate_modules_are_removed():
    forbidden = [
        Path("models.py"),
        Path("core_engine.py"),
        Path("ocr_processor.py"),
        Path("ppt_generator.py"),
        Path("services/gemini_service.py"),
        Path("services/pdf_service.py"),
        Path("services/ppt_service.py"),
        Path("services/extraction_service.py"),
    ]
    assert not any(path.exists() for path in forbidden)


def test_pipeline_modules_import_without_gemini():
    for module in (
        "pipeline.page_analyzer",
        "pipeline.orchestrator",
        "models.question",
        "ppt.exporter",
    ):
        importlib.import_module(module)
