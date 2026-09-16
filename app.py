import io
import os
import re
import json
import zipfile
import shutil
import streamlit as st
from PIL import Image, ImageOps, ImageEnhance
from pdf2image import convert_from_bytes
from pptx import Presentation
from pptx.util import Inches, Pt
from google import genai
from google.genai import types

# ---------------------------------------------------------
# PAGE SETUP
# ---------------------------------------------------------
st.set_page_config(page_title="PW Test PPT Generator", layout="wide")

st.title("📚 Automated Question Paper to PPT Generator")
st.write("PDF Question Paper upload karein, Subject-wise PPTs download karein!")

# ---------------------------------------------------------
# SIDEBAR CONFIGURATION
# ---------------------------------------------------------
st.sidebar.header("⚙️ Configuration")

# Gemini API Key Input
gemini_api_key = st.sidebar.text_input("Enter Gemini API Key:", type="password")

# Exam Selection
exam_type = st.sidebar.selectbox("Select Exam Type:", ["JEE Main / Advanced", "NEET"])

if "JEE" in exam_type:
    subjects = ["Physics", "Chemistry", "Mathematics"]
else:
    subjects = ["Physics", "Chemistry", "Botany", "Zoology"]

st.sidebar.info(f"Target Folders: **{', '.join(subjects)}**")

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

def invert_to_black_bg(pil_img):
    """Image ko Dark Mode (Black BG, White Text) me convert karta hai"""
    rgb_img = pil_img.convert("RGB")
    inverted_img = ImageOps.invert(rgb_img)
    enhancer = ImageEnhance.Contrast(inverted_img)
    return enhancer.enhance(1.4)

def parse_answer_key(text):
    """Answer key text parsing logic"""
    ans_dict = {}
    if not text:
        return ans_dict
    matches = re.findall(r'(\d+)[\s:\-\.]+\(?([1-4A-Da-d]+)\)?', text)
    for q_num, ans in matches:
        ans_dict[int(q_num)] = ans.upper()
    return ans_dict

def create_subject_ppt(template_bytes, questions_dict, answers_dict, subject_name, output_path):
    """Sample PPT Template me questions & answers fill karta hai"""
    prs = Presentation(io.BytesIO(template_bytes))
    
    # Template ki slide layout choose karein
    slide_layout = prs.slide_layouts[0] if len(prs.slide_layouts) > 0 else prs.slide_layouts[0]

    for q_no in sorted(questions_dict.keys()):
        q_img = questions_dict[q_no]
        slide = prs.slides.add_slide(slide_layout)
        
        # Temp image save
        temp_img_path = f"temp_{subject_name}_{q_no}.png"
        q_img.save(temp_img_path)
        
        # Image slide par add karein
        left = Inches(0.8)
        top = Inches(1.8)
        width = Inches(8.4)
        slide.shapes.add_picture(temp_img_path, left, top, width=width)
        
        # Answer Box Add karein
        if q_no in answers_dict:
            txBox = slide.shapes.add_textbox(Inches(1.0), Inches(6.5), Inches(4.0), Inches(0.8))
            tf = txBox.text_frame
            p = tf.paragraphs[0]
            p.text = f"Ans. ({answers_dict[q_no]})"
            p.font.size = Pt(24)
            p.font.bold = True

        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)

    prs.save(output_path)

# ---------------------------------------------------------
# MAIN UPLOAD INTERFACE
# ---------------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    pdf_file = st.file_uploader("1. Upload Question Paper (PDF)", type=["pdf"])

with col2:
    template_ppt = st.file_uploader("2. Upload Sample PPT Template (.pptx)", type=["pptx"])

ans_key_text = st.text_area(
    "3. Paste Answer Key (Optional)",
    placeholder="Example:\n1: (3)\n2: (1)\n3: (4)...",
    height=150
)

# ---------------------------------------------------------
# PROCESSING & GENERATION
# ---------------------------------------------------------
if st.button("🚀 Process & Generate All Subject PPTs"):
    if not pdf_file or not template_ppt:
        st.error("⚠️ Kripya Question Paper PDF aur Sample PPT Template dono upload karein!")
    elif not gemini_api_key:
        st.error("⚠️ Sidebar me Gemini API Key daalna zaroori hai!")
    else:
        try:
            with st.spinner("PDF Pages process ho rahe hain aur Dark Mode PPT ban rahi hai..."):
                
                # Answer Key Parse
                ans_dict = parse_answer_key(ans_key_text)
                
                # Setup Directories
                work_dir = "output_processing"
                if os.path.exists(work_dir):
                    shutil.rmtree(work_dir)
                os.makedirs(work_dir)

                for sub in subjects:
                    os.makedirs(os.path.join(work_dir, sub), exist_ok=True)

                # PDF to Image conversion
                pdf_bytes = pdf_file.read()
                ppt_bytes = template_ppt.read()
                pages = convert_from_bytes(pdf_bytes, dpi=200)

                # Prepare Gemini Client
                client = genai.Client(api_key=gemini_api_key)

                # Simple Page-based crop logic & Subject splitting
                total_pages = len(pages)
                questions_per_sub = 25  # Standard section size
                
                for sub_idx, sub in enumerate(subjects):
                    sub_folder = os.path.join(work_dir, sub)
                    cropped_questions = {}

                    start_q = sub_idx * questions_per_sub + 1
                    end_q = start_q + questions_per_sub

                    for q in range(start_q, end_q):
                        # Calculate rough page index
                        page_idx = min((q - 1) // 10, total_pages - 1)
                        page_img = pages[page_idx]

                        # Bounding Box Crop (Top-to-Bottom Slice)
                        w, h = page_img.size
                        crop_box = (int(w * 0.05), int(h * 0.12), int(w * 0.95), int(h * 0.45))
                        q_crop = page_img.crop(crop_box)

                        # Convert to Black BG White Text
                        dark_mode_q = invert_to_black_bg(q_crop)
                        cropped_questions[q] = dark_mode_q

                    # PPT Create karein
                    ppt_out_path = os.path.join(sub_folder, f"{sub}_Discussion.pptx")
                    create_subject_ppt(ppt_bytes, cropped_questions, ans_dict, sub, ppt_out_path)

                # Create ZIP for Download
                zip_filename = "All_Subject_PPTs.zip"
                shutil.make_archive("All_Subject_PPTs", 'zip', work_dir)

                st.success("🎉 Sabhi Subject PPTs successfully generate ho gayi hain!")

                # Download Button
                with open(zip_filename, "rb") as fp:
                    st.download_button(
                        label="📦 One-Click Download All PPTs (ZIP)",
                        data=fp,
                        file_name=zip_filename,
                        mime="application/zip"
                    )

        except Exception as e:
            st.error(f"Error aaya hai: {str(e)}")
