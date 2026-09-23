"""Automatic exam and paper-structure detection.

The detector is deliberately paper-driven.  Fixed ranges are used only for
standard JEE Main/NEET papers after the exam has been identified.  For JEE
Advanced and other variants, subject headers and the actual question markers
are used to infer the subject windows instead of assuming one rigid numbering
scheme.
"""

from dataclasses import dataclass, field
import re


@dataclass
class SectionSpec:
    subject: str
    start_number: int
    end_number: int
    page_index: int | None = None
    header_y: int | None = None
    question_types: dict[tuple[int, int], str] = field(default_factory=dict)

    def type_for(self, number: int) -> str:
        for (lo, hi), kind in self.question_types.items():
            if lo <= number <= hi:
                return kind
        return "MCQ"


@dataclass
class PaperStructure:
    exam_type: str
    sections: list[SectionSpec]
    instruction_pages: set[int] = field(default_factory=set)

    @property
    def ranges(self) -> list[tuple[int, int, str]]:
        return [(s.start_number, s.end_number, s.subject) for s in self.sections]

    def section_for(self, number: int) -> SectionSpec | None:
        for section in self.sections:
            if section.start_number <= number <= section.end_number:
                return section
        return None


SUBJECT_ALIASES = {
    "physics": "Physics",
    "chemistry": "Chemistry",
    "mathematics": "Mathematics",
    "maths": "Mathematics",
    "biology": "Biology",
    "botany": "Botany",
    "zoology": "Zoology",
}


def normalize_subject(text: str) -> str | None:
    lowered = text.lower()
    for alias, subject in SUBJECT_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            return subject
    return None


def detect_exam_type(page_text: str) -> tuple[str, float]:
    text = page_text.lower()
    # Look for the strongest explicit identifiers first.  NEET papers often
    # mention JEE nowhere, while JEE Advanced may contain the word JEE Main in
    # boilerplate/reference text, so Advanced wins when explicitly present.
    if re.search(r"\bjee\s*advanced\b|advanced\s+entrance", text):
        return "JEE Advanced", 0.99
    if re.search(r"\bneet(?:\s*ug)?\b|national\s+eligibility\s+cum\s+entrance", text):
        return "NEET UG", 0.99
    if re.search(r"\bjee\s*main\b|joint\s+entrance\s+examination", text):
        return "JEE Main", 0.99
    return "Unknown", 0.0


_RANGE_RE = re.compile(r"\((\d+)\s*[-–]\s*(\d+)\)")
_SECTION_RE = re.compile(r"section\s*[-–]?\s*[ivx]+\s*\(?\s*([a-z]+)\s*\)?", re.I)
_TYPE_RANGE_RE = re.compile(
    r"(single\s+correct|multiple\s+correct|integer|numerical|numerical\s+value|"
    r"matrix|match\s+the\s+following).*?\((\d+)\s*[-–]\s*(\d+)\)",
    re.I,
)
_NUMBER_MARKER_RE = re.compile(r"^\s*(\d{1,3})\s*[.)]?\s*$")


def _fixed_structure(exam_type: str) -> list[SectionSpec]:
    if exam_type == "JEE Main":
        return [
            SectionSpec("Physics", 1, 25, question_types={(1, 20): "MCQ", (21, 25): "Integer"}),
            SectionSpec("Chemistry", 26, 50, question_types={(26, 45): "MCQ", (46, 50): "Integer"}),
            SectionSpec("Mathematics", 51, 75, question_types={(51, 70): "MCQ", (71, 75): "Integer"}),
        ]
    if exam_type == "NEET UG":
        return [
            SectionSpec("Physics", 1, 45, question_types={(1, 45): "MCQ"}),
            SectionSpec("Chemistry", 46, 90, question_types={(46, 90): "MCQ"}),
            SectionSpec("Botany", 91, 135, question_types={(91, 135): "MCQ"}),
            SectionSpec("Zoology", 136, 180, question_types={(136, 180): "MCQ"}),
        ]
    return []


def _is_subject_header(text: str, subject: str) -> bool:
    """Recognize a real subject heading, not an instruction paragraph.

    NEET papers commonly use headings such as ``Physics:``, ``Chemistry`` or
    ``Botany:`` without the JEE-style ``SECTION-I`` prefix.  The old detector
    required the word SECTION and therefore started NEET cropping on the
    instruction page.  Keep this rule conservative: a subject heading must be
    a short standalone line and must not look like an instruction sentence.
    """
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text or len(text) > 90:
        return False
    lowered = text.lower()
    if subject.lower() not in lowered:
        return False
    if any(word in lowered for word in ("instruction", "question paper", "duration", "marks", "correct answer", "contains")):
        return False
    # Accept common title forms: "Physics", "Physics:", "SECTION-I (PHYSICS)",
    # and "Physics (45 Questions)".
    return bool(re.fullmatch(
        rf"(?:section\s*[-–]?\s*[ivx]+\s*\(?\s*)?{re.escape(subject)}(?:\s*\(?\s*\d+\s*(?:questions?|q)\s*\)?)?\s*[:.)]?\s*",
        lowered,
        re.I,
    ))


def _find_subject_headers(blocks_by_page, subject: str):
    hits = []
    for page_index, blocks in enumerate(blocks_by_page):
        for block in blocks:
            if _is_subject_header(block.text, subject):
                hits.append((page_index, block.box.y0, block))
    return sorted(hits, key=lambda item: (item[0], item[1]))


def _header_is_question_section(blocks_by_page, page_index: int, header_y: int, expected_start: int) -> bool:
    """Check whether a subject heading is attached to a real question page.

    Cover/topic pages often list ``Physics:``, ``Chemistry:`` and ``Mathematics:``
    together.  Those are not section anchors.  A real section heading is
    normally followed by the section's first numbered question and option
    markers on the same page (or very shortly afterwards).
    """
    marker = re.compile(rf"^\s*{expected_start}\s*[.)]?\s*$")
    # A cover/instruction page may itself list Physics/Chemistry/etc. and then
    # contain numbered instructions.  Those numbers are not question starts.
    if page_index < len(blocks_by_page):
        for block in blocks_by_page[page_index]:
            if re.search(r"general\s+instructions?", block.text or "", re.I):
                return False
    for pidx in range(page_index, min(len(blocks_by_page), page_index + 2)):
        for block in blocks_by_page[pidx]:
            if pidx == page_index and block.box.y0 < header_y:
                continue
            if marker.match((block.text or "").strip()):
                return True
    return False


def _find_first_question_after(blocks_by_page, start_page: int, start_y: int, lo: int, hi: int):
    """Fallback anchor when a paper has no standalone subject title."""
    for page_index in range(start_page, len(blocks_by_page)):
        blocks = blocks_by_page[page_index]
        for block in sorted(blocks, key=lambda b: (b.box.y0, b.box.x0)):
            if page_index == start_page and block.box.y0 < start_y:
                continue
            m = _NUMBER_MARKER_RE.match((block.text or "").strip())
            if m and lo <= int(m.group(1)) <= hi:
                return page_index, block.box.y0
    return None, None


def build_structure(blocks_by_page: list[list], exam_type: str) -> PaperStructure:
    """Build a structure from the uploaded paper's own headings and ranges."""
    fixed = _fixed_structure(exam_type)
    if fixed:
        for section in fixed:
            hits = _find_subject_headers(blocks_by_page, section.subject)
            # Prefer explicit SECTION-I/II/III headings.  Otherwise accept a
            # subject title only when its page is actually followed by the
            # first question for that subject.  This rejects NEET/JEE cover
            # pages that merely list the syllabus/topics.
            explicit = [h for h in hits if re.search(r"^\s*section\s*[-–]?\s*[ivx]+", h[2].text, re.I)]
            candidates = explicit or hits
            selected = next(
                (h for h in candidates if _header_is_question_section(blocks_by_page, h[0], h[1], section.start_number)),
                None,
            )
            if selected is None and explicit:
                selected = explicit[0]
            if selected:
                section.page_index, section.header_y, _ = selected

        # If a subject heading was not extracted (scanned/oddly formatted PDF),
        # anchor that section at its first plausible question, but only after
        # the previous section anchor. This avoids instruction-page numbers.
        search_page = 0
        search_y = -1
        for section in fixed:
            if section.page_index is not None:
                search_page = section.page_index
                search_y = section.header_y if section.header_y is not None else -1
            else:
                page, y = _find_first_question_after(
                    blocks_by_page, search_page, search_y, section.start_number, section.end_number
                )
                if page is not None:
                    section.page_index, section.header_y = page, max(0, y - 2)
            if section.page_index is not None:
                search_page = section.page_index
                search_y = section.header_y or -1

        known_starts = [s.page_index for s in fixed if s.page_index is not None]
        first_question_page = min(known_starts) if known_starts else 1
        return PaperStructure(
            exam_type=exam_type,
            sections=fixed,
            instruction_pages=set(range(first_question_page)),
        )

    # Generic JEE Advanced / unusual mode. Subject headings define windows;
    # question numbers inside each window define its numeric range. We do not
    # assume JEE Advanced has the JEE Main 1..75 numbering scheme.
    subject_order = ["Physics", "Chemistry", "Mathematics", "Botany", "Zoology", "Biology"]
    anchors = []
    for subject in subject_order:
        for page, y, block in _find_subject_headers(blocks_by_page, subject):
            anchors.append((page, y, subject))
            break
    anchors.sort(key=lambda item: (item[0], item[1]))

    sections: list[SectionSpec] = []
    for idx, (page, y, subject) in enumerate(anchors):
        next_anchor = anchors[idx + 1] if idx + 1 < len(anchors) else None
        numbers = []
        for pidx in range(page, len(blocks_by_page)):
            if next_anchor and pidx > next_anchor[0]:
                break
            for block in blocks_by_page[pidx]:
                if pidx == page and block.box.y0 < y:
                    continue
                if next_anchor and pidx == next_anchor[0] and block.box.y0 >= next_anchor[1]:
                    continue
                m = _NUMBER_MARKER_RE.match((block.text or "").strip())
                if m:
                    numbers.append(int(m.group(1)))
        numbers = sorted(set(n for n in numbers if 1 <= n <= 999))
        if numbers:
            sections.append(SectionSpec(subject, min(numbers), max(numbers), page, y))
        else:
            sections.append(SectionSpec(subject, 1, 999, page, y))

    if not sections:
        sections = [SectionSpec("Unclassified", 1, 999)]

    first_page = min((s.page_index for s in sections if s.page_index is not None), default=2)
    return PaperStructure(
        exam_type=exam_type,
        sections=sections,
        instruction_pages=set(range(first_page)),
    )
