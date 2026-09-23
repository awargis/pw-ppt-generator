"""PDF loading and deterministic page rendering.

The loader owns the PDF handle and returns rendered RGB page images together
with lightweight page metadata. No OCR or question logic belongs here.
"""

from dataclasses import dataclass

import fitz
from PIL import Image

from models import PageInfo


@dataclass
class LoadedPDF:
    """Rendered pages plus their source metadata and live PyMuPDF document."""

    pages: list[Image.Image]
    page_info: list[PageInfo]
    document: fitz.Document


def load_pdf(pdf_bytes: bytes, dpi: int = 240) -> LoadedPDF:
    if not pdf_bytes:
        raise ValueError("The PDF is empty.")
    if dpi < 72 or dpi > 600:
        raise ValueError("DPI must be between 72 and 600.")

    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise ValueError(f"Unable to open PDF: {exc}") from exc

    if document.page_count == 0:
        document.close()
        raise ValueError("The PDF has no pages.")

    pages: list[Image.Image] = []
    metadata: list[PageInfo] = []
    try:
        for index, page in enumerate(document):
            rect = page.rect
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            native_text = page.get_text("text") or ""
            pages.append(image)
            metadata.append(
                PageInfo(
                    page_index=index,
                    width=image.width,
                    height=image.height,
                    pdf_width=float(rect.width),
                    pdf_height=float(rect.height),
                    rotation=int(page.rotation or 0),
                    dpi=dpi,
                    native_text_chars=len(native_text.strip()),
                )
            )
    except Exception:
        document.close()
        raise

    return LoadedPDF(pages, metadata, document)
