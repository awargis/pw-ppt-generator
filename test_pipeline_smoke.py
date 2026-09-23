import fitz

from config import get_subjects
from pipeline.orchestrator import run_pipeline


def synthetic_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((50, 80), "1. If f(x)=x^2, find f(2).")
    page.insert_text((50, 130), "The graph is shown below. Find the slope and explain your answer.")
    page.insert_text((50, 190), "2. Find the velocity of a body moving with constant speed.")
    page.insert_text((320, 80), "3. Which compound is an alkane?")
    page.insert_text((320, 140), "4. Find the value of 2+3.")
    data = document.tobytes()
    document.close()
    return data


def single_column_pdf() -> bytes:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((50, 80), "1. First question with multiple lines.")
    page.insert_text((50, 120), "This is continuation text and must remain inside Q1.")
    page.insert_text((50, 180), "2. Second question starts here.")
    data = document.tobytes()
    document.close()
    return data


def test_pipeline_smoke_detects_questions_and_assigns_subjects():
    regions, report, structure = run_pipeline(
        synthetic_pdf(), "JEE Main", get_subjects("JEE Main"),
        dpi=120, pad_x=8, pad_y=6, use_ocr=False,
    )
    assert len(regions) == 4
    assert report.pages == 1
    assert all(region.image is not None for region in regions)
    assert all(region.image.width > 0 and region.image.height > 0 for region in regions)
    assert {region.subject for region in regions} <= set(get_subjects("JEE Main"))


def test_single_column_questions_use_full_page_width():
    regions, _, _ = run_pipeline(
        single_column_pdf(), "JEE Main", get_subjects("JEE Main"),
        dpi=120, pad_x=8, pad_y=6, use_ocr=False,
    )
    assert len(regions) == 2
    assert regions[0].box.width > regions[0].image.width - 2
    assert regions[0].box.width > 500
    assert "multiple lines" in regions[0].ocr_text


def test_jee_advanced_does_not_use_jee_main_number_ranges():
    from models import BoundingBox, QuestionRegion
    from pipeline.subject_classifier import classify_subjects

    regions = [QuestionRegion(1, 0, 0, BoundingBox(0, 0, 100, 100))]
    classify_subjects(regions, [], get_subjects("JEE Main"), "JEE Advanced")
    assert regions[0].subject == "Unclassified"
