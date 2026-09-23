from models import BoundingBox, TextBlock
from pipeline.paper_structure import build_structure


def block(text, page, y, x=10, column=0):
    return TextBlock(
        text=text,
        box=BoundingBox(x, y, x + 120, y + 16),
        page_index=page,
        column_index=column,
    )


def test_neet_subject_headings_do_not_start_on_instruction_cover():
    pages = [
        [
            block("Physics:", 0, 140),
            block("Chemistry:", 0, 170),
            block("Botany:", 0, 200),
            block("Zoology:", 0, 230),
            block("GENERAL INSTRUCTIONS", 0, 260),
            block("1.", 0, 300),
        ],
        [block("Physics:", 1, 30), block("1.", 1, 65), block("45.", 1, 900)],
        [block("Chemistry:", 2, 30), block("46.", 2, 65), block("90.", 2, 900)],
        [block("Botany:", 3, 30), block("91.", 3, 65), block("135.", 3, 900)],
        [block("Zoology:", 4, 30), block("136.", 4, 65), block("180.", 4, 900)],
    ]

    structure = build_structure(pages, "NEET UG")
    assert [(s.subject, s.start_number, s.end_number) for s in structure.sections] == [
        ("Physics", 1, 45),
        ("Chemistry", 46, 90),
        ("Botany", 91, 135),
        ("Zoology", 136, 180),
    ]
    assert [s.page_index for s in structure.sections] == [1, 2, 3, 4]
    assert structure.instruction_pages == {0}


def test_jee_advanced_subject_ranges_can_restart_question_numbers():
    pages = [
        [block("JEE Advanced", 0, 20), block("GENERAL INSTRUCTIONS", 0, 50)],
        [block("PHYSICS", 1, 30), block("1.", 1, 70), block("2.", 1, 120)],
        [block("CHEMISTRY", 2, 30), block("1.", 2, 70), block("2.", 2, 120)],
        [block("MATHEMATICS", 3, 30), block("1.", 3, 70), block("3.", 3, 120)],
    ]

    structure = build_structure(pages, "JEE Advanced")
    assert [(s.subject, s.start_number, s.end_number) for s in structure.sections] == [
        ("Physics", 1, 2),
        ("Chemistry", 1, 2),
        ("Mathematics", 1, 3),
    ]
    assert structure.instruction_pages == {0}
