"""Question-start detection using paper structure, not option markers."""

import re
from models import TextBlock

STANDALONE_NUMBER = re.compile(r"^\s*(\d{1,3})\s*[.)]?\s*$")
INLINE_NUMBER = re.compile(r"^\s*(\d{1,3})\s*[.)]\s+\S")
PAREN_OPTION = re.compile(r"^\s*\(\s*[1-9]\s*\)")


def question_number(text: str):
    """Return a number only when text looks like a question-start marker.

    Option markers such as ``(1)`` are deliberately excluded.
    """
    text = text or ""
    if PAREN_OPTION.match(text):
        return None
    m = STANDALONE_NUMBER.match(text)
    if m:
        return int(m.group(1))
    m = INLINE_NUMBER.match(text)
    return int(m.group(1)) if m else None


def _candidate(block: TextBlock) -> bool:
    text = block.text.strip()
    if PAREN_OPTION.match(text):
        return False
    return bool(STANDALONE_NUMBER.match(text) or INLINE_NUMBER.match(text))


def find_questions(
    blocks: list[TextBlock],
    expected_numbers: set[int] | None = None,
    min_number: int = 1,
    max_number: int = 999,
) -> list[TextBlock]:
    """Find actual question starts.

    ``expected_numbers`` is the critical guard against instruction-page
    numbering and option numbering. For JEE Main, it is {1..75}; therefore the
    instruction list 1..8 is never considered because it is before the first
    detected subject section and the orchestrator passes the relevant page
    window.
    """
    # Real question markers are normally aligned to the left edge of their
    # physical column. Equations can contain standalone-looking numbers much
    # deeper inside the column; rejecting those removes false detections such
    # as the "36" appearing inside a Chemistry equation in the sample paper.
    page_column_min_x = {}
    page_column_width = {}
    for block in blocks:
        key = (block.page_index, block.column_index)
        page_column_min_x[key] = min(
            block.box.x0, page_column_min_x.get(key, block.box.x0)
        )
        page_column_width[key] = max(
            block.box.x1, page_column_width.get(key, block.box.x1)
        )

    candidates = []
    for block in blocks:
        number = question_number(block.text)
        if number is None or not _candidate(block):
            continue
        if not (min_number <= number <= max_number):
            continue
        if expected_numbers is not None and number not in expected_numbers:
            continue

        text = block.text.strip()
        if STANDALONE_NUMBER.match(text):
            key = (block.page_index, block.column_index)
            left_edge = page_column_min_x.get(key, block.box.x0)
            span = max(1, page_column_width.get(key, block.box.x1) - left_edge)
            # Allow a modest indentation while rejecting embedded equation
            # numbers and matrix coefficients.
            if block.box.x0 > left_edge + span * 0.12:
                continue
        candidates.append((number, block))

    # One true question number should have one start. Pick the marker with the
    # smallest x/y marker-like geometry when OCR produces duplicates.
    by_number: dict[int, list[TextBlock]] = {}
    for number, block in candidates:
        by_number.setdefault(number, []).append(block)

    selected = []
    for number, options in by_number.items():
        options.sort(key=lambda b: (b.page_index, b.box.y0, b.box.x0))
        selected.append(options[0])
    return sorted(selected, key=lambda b: (b.page_index, b.column_index, b.box.y0))


HEADER_WORDS = ("physics", "chemistry", "mathematics", "maths", "botany", "zoology", "biology")


def find_headers(blocks: list[TextBlock]) -> list[TextBlock]:
    headers = []
    for block in blocks:
        text = block.text.strip()
        lowered = text.lower()
        if len(text) <= 140 and (
            "section" in lowered
            or any(re.search(rf"\b{re.escape(word)}\b", lowered) for word in HEADER_WORDS)
        ):
            if question_number(text) is None:
                headers.append(block)
    return headers
