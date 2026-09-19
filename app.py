import time
import streamlit as st
from tenacity import RetryError

from models import DetectedItem
from services.gemini_service import GeminiService
from services.pdf_service import render_pdf, split_page_columns
from services.crop_service import normalized_box_to_absolute, crop_question
from services.subject_service import normalize_subject
from services.answer_key_service import parse_answer_key_text
from services.ppt_service import build_subject_ppt
from services.output_service import create_subject_outputs
from ui.sidebar import render_sidebar
from ui.preview import render_question_preview
from ui.report import render_counts

st.set_page_config(page_title="Vidyapeeth PPT Generator", layout="wide")
st.title("📚 Vidyapeeth Test PPT Generator")

# Initialize sidebar and get settings
settings = render_sidebar()

pdf_file = st.file_uploader("1. Question Paper PDF", type=["pdf"])
template_file = st.file_uploader("2. Sample PPT Template", type=["pptx"])
answer_key_text = st.text_area("3. Answer key", placeholder="1: (3)\n2: (1)")

def process_pipeline(app_settings, uploaded_pdf):
    gemini = GeminiService(api_key=app_settings["api_key"], model_name=app_settings["model_name"])
    
    with st.spinner("Rasterizing PDF to high-DPI images..."):
        # Use a safe default for render_dpi if it's missing
        dpi = app_settings.get("render_dpi", 300)
        pages = render_pdf(uploaded_pdf.read(), dpi=dpi)
    
    questions = []
    headers = []
    total_columns = len(pages) * 2
    completed = 0
    
    progress = st.progress(0)
    status = st.empty()

    for p_idx, page in enumerate(pages):
        outer_margin = app_settings.get("outer_margin", 1.2)
        column_gap = app_settings.get("column_gap", 1.5)
        
        for c_idx, (col_img, off_x, off_y) in enumerate(split_page_columns(page, outer_margin, column_gap)):
            completed += 1
            progress.progress(completed / total_columns)
            status.text(f"Scanning Page {p_idx + 1}/{len(pages)}, Column {c_idx + 1}/2...")

            # Safety delay to respect Gemini free-tier limits (15 Requests Per Minute)
            time.sleep(3.5)

            detected = gemini.detect_column_items(col_img, app_settings["subjects"])
            
            for item in detected:
                try:
                    box = normalized_box_to_absolute(item["box_2d"], col_img.width, col_img.height, off_x, off_y)
                    
                    if item.get("type") == "question":
                        questions.append(DetectedItem(
                            kind="question", 
                            page_index=p_idx, 
                            column_index=c_idx, 
                            box=box,
                            question_number=int(item.get("question_number", 0)), 
                            confidence=item.get("confidence", 0.9)
                        ))
                    elif item.get("type") == "section_header":
                        headers.append(DetectedItem(
                            kind="section_header", 
                            page_index=p_idx, 
                            column_index=c_idx, 
                            box=box,
                            subject=normalize_subject(item.get("subject"), app_settings["subjects"])
                        ))
                except Exception:
                    continue
                
    progress.empty()
    status.empty()

    # Apply chronological serial sorting (Top-down, Left-to-Right layout)
    questions.sort(key=lambda i: i.sort_key)
    headers.sort(key=lambda i: i.sort_key)

    # Assign Subjects & Crop
    grouped = {sub: [] for sub in app_settings["subjects"]}
    grouped["Unclassified"] = []
    
    h_idx = 0
    current_subject = None
    
    status.text("Cropping and applying dark-mode filters...")
    for q in questions:
        # Update current subject based on section headers
        while h_idx < len(headers) and headers[h_idx].sort_key <= q.sort_key:
            current_subject = headers[h_idx].subject
            h_idx += 1
            
        try:
            img = crop_question(pages[q.page_index], q, app_settings.get("pad_x", 15), app_settings.get("pad_y", 10))
            sub = current_subject or "Unclassified"
            grouped.setdefault(sub, []).append({
                "number": q.question_number, 
                "image": img, 
                "page_index": q.page_index
            })
        except ValueError: 
            # Skips invalid or empty crops
            continue

    status.empty()
    for sub in grouped: 
        grouped[sub].sort(key=lambda i: i["number"])
        
    return grouped


if st.button("🚀 Process & Generate", type="primary"):
    if not pdf_file or not template_file or not settings.get("api_key"):
        st.error("Upload required files and enter API key.")
        st.stop()

    try:
        # Call the pipeline explicitly passing the global variables to protect scope
        subject_questions = process_pipeline(settings, pdf_file)
        answers = parse_answer_key_text(answer_key_text)
        
        with st.spinner("Generating PowerPoint files..."):
            zip_buffer = create_subject_outputs(
                template_bytes=template_file.read(),
                subject_questions=subject_questions,
                answers=answers,
                build_ppt_function=build_subject_ppt
            )

        st.success("Extraction Complete.")
        
        # Render UI components
        subject_counts = {s: len(i) for s, i in subject_questions.items() if i}
        render_counts(subject_counts)
        render_question_preview(subject_questions)
        
        safe_filename = str(settings.get('exam_type', 'Test')).replace('/', '_')
        
        st.download_button(
            label="📦 Download Formatted PPTs",
            data=zip_buffer,
            file_name=f"{safe_filename}_Presentations.zip",
            mime="application/zip",
            type="primary"
        )
        
    except RetryError as e:
        # Unwraps the Tenacity error to show exactly why Gemini failed
        error_msg = str(e.last_attempt.exception()) if e.last_attempt else "Unknown API Timeout"
        st.error(f"API Error: The Gemini API rejected the request after multiple retries. Details: {error_msg}")
    except Exception as e:
        st.error(f"Processing Failed: {str(e)}")
        st.exception(e)
