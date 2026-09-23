import io
import json
import re
import zipfile
from datetime import datetime, timezone

from ppt.exporter import export_subject_ppts


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_") or "Unclassified"


def create_subject_outputs(template_bytes: bytes, regions, answers: dict, style: str = "Premium Light"):
    """Create a production ZIP containing PPTX files, crops and a manifest."""
    outputs = export_subject_ppts(template_bytes, regions, answers, style=style)
    archive_buffer = io.BytesIO()
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "questions": [],
        "presentations": [],
    }
    with zipfile.ZipFile(archive_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for region in regions:
            if not getattr(region, "included", True) or region.image is None:
                continue
            subject = safe_name(region.subject)
            crop_path = f"crops/{subject}/Q{region.number:03d}.png"
            crop_stream = io.BytesIO()
            region.image.save(crop_stream, "PNG", optimize=True)
            archive.writestr(crop_path, crop_stream.getvalue())
            manifest["questions"].append({
                "number": region.number,
                "subject": region.subject,
                "answer": answers.get(region.number, region.answer),
                "confidence": region.confidence,
                "needs_review": region.needs_review,
                "question_type": getattr(region, "question_type", "MCQ"),
                "page_index": region.page_index,
                "column_index": region.column_index,
                "crop": crop_path,
            })

        for subject, ppt_bytes in outputs.items():
            name = safe_name(subject)
            ppt_path = f"presentations/{name}/{name}_Discussion.pptx"
            archive.writestr(ppt_path, ppt_bytes)
            manifest["presentations"].append({"subject": subject, "file": ppt_path})

        archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))

    archive_buffer.seek(0)
    return archive_buffer, manifest
