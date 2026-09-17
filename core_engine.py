import fitz  # PyMuPDF
import re
import io
from PIL import Image, ImageOps
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

def parse_answer_key(text):
    """Parses raw text into an answer key dictionary {q_num: 'A'}."""
    ans_dict = {}
    if not text:
        return ans_dict
    matches = re.findall(r'(\d+)[\s:\-\.]+\(?([0-9\.\,A-Da-d]+)\)?', text)
    for q_num, ans in matches:
        ans_dict[int(q_num)] = ans.upper()
    return ans_dict

def process_watermark_and_dark_mode(pil_img):
    """
    Suppresses light-grey background watermarks without destroying diagram details,
    then converts the cropped question image into dark mode.
    """
    gray = pil_img.convert('L')
    # Push light-grey watermarks (>205) to pure white (255) while preserving text/diagrams (<=205)
    cleaned = gray.point(lambda p: 255 if p > 205 else p)
    # Invert to dark mode (white text on dark background)
    dark_img = ImageOps.invert(cleaned.convert('RGB'))
    return dark_img

def extract_questions_from_pdf(pdf_bytes):
    """
    Uses PyMuPDF to extract questions using exact vector coordinates.
    Handles two-column layouts, diagrams, tables, and variable heights.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    questions = {}

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_width = page.rect.width
        page_height = page.rect.height
        mid_x = page_width / 2.0

        # Extract text blocks: (x0, y0, x1, y1, text, block_no, block_type)
        blocks = page.get_text("blocks")

        left_blocks = []
        right_blocks = []

        # Split blocks into Left and Right Columns
        for b in blocks:
            if b[6] != 0:  # Ignore non-text blocks
                continue
            x0 = b[0]
            if x0 < mid_x:
                left_blocks.append(b)
            else:
                right_blocks.append(b)

        # Process each column independently
        columns_data = [
            ("left", left_blocks, page_width * 0.03, mid_x - page_width * 0.01),
            ("right", right_blocks, mid_x + page_width * 0.01, page_width * 0.97)
        ]

        for col_name, col_blocks, x_min, x_max in columns_data:
            if not col_blocks:
                continue

            # Locate question header lines (e.g., "1.", "Q.1", "Question 1")
            q_in_col = []
            for b in col_blocks:
                text = b[4].strip()
                match = re.match(r'^(?:Q(?:uestion)?\.?\s*)?(\d+)[\.\s\)]', text, re.IGNORECASE)
                if match:
                    q_num = int(match.group(1))
                    q_in_col.append((q_num, b[1]))  # Store (q_num, y0_position)

            # Sort top-to-bottom
            q_in_col.sort(key=lambda item: item[1])

            # Calculate deterministic height boundaries
            for i, (q_num, y_start) in enumerate(q_in_col):
                if i < len(q_in_col) - 1:
                    # End crop right above the next question
                    y_end = q_in_col[i + 1][1] - 4
                else:
                    # End crop at the bottom-most text block in the column
                    col_bottoms = [b[3] for b in col_blocks if b[1] >= y_start]
                    y_end = max(col_bottoms) + 12 if col_bottoms else page_height - 20

                # Apply dynamic vertical padding
                crop_ymin = max(0, y_start - 12)
                crop_ymax = min(page_height, y_end + 10)

                # Render exact PDF region at high DPI (300 DPI equivalent)
                rect = fitz.Rect(x_min, crop_ymin, x_max, crop_ymax)
                pix = page.get_pixmap(clip=rect, dpi=250)

                # Convert to PIL Image & apply watermark removal + dark mode
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                processed_img = process_watermark_and_dark_mode(img)

                questions[q_num] = processed_img

    return questions

def build_subject_ppts(template_bytes, questions_dict, answer_key_dict, exam_type):
    """Builds subject-wise PPTs using the provided master PPT layout."""
    if "JEE" in exam_type:
        subject_map = {
            "Physics": range(1, 26),
            "Chemistry": range(26, 51),
            "Mathematics": range(51, 76)
        }
    else:
        subject_map = {
            "Physics": range(1, 46),
            "Chemistry": range(46, 91),
            "Botany": range(91, 136),
            "Zoology": range(136, 181)
        }

    output_ppts = {}

    for subject_name, q_range in subject_map.items():
        prs = Presentation(io.BytesIO(template_bytes))
        blank_layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[0]

        has_data = False
        for q_num in q_range:
            if q_num in questions_dict:
                has_data = True
                slide = prs.slides.add_slide(blank_layout)

                # Convert PIL image to byte stream
                img_stream = io.BytesIO()
                questions_dict[q_num].save(img_stream, format="PNG")
                img_stream.seek(0)

                # Position crop centered on the slide
                slide.shapes.add_picture(img_stream, Inches(0.8), Inches(1.0), width=Inches(8.4))

                # Append Answer Key Badge if available
                if q_num in answer_key_dict:
                    tx_box = slide.shapes.add_textbox(Inches(7.0), Inches(6.5), Inches(2.5), Inches(0.8))
                    tf = tx_box.text_frame
                    p = tf.paragraphs[0]
                    p.text = f"Ans. ({answer_key_dict[q_num]})"
                    p.font.size = Pt(28)
                    p.font.bold = True
                    p.font.color.rgb = RGBColor(255, 215, 0)  # PW Gold/Yellow

        if has_data:
            out_buf = io.BytesIO()
            prs.save(out_buf)
            out_buf.seek(0)
            output_ppts[subject_name] = out_buf.getvalue()

    return output_ppts
