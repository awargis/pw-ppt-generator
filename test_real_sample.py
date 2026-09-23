"""Regression test against the supplied PW Milestone JEE Main sample."""

from pathlib import Path

from image.enhancement import enhance
from pipeline.orchestrator import run_pipeline


SAMPLE = Path(__file__).parents[1] / "examples" / "PW_Milestone_Test-01_JEE_Main_sample.pdf"


def test_supplied_pw_sample_detects_exact_75_question_structure():
    regions, report, structure = run_pipeline(
        SAMPLE.read_bytes(),
        "Auto",
        [],
        dpi=120,
        pad_x=10,
        pad_y=6,
        use_ocr=False,
        answers={},
    )

    assert report.exam_type == "JEE Main"
    assert report.expected_questions == 75
    assert len(regions) == 75
    assert sorted(r.number for r in regions) == list(range(1, 76))
    assert report.subject_counts == {
        "Physics": 25,
        "Chemistry": 25,
        "Mathematics": 25,
    }

    # The instruction page contains numbered instructions 1–8. None may become
    # a question crop.
    assert all(region.page_index >= 1 for region in regions)

    assert all(region.image.width > 0 and region.image.height > 0 for region in regions)

    for number in range(1, 76):
        region = next(r for r in regions if r.number == number)
        if number in {21, 22, 23, 24, 25, 46, 47, 48, 49, 50, 71, 72, 73, 74, 75}:
            assert region.question_type == "Integer"
        else:
            assert region.question_type == "MCQ"

    # A representative MCQ crop must be materially taller than its question
    # marker alone, because the options belong to the same image.
    q2 = next(r for r in regions if r.number == 2)
    assert q2.image.height > 250

    # Background removal produces an RGBA image while retaining the source
    # question as raster content.
    cleaned = enhance(q2.image, "Premium Light", transparent_background=True)
    assert cleaned.mode == "RGBA"
    assert cleaned.width > 250
    assert cleaned.height > 250
