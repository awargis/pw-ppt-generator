from models import BoundingBox, QuestionRegion, TextBlock
from pipeline.subject_classifier import classify_subjects


def test_jee_advanced_uses_section_header():
    regions = [QuestionRegion(17, 2, 0, BoundingBox(50, 200, 500, 400))]
    headers = [TextBlock("MATHEMATICS", BoundingBox(50, 100, 300, 130), page_index=2, column_index=0)]
    classify_subjects(regions, headers, ["Physics", "Chemistry", "Mathematics"], "JEE Advanced")
    assert regions[0].subject == "Mathematics"


def test_unclassified_is_flagged_for_review():
    regions = [QuestionRegion(1, 0, 0, BoundingBox(50, 100, 500, 400))]
    classify_subjects(regions, [], ["Physics", "Chemistry", "Mathematics"], "JEE Advanced")
    assert regions[0].subject == "Unclassified"
    assert regions[0].needs_review is True
