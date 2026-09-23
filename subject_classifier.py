"""Deterministic subject assignment backed by detected paper structure."""

from services.subject_service import normalize_subject


def classify_subjects(regions, headers, known_subjects, exam_type, structure=None):
    for region in regions:
        subject = None
        if structure is not None:
            # Prefer the section identity carried from the detector.  Fall back
            # to numeric ranges for standard JEE Main/NEET papers.
            section = getattr(region, "source_section", None) or structure.section_for(region.number)
            if section and section.subject in known_subjects:
                subject = section.subject
                region.question_type = section.type_for(region.number)

        # For unusual/JEE Advanced papers, use the nearest preceding section
        # header as a secondary evidence source.
        if subject is None:
            preceding = [
                h for h in headers
                if (h.page_index, h.box.y0) <= (region.page_index, region.box.y0)
            ]
            for header in sorted(preceding, key=lambda h: (h.page_index, h.box.y0), reverse=True):
                candidate = normalize_subject(header.text, known_subjects)
                if candidate:
                    subject = candidate
                    break

        if subject is None and exam_type == "JEE Main":
            if 1 <= region.number <= 25:
                subject = "Physics"
            elif 26 <= region.number <= 50:
                subject = "Chemistry"
            elif 51 <= region.number <= 75:
                subject = "Mathematics"
        elif subject is None and exam_type == "NEET UG":
            if 1 <= region.number <= 45:
                subject = "Physics"
            elif 46 <= region.number <= 90:
                subject = "Chemistry"
            elif 91 <= region.number <= 135:
                subject = "Botany"
            elif 136 <= region.number <= 180:
                subject = "Zoology"

        region.subject = subject if subject in known_subjects else "Unclassified"
        region.needs_review = region.subject == "Unclassified"
    return regions
