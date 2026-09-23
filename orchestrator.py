"""Top-level coordinator for the production local-first pipeline."""

from .confidence import score_region
from .page_analyzer import analyze_page
from .pdf_loader import load_pdf
from .question_detector import find_headers, find_questions
from .question_segmenter import segment_questions
from .paper_structure import build_structure, detect_exam_type
from .subject_classifier import classify_subjects
from .validator import validate_regions


def _blocks_to_text(blocks):
    return "\n".join(block.text for block in blocks if block.text)


def _section_window(blocks_by_page, section, next_section=None):
    """Return only blocks inside a subject's physical document window.

    This is critical for NEET: instruction pages may contain numbered rules,
    while the four subject blocks can start on different pages.  It is also
    useful for JEE Advanced where section/subject layouts vary from paper to
    paper.
    """
    selected = []
    for page_index, blocks in enumerate(blocks_by_page):
        if section.page_index is not None and page_index < section.page_index:
            continue
        if next_section and next_section.page_index is not None and page_index > next_section.page_index:
            break
        for block in blocks:
            if section.page_index == page_index and section.header_y is not None and block.box.y0 < section.header_y:
                continue
            if next_section and next_section.page_index == page_index and next_section.header_y is not None:
                if block.box.y0 >= next_section.header_y:
                    continue
            selected.append(block)
    return selected


def run_pipeline(
    pdf_bytes,
    exam_type=None,
    subjects=None,
    dpi=240,
    pad_x=18,
    pad_y=10,
    use_ocr=True,
    answers=None,
):
    loaded = load_pdf(pdf_bytes, dpi)
    blocks_by_page = []
    all_headers = []
    try:
        for index, page in enumerate(loaded.document):
            analysis = analyze_page(
                page,
                loaded.pages[index],
                index,
                dpi=dpi,
                use_ocr=use_ocr,
                page_info=loaded.page_info[index],
            )
            blocks_by_page.append(analysis.blocks)
            all_headers.extend(find_headers(analysis.blocks))

        first_pages_text = "\n".join(
            _blocks_to_text(blocks) for blocks in blocks_by_page[:3]
        )
        detected_exam, exam_confidence = detect_exam_type(first_pages_text)
        if not exam_type or exam_type == "Auto":
            exam_type = detected_exam
        elif detected_exam != "Unknown" and exam_type != detected_exam:
            # The paper's explicit label wins over a stale UI selection.
            exam_type = detected_exam

        structure = build_structure(blocks_by_page, exam_type)
        expected = {
            n
            for section in structure.sections
            for n in range(section.start_number, section.end_number + 1)
            if section.end_number < 1000
        }

        all_questions = []
        if structure.sections:
            # Run detection section-by-section for every exam type.  This is
            # safer than a global 1..N scan because NEET has four fixed
            # subject ranges and JEE Advanced can reuse question numbers in
            # different subject/section blocks.
            for section_index, section in enumerate(structure.sections):
                next_section = structure.sections[section_index + 1] if section_index + 1 < len(structure.sections) else None
                window = _section_window(blocks_by_page, section, next_section)
                expected_numbers = None
                if section.end_number < 1000:
                    expected_numbers = set(range(section.start_number, section.end_number + 1))
                found = find_questions(
                    window,
                    expected_numbers=expected_numbers,
                    min_number=section.start_number if section.end_number < 1000 else 1,
                    max_number=section.end_number if section.end_number < 1000 else 999,
                )
                for block in found:
                    # Carry the physical section identity forward.  Number
                    # alone is not sufficient for some JEE Advanced papers.
                    block._section_spec = section
                all_questions.extend(found)

        # De-duplicate OCR duplicates.  Standard papers use a global question
        # number; JEE Advanced may reuse numbers in separate subject sections,
        # so the physical section is part of the key there.
        from .question_detector import question_number
        unique = {}
        for q in all_questions:
            number = question_number(q.text)
            if number is None:
                continue
            section = getattr(q, "_section_spec", None)
            if exam_type == "JEE Advanced" and section is not None:
                key = (section.subject, number, q.page_index, q.column_index, q.box.y0)
            else:
                key = (number,)
            unique.setdefault(key, q)
        all_questions = sorted(
            unique.values(), key=lambda b: (b.page_index, b.column_index, b.box.y0)
        )

        regions = segment_questions(
            loaded.pages,
            all_questions,
            structure=structure,
            pad_x=pad_x,
            pad_y=pad_y,
        )
        effective_subjects = subjects or [
            section.subject for section in structure.sections
            if section.subject != "Unclassified"
        ]
        regions = classify_subjects(
            regions,
            all_headers,
            effective_subjects,
            exam_type,
            structure=structure,
        )

        for region in regions:
            region.confidence = score_region(region)
            if answers and region.number in answers:
                region.answer = answers[region.number]

        report = validate_regions(regions, answers)
        report.pages = len(loaded.pages)
        report.exam_type = exam_type
        report.exam_confidence = exam_confidence
        report.expected_questions = sum(
            s.end_number - s.start_number + 1
            for s in structure.sections
            if s.end_number < 1000
        )
        report.detected_questions = len(regions)
        return regions, report, structure
    finally:
        loaded.document.close()
