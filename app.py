import io
import os
import re
import json
import shutil
import streamlit as st
from PIL import Image, ImageOps, ImageEnhance
from pdf2image import convert_from_bytes
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from google import genai

# ---------------------------------------------------------
# PAGE SETUP
# ---------------------------------------------------------
st.set_page_config(page_title="PW Premium Test PPT Generator", layout="wide")
st.title("📚 PW Premium Question Paper to PPT Generator")

# ---------------------------------------------------------
# SIDEBAR CONFIGURATION
# ---------------------------------------------------------
st.sidebar.header("⚙️ Configuration")
gemini_api_key = st.sidebar.text_input("Enter Gemini API Key:", type="password")
exam_type = st.sidebar.selectbox("Select Exam Type:", ["JEE Main / Advanced", "NEET"])

subjects = ["Physics", "Chemistry", "Mathematics"] if "JEE" in exam_type else ["Physics", "Chemistry", "Botany", "Zoology"]
st.sidebar.info(f"Target Folders: **{', '.join(subjects)}**")

# ---------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------

def invert_to_black_bg(pil_img):
    """Converts question snippet to PW Dark Mode with enhanced contrast."""
    rgb_img = pil_img.convert("RGB")
    inverted_img = ImageOps.invert(rgb_img)
    enhancer = ImageEnhance.Contrast(inverted_img)
    return enhancer.enhance(1.6)

def parse_answer_key(text):
    ans_dict = {}
    if not text:
        return ans_dict
    matches = re.findall(r'(\d+)[\s:\-\.]+\(?([0-9\.\,A-Da-d]+)\)?', text)
    for q_num, ans in matches:
        ans_dict[int(q_num)] = ans.upper()
    return ans_dict

def detect_questions_with_gemini(client, image):
    """Detects bounding boxes with Gemini Vision API."""
    prompt = """
    Analyze this exam paper page. Identify each question along with its full statement, formulas, diagrams, and options (1-4 or A-D).
    Return ONLY a valid JSON list of objects:
    [
      {"q_num": 1, "box": [ymin, xmin, ymax, xmax]}
    ]
    Coordinates MUST be normalized between 0 and 1000. Ensure ymin starts BEFORE the question number, and ymax ends AFTER the last option line.
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

def crop_with_smart_padding(page_img, box):
    """Crops question with strict column boundaries and top/bottom vertical padding."""
    w, h = page_img.size
    ymin, xmin, ymax, xmax = box

    # Convert 0-1000 scale to pixels
    px_ymin = int((ymin / 1000.0) * h)
    px_xmin = int((xmin / 1000.0) * w)
    px_ymax = int((ymax / 1000.0) * h)
    px_xmax = int((xmax / 1000.0) * w)

    # 1. Smart Dynamic Padding (Adds 25px safety margin top & bottom to avoid line clipping)
    pad_top = 25
    pad_bottom = 20
    
    px_ymin = max(0, px_ymin - pad_top)
    px_ymax = min(h, px_ymax + pad_bottom)

    # 2. Enforce Strict Column Separation (PW papers have 2 columns split at 50% width)
    mid_x = w // 2
    if px_xmin < mid_x:
        # Left Column: Lock boundaries within left page area
        px_xmin = max(0, int(w * 0.02))
        px_xmax = min(mid_x - 10, px_xmax + 15)
    else:
        # Right Column: Lock boundaries within right page area
        px_xmin = max(mid_x + 10, px_xmin - 15)
        px_xmax = min(w - int(w * 0.02), px_xmax + 15)

    cropped = page_img.crop((px_xmin, px_ymin, px_xmax, px_ymax))
    return cropped

def create_subject_ppt(template_bytes, questions_dict, answers_dict, subject_name, output_path):
    prs = Presentation(io.BytesIO(template_bytes))
    blank_layout = prs.slide_layouts[6] if len(prs.slide_layouts) > 6 else prs.slide_layouts[0]

    for q_no in sorted(questions_dict.keys()):
        q_img = questions_dict[q_no]
        slide = prs.slides.add_slide(blank_layout)
        
        temp_img_path = f"temp_{subject_name}_{q_no}.png"
        q_img.save(temp_img_path)
        
        # Position question cleanly centered on slide
        left = Inches(0.8)
        top = Inches(1.0)
        width = Inches(8.4)
        slide.shapes.add_picture(temp_img_path, left, top, width=width)
        
        # Insert 24pt Bold Answer Key badge
        if q_no in answers_dict:
            txBox = slide.shapes.add_textbox(Inches(6.5), Inches(6.8), Inches(3.0), Inches(0.6))
            tf = txBox.text_frame
            p = tf.paragraphs[0]
            p.text = f"Ans. ({answers_dict[q_no]})"
            p.font.size = Pt(24)
            p.font.bold = True
            p.font.color.rgb = RGBColor(255, 215, 0) # PW Yellow/Gold

        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)

    prs.save(output_path)

# ---------------------------------------------------------
# UI & EXECUTION
# ---------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    pdf_file = st.file_uploader("1. Upload Question Paper (PDF)", type=["pdf"])
with col2:
    template_ppt = st.file_uploader("2. Upload Sample PPT Template (.pptx)", type=["pptx"])

ans_key_text = st.text_area("3. Paste Answer Key", placeholder="1: (4), 2: (4), 3: (2)...", height=100)

if st.button("🚀 Generate Perfect PW PPTs"):
    if not pdf_file or not template_ppt or not gemini_api_key:
        st.error("⚠️ Please fill in all inputs and enter your Gemini API Key!")
    else:
        try:
            with st.spinner("Processing PDF with Smart Column & Height Padding..."):
                ans_dict = parse_answer_key(ans_key_text)
                
                work_dir = "output_processing"
                if os.path.exists(work_dir):
                    shutil.rmtree(work_dir)
                os.makedirs(work_dir)

                for sub in subjects:
                    os.makedirs(os.path.join(work_dir, sub), exist_ok=True)

                pages = convert_from_bytes(pdf_file.read(), dpi=250) # Increased DPI for sharper OCR
                ppt_bytes = template_ppt.read()
                client = genai.Client(api_key=gemini_api_key)
                
                all_cropped_questions = {}

                for p_idx, page_img in enumerate(pages):
                    # Skip cover and instruction pages (Pages 1 & 2)
                    if p_idx < 1:
                        continue
                        
                    detected_list = detect_questions_with_gemini(client, page_img)
                    
                    for item in detected_list:
                        try:
                            q_num = int(item["q_num"])
                            cropped_img = crop_with_smart_padding(page_img, item["box"])
                            dark_img = invert_to_black_bg(cropped_img)
                            all_cropped_questions[q_num] = dark_img
                        except Exception:
                            continue

                # Divide into subjects (25 questions per subject for JEE / 45 for NEET)
                qs_per_sub = 25 if "JEE" in exam_type else 45
                for sub_idx, sub in enumerate(subjects):
                    sub_folder = os.path.join(work_dir, sub)
                    start_q = sub_idx * qs_per_sub + 1
                    end_q = start_q + qs_per_sub
                    
                    sub_q_dict = {q: all_cropped_questions[q] for q in range(start_q, end_q) if q in all_cropped_questions}

                    ppt_out_path = os.path.join(sub_folder, f"{sub}_PW_Discussion.pptx")
                    create_subject_ppt(ppt_bytes, sub_q_dict, ans_dict, sub, ppt_out_path)

                zip_filename = "PW_Subject_PPTs.zip"
                shutil.make_archive("PW_Subject_PPTs", 'zip', work_dir)

                st.success("🎉 PPTs created with exact question cropping and zero line clips!")
                with open(zip_filename, "rb") as fp:
                    st.download_button("📦 Download PW PPT Package (ZIP)", fp, file_name=zip_filename, mime="application/zip")

        except Exception as e:
            st.error(f"Error: {str(e)}")
