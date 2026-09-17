import streamlit as st
import io
import zipfile
from core_engine import extract_questions_from_pdf, parse_answer_key, build_subject_ppts

st.set_page_config(page_title="PW DTP Automation Engine", page_icon="⚡", layout="wide")

st.title("⚡ Question Paper to PPT Engine")
st.markdown("**Deterministic PDF Geometry** • **Watermark Removal** • **1 Question Per Slide**")

col1, col2 = st.columns(2)
with col1:
    pdf_file = st.file_uploader("1. Upload Question Paper (PDF)", type=["pdf"])
with col2:
    template_file = st.file_uploader("2. Upload Master PPT Template (.pptx)", type=["pptx"])

ans_key_raw = st.text_area("3. Paste Answer Key (Optional)", placeholder="1: A, 2: C, 3: B...", height=100)
exam_type = st.radio("Select Exam Type:", ["JEE (75 Qs: Phy/Chem/Math)", "NEET (180 Qs: Phy/Chem/Bot/Zoo)"], horizontal=True)

if st.button("🚀 Generate Presentation Deck", use_container_width=True):
    if not pdf_file or not template_file:
        st.error("⚠️ Please upload both the PDF paper and the PPT template!")
    else:
        with st.spinner("Processing PDF native coordinates, cropping diagrams, and removing watermarks..."):
            pdf_bytes = pdf_file.read()
            template_bytes = template_file.read()
            ans_dict = parse_answer_key(ans_key_raw)

            # 1. Extract Questions via PyMuPDF Vector Engine
            questions_dict = extract_questions_from_pdf(pdf_bytes)

            if not questions_dict:
                st.error("❌ No structured questions were detected. Please check PDF layout.")
            else:
                st.success(f"✅ Successfully extracted {len(questions_dict)} questions with zero text clipping!")

                # 2. Build PPT Decks
                output_ppts = build_subject_ppts(template_bytes, questions_dict, ans_dict, exam_type)

                # 3. Package into ZIP
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                    for sub_name, ppt_bytes in output_ppts.items():
                        zip_file.writestr(f"{sub_name}/{sub_name}_Discussion.pptx", ppt_bytes)

                zip_buffer.seek(0)

                st.download_button(
                    label="📦 Download All Subject PPTs (ZIP)",
                    data=zip_buffer,
                    file_name="PW_Subject_PPTs.zip",
                    mime="application/zip",
                    use_container_width=True
                )
