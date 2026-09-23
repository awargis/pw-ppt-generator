import fitz

from pipeline.pdf_loader import load_pdf
from pipeline.page_analyzer import analyze_page


def make_single_column_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((60, 70), "Physics Practice Paper")
    page.insert_text((60, 120), "1. Find the velocity of the particle.")
    page.insert_text((60, 170), "2. Find the acceleration of the particle.")
    data = doc.tobytes()
    doc.close()
    return data


def make_two_column_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((40, 80), "1. Left column question")
    page.insert_text((40, 140), "2. Another left question")
    page.insert_text((330, 80), "3. Right column question")
    page.insert_text((330, 140), "4. Another right question")
    data = doc.tobytes()
    doc.close()
    return data


def test_pdf_loader_preserves_rendered_dimensions_and_metadata():
    loaded = load_pdf(make_single_column_pdf(), dpi=144)
    try:
        assert len(loaded.pages) == 1
        image = loaded.pages[0]
        info = loaded.page_info[0]
        assert image.width == info.width
        assert image.height == info.height
        assert info.pdf_width == 595
        assert info.pdf_height == 842
        assert info.native_text_chars > 0
    finally:
        loaded.document.close()


def test_page_analyzer_prefers_native_text():
    loaded = load_pdf(make_single_column_pdf(), dpi=144)
    try:
        analysis = analyze_page(
            loaded.document[0],
            loaded.pages[0],
            0,
            dpi=144,
            use_ocr=False,
            page_info=loaded.page_info[0],
        )
        assert not analysis.used_ocr
        assert analysis.native_block_count >= 3
        assert all(block.source == "native" for block in analysis.blocks)
        assert {block.column_index for block in analysis.blocks} == {0}
    finally:
        loaded.document.close()


def test_page_analyzer_detects_real_two_column_layout():
    loaded = load_pdf(make_two_column_pdf(), dpi=144)
    try:
        analysis = analyze_page(
            loaded.document[0],
            loaded.pages[0],
            0,
            dpi=144,
            use_ocr=False,
            page_info=loaded.page_info[0],
        )
        assert {block.column_index for block in analysis.blocks} == {0, 1}
    finally:
        loaded.document.close()
