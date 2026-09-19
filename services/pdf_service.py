from io import BytesIO
from pdf2image import convert_from_bytes


def render_pdf(
    pdf_bytes: bytes,
    dpi: int = 300,
    poppler_path: str | None = None,
):
    pages = convert_from_bytes(
        pdf_bytes,
        dpi=dpi,
        poppler_path=poppler_path,
    )

    if not pages:
        raise ValueError("The uploaded PDF contains no renderable pages.")

    return pages


def split_page_columns(
    page_image,
    outer_margin_percent: float = 1.2,
    column_gap_percent: float = 1.5,
):
    width, height = page_image.size

    outer_margin = outer_margin_percent / 100
    column_gap = column_gap_percent / 100

    left_x0 = int(width * outer_margin)
    left_x1 = int(width * (0.5 - column_gap))
    right_x0 = int(width * (0.5 + column_gap))
    right_x1 = int(width * (1 - outer_margin))

    top = int(height * outer_margin)
    bottom = int(height * (1 - outer_margin))

    return [
        (
            page_image.crop((left_x0, top, left_x1, bottom)),
            left_x0,
            top,
        ),
        (
            page_image.crop((right_x0, top, right_x1, bottom)),
            right_x0,
            top,
        ),
    ]
