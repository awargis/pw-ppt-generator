import io

from .slide_builder import build_slides


def export_subject_ppts(template_bytes, regions, answers, style="Premium Light"):
    """Build one PPTX per subject from the uploaded template."""
    result = {}
    active = [region for region in regions if getattr(region, "included", True) and region.image is not None]
    preferred_order = ["Physics", "Chemistry", "Mathematics", "Botany", "Zoology", "Biology", "Unclassified"]
    present = {region.subject for region in active}
    subjects = [s for s in preferred_order if s in present] + sorted(present - set(preferred_order))
    for subject in subjects:
        selected = sorted(
            [region for region in active if region.subject == subject],
            key=lambda region: region.number,
        )
        if not selected:
            continue
        prs = build_slides(template_bytes, selected, answers, style=style)
        output = io.BytesIO()
        prs.save(output)
        data = output.getvalue()
        if len(data) < 1000:
            raise ValueError(f"Generated PPT for {subject} is unexpectedly small.")
        result[subject] = data
    return result
