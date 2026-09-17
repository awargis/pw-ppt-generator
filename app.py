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
# PAGE SETUP & BRANDING
# ---------------------------------------------------------
st.set_page_config(page_title="PW Premium Test PPT Generator", page_icon="📚", layout="wide")
st.title("📚 PW Premium Question Paper to PPT Generator")
st.markdown("**Intelligent AI Cropping** • **Zero Text Clipping** • **1 Question Per Slide**")

# ---------------------------------------------------------
# SIDEBAR CONFIGURATION
# ---------------------------------------------------------
st.sidebar.header("⚙️ Configuration")
gemini_api_key = st.sidebar.text_input("Enter Gemini API Key:", type="password")
exam_type = st.sidebar.selectbox("Select Exam Type:", ["JEE Main / Advanced", "NEET"])

# Auto-set subjects based on exam type
if "JEE" in exam_type:
    subjects = ["Physics", "Chemistry", "Mathematics"]
    qs_per_sub = 25
else:
    subjects = ["Physics", "Chemistry", "Botany", "Zoology"]
    qs_per_sub = 45

st.sidebar.info(f"Target Folders: **{', '.join(subjects)}**\n\nQuestions per subject: **{qs_per_sub}**")

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
    """Parses answer key text into a dictionary."""
    ans_dict = {}
    if not text:
        return ans_dict
    matches = re.findall(r'(\d+)[\s:\-\.]+\(?([0-9\.\,A-Da-d]+)\)?', text)
    for q_num, ans in matches:
        ans_dict[int(q_num)] = ans.upper()
    return ans_dict

def detect_questions_with_gemini(client, image):
    """Uses AI strictly as a vertical ruler to find question height and column."""
    prompt = """
    Analyze this two-column exam paper. Identify every question.
    For each question, determine:
    1. Question number (q_num)
    2. Column ("left" or "right")
    3. ymin: Normalized vertical start (0-1000). Must start well ABOVE the question number to capture upper formulas.
    4. ymax: Normalized vertical end (0-1000). Must end well BELOW the last option to ensure nothing is cut off.

    Return ONLY a valid JSON list of objects. Example format:
    [
      {"q_num": 1, "col": "left", "ymin": 50, "ymax": 250},
      {"q_num": 2, "col": "right", "ymin": 260, "ymax": 400}
    ]
    Do not include any markdown formatting or backticks.
    """
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[image, prompt]
        )
        cleaned_json = re.sub(r'```(?:json)?\n?', '', response.text).replace('```', '').strip()
        return json.loads(cleaned_json)
    except Exception as e:
        return []

def crop_with_smart_padding(page_img, item):
    """Crops the image taking the FULL width of the column to avoid horizontal clipping."""
    w, h = page_img.size
    
    ymin = item.get("ymin", 0)
    ymax = item.get("ymax", 1000)
    col = item.get("col", "left").lower()

    # Convert normalized 0-1000 scale to actual pixels
    px_ymin = int((ymin / 1000.0) * h)
    px_ymax = int((ymax / 1000.0) * h)

    # 1. Generous Vertical Padding (Ensures tall formulas/options stay intact)
    px_ymin = max(0, px_ymin - 40)
    px_ymax = min(h, px_ymax + 45)

    # 2. Hardcoded Horizontal Boundaries for 2-Column PDF
    mid_x = w // 2
    margin = int(w * 0.035)  # 3.5% outer page margin
    center_gap = int(w * 0.015) # 1.5% gap from the center line

    if col == "left":
        px_xmin = margin
        px_xmax = mid_x - center_gap
    else:
        px_xmin = mid_x + center_gap
        px_xmax = w - margin

    return page_img.crop((px_xmin, px_ymin, px_xmax, px_ymax))

def create_subject_ppt(template_bytes, questions_dict, answers_dict, subject_name, output_path):
    """Generates the actual PPTX file for a specific subject."""
    prs = Presentation(io.BytesIO(template_bytes))
    # Try to use a blank layout
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
        
        # Insert Premium 24pt Bold Answer Key badge
        if q_no in answers_dict:
            txBox = slide.shapes.add_textbox(Inches(7.0), Inches(6.5), Inches(2.5), Inches(0.8))
            tf = txBox.text_frame
            p = tf.paragraphs[0]
            p.text = f"Ans. ({answers_dict[q_no]})"
            p.font.size = Pt(28) # Slightly larger for maximum visibility
            p.font.bold = True
            p.font.color.rgb = RGBColor(255, 215, 0) # PW Yellow/Gold

        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)

    prs.save(output_path)

# ---------------------------------------------------------
# MAIN UI & EXECUTION LOGIC
# ---------------------------------------------------------
col1, col2 = st.columns(2)
with col1:
    pdf_file = st.file_uploader("1. Upload Question Paper (PDF)", type=["pdf"])
with col2:
    template_ppt = st.file_uploader("2. Upload Sample PPT Template (.pptx)", type=["pptx"])

ans_key_text = st.text_area("3. Paste Answer Key (Optional)", placeholder="Example: 1: (4), 2: (4), 3: (2)...", height=100)

if st.button("🚀 Generate Perfect PW PPTs", use_container_width=True):
    if not pdf_file or not template_ppt:
        st.error("⚠️ Please upload both the PDF and the PPT template!")
    elif not gemini_api_key:
        st.error("⚠️ Please enter your Gemini API Key in the sidebar!")
    else:
        try:
            with st.spinner("🤖 AI is reading the paper, analyzing columns, and cropping smartly... This takes 1-2 minutes."):
                ans_dict = parse_answer_key(ans_key_text)
                
                # Setup clean working directory
                work_dir = "output_processing"
                if os.path.exists(work_dir):
                    shutil.rmtree(work_dir)
                os.makedirs(work_dir)

                for sub in subjects:
                    os.makedirs(os.path.join(work_dir, sub), exist_ok=True)

                # Convert PDF to high-res images (DPI 300 for crisp text)
                pages = convert_from_bytes(pdf_file.read(), dpi=300)
                ppt_bytes = template_ppt.read()
                client = genai.Client(api_key=gemini_api_key)
                
                all_cropped_questions = {}

                # Process each page
                for p_idx, page_img in enumerate(pages):
                    # Skip cover page and instructions (Page 0)
                    if p_idx < 1:
                        continue
                        
                    detected_list = detect_questions_with_gemini(client, page_img)
                    
                    if not detected_list:
                        continue # AI couldn't read this page, skip to next
                        
                    for item in detected_list:
                        try:
                            q_num = int(item["q_num"])
                            # Smart Column Crop
                            cropped_img = crop_with_smart_padding(page_img, item)
                            # Apply Premium Dark Mode
                            dark_img = invert_to_black_bg(cropped_img)
                            all_cropped_questions[q_num] = dark_img
                        except Exception as e:
                            # If a single question fails, don't crash the whole app
                            continue

                if not all_cropped_questions:
                    st.error("❌ AI could not detect any questions. Please check the PDF format.")
                    st.stop()

                # Divide into subjects automatically
                for sub_idx, sub in enumerate(subjects):
                    sub_folder = os.path.join(work_dir, sub)
                    start_q = sub_idx * qs_per_sub + 1
                    end_q = start_q + qs_per_sub
                    
                    # Filter questions belonging to this subject
                    sub_q_dict = {q: all_cropped_questions[q] for q in range(start_q, end_q) if q in all_cropped_questions}

                    if sub_q_dict:
                        ppt_out_path = os.path.join(sub_folder, f"{sub}_PW_Discussion.pptx")
                        create_subject_ppt(ppt_bytes, sub_q_dict, ans_dict, sub, ppt_out_path)

                # Zip the folders for download
                zip_filename = "PW_Subject_PPTs.zip"
                shutil.make_archive("PW_Subject_PPTs", 'zip', work_dir)

                st.success("🎉 Success! PPTs created with exact question cropping and zero line clips!")
                
                with open(zip_filename, "rb") as fp:
                    st.download_button(
                        label="📦 Download Full PPT Package (ZIP)", 
                        data=fp, 
                        file_name=zip_filename, 
                        mime="application/zip",
                        use_container_width=True
                    )

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
