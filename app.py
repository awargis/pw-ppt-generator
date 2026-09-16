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
from pptx.dml.color import RGBColor
from google import genai
from google.genai import types

# ---------------------------------------------------------
# PAGE SETUP
# ---------------------------------------------------------
st.set_page_config(page_title="PW Premium Test PPT Generator", layout="wide")

st.title("📚 PW Premium Question Paper to PPT Generator")
st.write("Smart OCR Bounding Box Cropping — 1 Question Per Slide with High Contrast Dark Mode.")

# ---------------------------------------------------------
# SIDEBAR CONFIGURATION
# ---------------------------------------------------------
st.sidebar.header("⚙️ Configuration")

gemini_api_key = st.sidebar.text_input("Enter Gemini API Key:", type="password")
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
    """Converts question snippet to PW Dark Mode (High-contrast white text on black background)"""
    rgb_img = pil_img.convert("RGB")
    inverted_img = ImageOps.invert(rgb_img)
    enhancer = ImageEnhance.Contrast(inverted_img)
    return enhancer.enhance(1.5)

def parse_answer_key(text):
    """Parses answer key formats like '1: (3), 2:(1)' or line-by-line"""
    ans_dict = {}
    if not text:
        return ans_dict
    matches = re.findall(r'(\d+)[\s:\-\.]+\(?([0-9\.\,A-Da-d]+)\)?', text)
    for q_num, ans in matches:
        ans_dict[int(q_num)] = ans.upper()
    return ans_dict

def detect_questions_with_gemini(client, image):
    """Uses Gemini Vision API to detect exact question bounding boxes [ymin, xmin, ymax, xmax]"""
    prompt = """
    Analyze this question paper page image. Detect every distinct question (including options, diagrams, and question numbers).
    Return ONLY a valid JSON list of objects with no markdown code blocks, using this format:
    [
      {"q_num": 1, "box": [ymin, xmin, ymax, xmax]},
      {"q_num": 2, "box": [ymin, xmin, ymax, xmax]}
    ]
    Where coordinates are normalized from 0 to 1000.
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image, prompt]
        )
        cleaned_json = re.sub(r'```(?:json)?\n?', '', response.text).replace('```', '').strip()
        return json.loads(cleaned_json)
    except Exception:
        return []

def create_subject_ppt(template_bytes, questions_dict, answers_dict, subject_name, output_path):
    """Builds premium PPT slides with 1 Question per slide and 24pt bold answer keys"""
    prs = Presentation(io.BytesIO(template_bytes))
    blank_layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[0]

    for q_no in sorted(questions_dict.keys()):
        q_img = questions_dict[q_no]
        slide = prs.slides.add_slide(blank_layout)
        
        # Save temporary cropped dark image
        temp_img_path = f"temp_{subject_name}_{q_no}.png"
        q_img.save(temp_img_path)
        
        # Insert image centered with fixed width/proportions
        left = Inches(0.8)
        top = Inches(1.2)
        width = Inches(8.4)
        slide.shapes.add_picture(temp_img_path, left, top, width=width)
        
        # Insert Answer Key Badge at Bottom Right with 24pt Font
        if q_no in answers_dict:
            txBox = slide.shapes.add_textbox(Inches(6.5), Inches(6.8), Inches(3.0), Inches(0.6))
            tf = txBox.text_frame
            p = tf.paragraphs[0]
            p.text = f"Ans. ({answers_dict[q_no]})"
            p.font.size = Pt(24)
            p.font.bold = True
            p.font.color.rgb = RGBColor(255, 215, 0)  # PW Premium Gold/Yellow Text Color

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
    "3. Paste Answer Key",
    placeholder="Example: 1: (4), 2: (4), 3: (2), 4: (3)...",
    height=120
)

# ---------------------------------------------------------
# PROCESSING PIPELINE
# ---------------------------------------------------------
if st.button("🚀 Generate PW Premium PPTs"):
    if not pdf_file or not template_ppt:
        st.error("⚠️ Please upload both the PDF Question Paper and PPT Template!")
    elif not gemini_api_key:
        st.error("⚠️ Enter your Gemini API Key in the sidebar!")
    else:
        try:
            with st.spinner("Processing PDF, detecting exact question coordinates via Gemini Vision OCR..."):
                
                ans_dict = parse_answer_key(ans_key_text)
                
                work_dir = "output_processing"
                if os.path.exists(work_dir):
                    shutil.rmtree(work_dir)
                os.makedirs(work_dir)

                for sub in subjects:
                    os.makedirs(os.path.join(work_dir, sub), exist_ok=True)

                pdf_bytes = pdf_file.read()
                ppt_bytes = template_ppt.read()
                pages = convert_from_bytes(pdf_bytes, dpi=200)

                client = genai.Client(api_key=gemini_api_key)
                
                all_cropped_questions = {}

                # Smart OCR Box Extraction
                for p_idx, page_img in enumerate(pages):
                    w, h = page_img.size
                    detected_list = detect_questions_with_gemini(client, page_img)
                    
                    for item in detected_list:
                        try:
                            q_num = int(item["q_num"])
                            ymin, xmin, ymax, xmax = item["box"]
                            
                            # Normalize coordinates (0-1000 scale to pixels)
                            crop_box = (
                                int((xmin / 1000.0) * w),
                                int((ymin / 1000.0) * h),
                                int((xmax / 1000.0) * w),
                                int((ymax / 1000.0) * h)
                            )
                            
                            cropped_img = page_img.crop(crop_box)
                            dark_img = invert_to_black_bg(cropped_img)
                            all_cropped_questions[q_num] = dark_img
                        except Exception:
                            continue

                # Divide detected questions into subject folders based on exam type
                total_qs = len(all_cropped_questions) or 75
                qs_per_subject = total_qs // len(subjects)

                for sub_idx, sub in enumerate(subjects):
                    sub_folder = os.path.join(work_dir, sub)
                    start_q = sub_idx * qs_per_subject + 1
                    end_q = start_q + qs_per_subject
                    
                    sub_q_dict = {q: all_cropped_questions[q] for q in range(start_q, end_q) if q in all_cropped_questions}

                    ppt_out_path = os.path.join(sub_folder, f"{sub}_PW_Discussion.pptx")
                    create_subject_ppt(ppt_bytes, sub_q_dict, ans_dict, sub, ppt_out_path)

                # Create ZIP File
                zip_filename = "PW_Subject_PPTs.zip"
                shutil.make_archive("PW_Subject_PPTs", 'zip', work_dir)

                st.success("🎉 All Subject PPTs generated with smart bounding boxes and 24pt formatting!")

                with open(zip_filename, "rb") as fp:
                    st.download_button(
                        label="📦 One-Click Download PW PPT Package (ZIP)",
                        data=fp,
                        file_name=zip_filename,
                        mime="application/zip"
                    )

        except Exception as e:
            st.error(f"Execution Error: {str(e)}")
