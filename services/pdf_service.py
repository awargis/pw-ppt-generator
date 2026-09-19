from pdf2image import convert_from_bytes

def render_pdf(pdf_bytes: bytes, dpi: int = 300):
    pages = convert_from_bytes(pdf_bytes, dpi=dpi)
    if not pages: raise ValueError("PDF contains no renderable pages.")
    return pages

def split_page_columns(page_image, outer_margin_percent: float = 1.2, column_gap_percent: float = 1.5):
    width, height = page_image.size
    outer_margin = outer_margin_percent / 100
    column_gap = column_gap_percent / 100

    left_x0, top = int(width * outer_margin), int(height * outer_margin)
    left_x1 = int(width * (0.5 - column_gap))
    right_x0 = int(width * (0.5 + column_gap))
    right_x1, bottom = int(width * (1 - outer_margin)), int(height * (1 - outer_margin))

    return [
        (page_image.crop((left_x0, top, left_x1, bottom)), left_x0, top),
        (page_image.crop((right_x0, top, right_x1, bottom)), right_x0, top),
    ]
