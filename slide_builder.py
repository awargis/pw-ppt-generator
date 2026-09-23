import copy
import io

from .layout_engine import find_image_placeholder, fit_box
from .template_validator import validate_template

RELATIONSHIP_NAMESPACE = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _duplicate_slide(prs, source_index=0):
    source = prs.slides[source_index]
    target = prs.slides.add_slide(source.slide_layout)

    for shape in list(target.shapes):
        shape._element.getparent().remove(shape._element)

    relationships = {}
    for relationship_id, relationship in source.part.rels.items():
        if "notesSlide" in relationship.reltype or "slideLayout" in relationship.reltype:
            continue
        relationships[relationship_id] = target.part.relate_to(
            relationship.target_ref if relationship.is_external else relationship.target_part,
            relationship.reltype,
            is_external=relationship.is_external,
        )

    for shape in source.shapes:
        element = copy.deepcopy(shape._element)
        for child in element.iter():
            for attribute, value in list(child.attrib.items()):
                if attribute.startswith(RELATIONSHIP_NAMESPACE) and value in relationships:
                    child.set(attribute, relationships[value])
        target.shapes._spTree.insert_element_before(element, "p:extLst")
    return target


def _replace_template_tokens(slide, region, answer):
    replacements = {
        "#QUESTION": f"Q{region.number}",
        "#ANSWER": answer or region.answer or "—",
        "#SUBJECT": region.subject,
    }
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        for paragraph in shape.text_frame.paragraphs:
            for run in paragraph.runs:
                for token, value in replacements.items():
                    run.text = run.text.replace(token, str(value))


def _remove_shape(shape):
    element = shape._element
    element.getparent().remove(element)


def _add_question_image(slide, prs, region):
    if region.image is None:
        raise ValueError(f"Question {region.number} has no crop image.")
    stream = io.BytesIO()
    region.image.save(stream, "PNG", optimize=True)
    stream.seek(0)

    placeholder = find_image_placeholder(slide)
    if placeholder is not None:
        left, top, width, height = placeholder.left, placeholder.top, placeholder.width, placeholder.height
        _remove_shape(placeholder)
    else:
        left, top, width, height = fit_box(prs, region.image)
    slide.shapes.add_picture(stream, left, top, width=width, height=height)


def build_slides(template_bytes, regions, answers, style="Premium Light"):
    """Clone the first template slide once per question and inject the crop."""
    prs = validate_template(template_bytes)
    source_index = 0
    for region in regions:
        slide = _duplicate_slide(prs, source_index)
        _replace_template_tokens(slide, region, str(answers.get(region.number, "")))
        _add_question_image(slide, prs, region)

    slide_ids = prs.slides._sldIdLst
    slide_ids.remove(slide_ids[0])
    return prs
