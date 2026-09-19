import time
import streamlit as st
from tenacity import RetryError

from models import DetectedItem
from services.gemini_service import GeminiService
from services.pdf_service import render_pdf, split_page_columns
from services.crop_service import normalized_box_to_absolute, crop_question
from services.subject_service import assign_subject_by_number
from services.answer_key_service import parse_answer_key_text
from services.ppt_service import build_subject_ppt
from services.output_service import create_subject_outputs
from ui.sidebar import render_sidebar
from ui.preview import render_question_preview
from ui.report import render_counts

st.set_page_config(page_title="Vidyapeeth PPT Generator", layout="wide")
st.title("📚 Vidyapeeth Test PPT Generator")

settings = render_sidebar()

pdf_file = st.file_uploader("1. Question Paper PDF", type=["pdf"])
template_file = st.file_uploader("2. Sample PPT Template", type=["pptx"])
answer_key_text = st.text_area("3. Answer key", placeholder="1: A\n2: B\n3: C")

def process_pipeline(app_settings, uploaded_pdf):
    gemini = GeminiService(api_key=app_settings["api_key"], model_name=app_settings["model_name"])
    
    with st.spinner("Rasterizing PDF to high-DPI images..."):
        pages = render_pdf(uploaded_pdf.read(), dpi=app_settings.get("render_dpi", 300))
    
    raw_questions = []
    total_columns = len(pages) * 2
    completed = 0
    
    progress = st.progress(0)
    status = st.empty()

    for p_idx, page in enumerate(pages):
        for c_idx, (col_img, off_x, off_y) in enumerate(split_page_columns(page, app_settings.get("outer_margin", 1.2), app_settings.get("column_gap", 1.5))):
            completed += 1
            progress.progress(completed / total_columns)
            status.text(f"Scanning Page {p_idx + 1}/{len(pages)}, Column {c_idx + 1}/2...")

            time.sleep(3.5) # Anti-Rate-Limit Delay

            detected = gemini.detect_column_items(col_img, app_settings["subjects"])
            for item in detected:
                try:
                    if item.get("type") == "question" and item.get("question_number"):
                        box = normalized_box_to_absolute(item["box_2d"], col_img.width, col_img.height, off_x, off_y)
                        raw_questions.append(DetectedItem(
                            kind="question", 
                            page_index=p_idx, 
                            column_index=c_idx, 
                            box=box,
                            question_number=int(item["question_number"]), 
                            confidence=item.get("confidence", 0.9)
                        ))
                except Exception:
                    continue
                
    progress.empty()
    status.empty()

    # De-duplicate questions (Keep the highest confidence detection)
    unique_questions = {}
    for q in raw_questions:
        if q.question_number not in unique_questions or q.confidence > unique_questions[q.question_number].confidence:
            unique_questions[q.question_number] = q
            
    # Sort strictly by Question Number, ignoring visual positions
    sorted_questions = sorted(unique_questions.values(), key=lambda x: x.question_number)

    grouped = {sub: [] for sub in app_settings["subjects"]}
    grouped["Unclassified"] = []
    
    status.text("Cropping and assigning subjects by boundaries...")
    for q in sorted_questions:
        # Enforce rigid Vidyapeeth subject boundaries
        sub = assign_subject_by_number(q.question_number, app_settings["exam_type"])
        
        try:
            img = crop_question(pages[q.page_index], q, app_settings.get("pad_x", 15), app_settings.get("pad_y", 10))
            if sub in grouped:
                grouped[sub].append({
                    "number": q.question_number, 
                    "image": img, 
                    "page_index": q.page_index
                })
            else:
                grouped["Unclassified"].append({
                    "number": q.question_number, 
                    "image": img, 
                    "page_index": q.page_index
                })
        except ValueError: 
            continue

    status.empty()
    return grouped


if st.button("🚀 Process & Generate", type="primary"):
    if not pdf_file or not template_file or not settings.get("api_key"):
        st.error("Upload required files and enter API key.")
        st.stop()

    try:
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
        error_msg = str(e.last_attempt.exception()) if e.last_attempt else "Unknown API Timeout"
        st.error(f"API Error: The Gemini API rejected the request after multiple retries. Details: {error_msg}")
    except Exception as e:
        st.error(f"Processing Failed: {str(e)}")
        st.exception(e)
