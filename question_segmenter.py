"""Exact question-image segmentation.

Questions are bounded by the next *question start*, never by option markers.
Section boundaries are also respected so the next subject header can never leak
into the final question of the previous subject.
"""

from PIL import Image
from models import BoundingBox, QuestionRegion, TextBlock
from .question_detector import question_number
from .paper_structure import PaperStructure


def _column_bounds(page_width: int, column_index: int, two_columns: bool) -> tuple[int, int]:
    if not two_columns or column_index == -1:
        return 0, page_width
    midpoint = page_width // 2
    return (midpoint, page_width) if column_index == 1 else (0, midpoint)


def _trim_content(image: Image.Image, padding: int = 12) -> Image.Image:
    """Trim empty white page margin while preserving diagrams and symbols."""
    rgb = image.convert("RGB")
    gray = rgb.convert("L")
    # A conservative threshold: pure/near-white paper is removed, ink remains.
    # Light grey institutional watermarks are page background, not question
    # content. A lower threshold keeps dark diagrams while excluding those
    # watermark shapes from the content bounds.
    mask = gray.point(lambda p: 0 if p >= 185 else 255)
    bbox = mask.getbbox()
    if not bbox:
        return rgb
    x0 = max(0, bbox[0] - padding)
    y0 = max(0, bbox[1] - padding)
    x1 = min(rgb.width, bbox[2] + padding)
    y1 = min(rgb.height, bbox[3] + padding)
    result = rgb.crop((x0, y0, x1, y1))

    # Remove a PDF page-border line if it is literally glued to an edge.
    arr = __import__("numpy").array(result.convert("L"))
    edge = max(2, min(8, result.width // 100))
    if (arr[:, :edge] < 80).mean() > 0.55:
        result = result.crop((edge, 0, result.width, result.height))
    if (arr[:, -edge:] < 80).mean() > 0.55:
        result = result.crop((0, 0, result.width - edge, result.height))
    return result


def _stitch_vertical(parts: list[Image.Image], background="white") -> Image.Image:
    if len(parts) == 1:
        return parts[0]
    width = max(p.width for p in parts)
    height = sum(p.height for p in parts)
    canvas = Image.new("RGB", (width, height), background)
    y = 0
    for part in parts:
        canvas.paste(part, (0, y))
        y += part.height
    return canvas


def segment_questions(
    page_images,
    questions: list[TextBlock],
    structure: PaperStructure | None = None,
    pad_x: int = 18,
    pad_y: int = 10,
):
    """Create one crop per actual question, including all of its options.

    The algorithm intentionally does not interpret ``(1)``, ``(2)``, etc. as
    questions. It uses the validated question-start markers produced by the
    detector and trims the resulting raster crop to visible content.
    """
    ordered = sorted(questions, key=lambda b: (b.page_index, b.column_index, b.box.y0))
    output = []

    question_by_number = {question_number(q.text): q for q in ordered}
    sections = structure.sections if structure else []

    def section_for(n):
        return structure.section_for(n) if structure else None

    for idx, start in enumerate(ordered):
        number = question_number(start.text)
        if number is None:
            continue
        # The orchestrator attaches the physical section when available.
        # This matters for JEE Advanced papers where question numbers can
        # restart inside another subject/section.
        section = getattr(start, "_section_spec", None) or section_for(number)

        page = page_images[start.page_index]
        two_columns = any(
            q.page_index == start.page_index and q.column_index == 1 for q in ordered
        )

        # Next question in the same physical column on this page is the safest
        # lower boundary. This keeps an adjacent right-column question out.
        next_same_column = None
        for candidate in ordered[idx + 1:]:
            if candidate.page_index != start.page_index:
                break
            if candidate.column_index == start.column_index:
                next_same_column = candidate
                break

        left, right = _column_bounds(page.width, start.column_index, two_columns)
        x0 = max(0, left + pad_x)
        x1 = min(page.width, right - pad_x)

        y0 = max(0, start.box.y0 - pad_y)
        y1 = page.height

        if next_same_column is not None:
            y1 = min(y1, next_same_column.box.y0 - max(3, pad_y // 2))

        # Hard stop at the next subject section header even when it lives in the
        # other column (this is the key fix for the Q25/Q50 boundary).
        if section and structure:
            next_sections = [
                s for s in sections
                if s.page_index is not None
                and (s.page_index > start.page_index or (
                    s.page_index == start.page_index
                    and (s.header_y or 0) > start.box.y0
                ))
                and s.start_number > section.end_number
            ]
            if next_sections:
                ns = sorted(next_sections, key=lambda s: (s.page_index, s.header_y or 0))[0]
                if ns.page_index == start.page_index and ns.header_y is not None:
                    y1 = min(y1, ns.header_y - pad_y)

        # Crop the current page.
        if y1 <= y0:
            continue
        first_part = page.crop((x0, y0, x1, y1))

        # Optional continuation: if the question reaches the bottom of a page
        # and the next numbered question starts on the next page, include the
        # upper portion of that page before the next question. This protects
        # genuinely multi-page questions without joining unrelated pages.
        parts = [first_part]
        end_page_index = start.page_index
        next_global = ordered[idx + 1] if idx + 1 < len(ordered) else None
        if (
            next_same_column is None
            and next_global is not None
            and next_global.page_index == start.page_index + 1
            and y1 >= page.height - max(30, pad_y * 3)
        ):
            next_page = page_images[next_global.page_index]
            next_two_columns = any(
                q.page_index == next_global.page_index and q.column_index == 1
                for q in ordered
            )
            nleft, nright = _column_bounds(
                next_page.width, next_global.column_index, next_two_columns
            )
            nx0 = max(0, nleft + pad_x)
            nx1 = min(next_page.width, nright - pad_x)
            ny1 = max(0, next_global.box.y0 - pad_y)
            if ny1 > pad_y:
                parts.append(next_page.crop((nx0, pad_y, nx1, ny1)))
                end_page_index = next_global.page_index

        image = _trim_content(_stitch_vertical(parts), padding=max(8, pad_x // 2))
        qtype = section.type_for(number) if section else "MCQ"
        output.append(
            QuestionRegion(
                number=number,
                page_index=start.page_index,
                column_index=start.column_index,
                box=BoundingBox(x0, y0, x1, y1).clamp(page.width, page.height),
                image=image,
                ocr_text=start.text,
                confidence=max(0.0, min(1.0, start.confidence)),
                extraction_method=start.source,
                end_page_index=end_page_index,
                question_type=qtype,
                source_section=section,
            )
        )
    return output
