"""Page-level extraction and layout analysis."""

from dataclasses import dataclass

from PIL import Image

from models import PageInfo, TextBlock
from .ocr_engine import ocr_blocks
from .text_extractor import detect_columns, extract_native_blocks


@dataclass
class PageAnalysis:
    page_index: int
    image: Image.Image
    info: PageInfo
    blocks: list[TextBlock]
    used_ocr: bool = False
    native_block_count: int = 0
    ocr_block_count: int = 0

    @property
    def extraction_method(self) -> str:
        return "ocr" if self.used_ocr else "native"

    @property
    def column_count(self) -> int:
        return 2 if any(block.column_index == 1 for block in self.blocks) else 1


def analyze_page(
    page,
    page_image: Image.Image,
    page_index: int,
    dpi: int = 240,
    use_ocr: bool = True,
    native_text_threshold: int = 30,
    page_info: PageInfo | None = None,
) -> PageAnalysis:
    scale = dpi / 72.0
    native_blocks = extract_native_blocks(page, page_index, scale)
    native_chars = sum(len(block.text) for block in native_blocks)
    blocks = native_blocks
    used_ocr = False

    if use_ocr and native_chars < native_text_threshold:
        blocks = ocr_blocks(page_image, page_index)
        used_ocr = True

    blocks = detect_columns(blocks, page_image.width)
    info = page_info or PageInfo(
        page_index=page_index,
        width=page_image.width,
        height=page_image.height,
        pdf_width=float(page.rect.width),
        pdf_height=float(page.rect.height),
        rotation=int(page.rotation or 0),
        dpi=dpi,
    )
    info.extraction_method = "ocr" if used_ocr else "native"
    info.native_text_chars = native_chars
    info.text_blocks = len(blocks)
    info.column_count = 2 if any(block.column_index == 1 for block in blocks) else 1

    return PageAnalysis(
        page_index=page_index,
        image=page_image,
        info=info,
        blocks=blocks,
        used_ocr=used_ocr,
        native_block_count=len(native_blocks),
        ocr_block_count=len(blocks) if used_ocr else 0,
    )
