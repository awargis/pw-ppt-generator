import os
import io
import zipfile
import tempfile
import cv2
import numpy as np
import streamlit as st
from PIL import Image
from pdf2image import convert_from_bytes
from pptx import Presentation
from pptx.util import Emu
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# --- UI Configuration ---
st.set_page_config(page_title="Vidyapeeth PPT Generator", layout="wide")
st.title("📚 Test Paper to PPT Pipeline")

# --- Schemas ---
class BoundingBox(BaseModel):
    y_min: float = Field(description="Normalized top coordinate (0-1000)")
    x_min: float = Field(description="Normalized left coordinate (0-1000)")
    y_max: float = Field(description="Normalized bottom coordinate (0-1000)")
    x_max: float = Field(description="Normalized right coordinate (0-1000)")

class Question(BaseModel):
    number: int
    subject: str = Field(description="Strictly: Physics, Chemistry, Mathematics, Botany, or Zoology")
    box: BoundingBox

class PageExtraction(BaseModel):
    questions: list[Question]

# --- Core Functions ---
def process_image_dark_mode(crop_pil: Image.Image) -> io.BytesIO:
    """Converts a standard crop into a high-contrast white-on-black image."""
    # Convert PIL to OpenCV format
    img_cv = cv2.cvtColor(np.array(crop_pil), cv2.COLOR_RGB2BGR)
    
    # Grayscale
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    
    # Otsu's Binarization to strictly separate text from paper texture
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Invert (Make background black, text white)
    inverted = cv2.bitwise_not(binary)
    
    # Convert back to PIL and save to buffer
    final_pil = Image.fromarray(inverted)
    img_buffer = io.BytesIO()
    final_pil.save(img_buffer, format="PNG")
    img_buffer.seek(0)
    
    return img_buffer

def sort_questions_serially(questions_data, img_width):
    """Sorts questions chronologically using dual-column layout logic."""
    midpoint = img_width / 2
    
    def get_sort_key(q):
        # Determine column: 0 for left, 1 for right
        col = 0 if q['abs_box'][0] < midpoint else 1
        # Sort by: Page Number -> Column -> Y-coordinate (Top to bottom)
        return (q['page'], col, q['abs_box'][1])
        
    return sorted(questions_data, key=get_sort_key)

def build_subject_ppt(template_bytes: bytes, questions: list, answers: dict) -> bytes:
    """Clones the template slide and injects the dark-mode crops."""
    prs = Presentation(io.BytesIO(template_bytes))
    
    # Find template slide index (assuming it's the first slide with #QUESTION)
    template_slide = prs.slides[0]
    slide_layout = template_slide.slide_layout
    
    # Content area bounding box (Adjust these based on exact template dimensions)
    content_left, content_top = Emu(int(0.5 * 914400)), Emu(int(1.5 * 914400))
    content_width, content_height = Emu(int(9.0 * 914400)), Emu(int(5.0 * 914400))

    for q in questions:
        new_slide = prs.slides.add_slide(slide_layout)
        
        # Replace placeholders
        for shape in new_slide.shapes:
            if shape.has_text_frame:
                if "#QUESTION" in shape.text:
                    shape.text = shape.text.replace("#QUESTION", f"Q{q['number']}")
                if "Ans. (?)" in shape.text:
                    ans = answers.get(str(q['number']), "")
                    shape.text = shape.text.replace("Ans. (?)", f"Ans. ({ans})")
        
        # Insert Image
        new_slide.shapes.add_picture(
            q['img_buffer'], 
            content_left, content_top, 
            width=content_width
        )

    # Remove the original template slide
    xml_slides = prs.slides._sldIdLst
    xml_slides.remove(xml_slides[0])
    
    out_buffer = io.BytesIO()
    prs.save(out_buffer)
    return out_buffer.getvalue()

# --- Streamlit UI ---
with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input("Gemini API Key", type="password")
    exam_track = st.radio("Exam Track", ["JEE", "NEET"])
    
    st.subheader("Crop Tuning")
    pad_x = st.slider("Horizontal Padding", 0, 50, 15)
    pad_y = st.slider("Vertical Padding", 0, 50, 10)

pdf_file = st.file_uploader("1. Upload Question Paper (PDF)", type="pdf")
ppt_template = st.file_uploader("2. Upload PPT Template", type="pptx")
answer_key_text = st.text_area("3. Answer Key (Format: 1:A, 2:B...)", height=100)

if st.button("Generate PPTs", type="primary"):
    if not api_key or not pdf_file or not ppt_template:
        st.error("Please provide the API key, PDF, and PPT template.")
        st.stop()

    client = genai.Client(api_key=api_key)
    subjects_map = {
        "JEE": ["Physics", "Chemistry", "Mathematics"],
        "NEET": ["Physics", "Chemistry", "Botany", "Zoology"]
    }[exam_track]

    # Parse answers
    answers = {}
    if answer_key_text:
        for pair in answer_key_text.replace("\n", ",").split(","):
            if ":" in pair:
                k, v = pair.split(":")
                answers[k.strip()] = v.strip()

    with st.spinner("Rasterizing PDF to high-DPI images..."):
        pages = convert_from_bytes(pdf_file.read(), dpi=300)

    extracted_data = []
    
    progress = st.progress(0)
    for i, page in enumerate(pages):
        st.text(f"Extracting coordinates from Page {i+1}...")
        
        img_byte_arr = io.BytesIO()
        page.save(img_byte_arr, format='PNG')
        img_bytes = img_byte_arr.getvalue()

        prompt = f"Identify all questions on this page. Assign each to one of these subjects: {', '.join(subjects_map)}. Return normalized bounding boxes (0-1000)."
        
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[
                    types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=PageExtraction,
                    temperature=0.0
                )
            )
            
            page_width, page_height = page.size
            
            # Process coordinates and apply OpenCV filters
            for q in response.parsed.questions:
                # Convert 0-1000 scale to absolute pixels with padding
                x0 = max(0, int((q.box.x_min / 1000) * page_width) - pad_x)
                y0 = max(0, int((q.box.y_min / 1000) * page_height) - pad_y)
                x1 = min(page_width, int((q.box.x_max / 1000) * page_width) + pad_x)
                y1 = min(page_height, int((q.box.y_max / 1000) * page_height) + pad_y)
                
                crop = page.crop((x0, y0, x1, y1))
                dark_img_buffer = process_image_dark_mode(crop)
                
                extracted_data.append({
                    "number": q.number,
                    "subject": q.subject,
                    "page": i,
                    "abs_box": (x0, y0, x1, y1),
                    "img_buffer": dark_img_buffer
                })
                
        except Exception as e:
            st.error(f"Failed on page {i+1}: {e}")
            
        progress.progress((i + 1) / len(pages))

    if not extracted_data:
        st.error("No questions detected.")
        st.stop()

    st.success("Extraction complete. Generating Subject PPTs...")

    # Sort sequentially based on column layout
    sorted_questions = sort_questions_serially(extracted_data, pages[0].size[0])

    # Group by subject
    subject_groups = {sub: [] for sub in subjects_map}
    for q in sorted_questions:
        if q['subject'] in subject_groups:
            subject_groups[q['subject']].append(q)

    # Generate PPTs and Zip in memory
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        template_bytes = ppt_template.read()
        
        for subject, qs in subject_groups.items():
            if qs:
                ppt_bytes = build_subject_ppt(template_bytes, qs, answers)
                zip_file.writestr(f"{exam_track}_Test/{subject}/{subject}_Discussion.pptx", ppt_bytes)

    zip_buffer.seek(0)
    
    st.download_button(
        label="📦 Download Formatted PPTs",
        data=zip_buffer,
        file_name=f"{exam_track}_Test_Presentations.zip",
        mime="application/zip",
        type="primary"
    )
