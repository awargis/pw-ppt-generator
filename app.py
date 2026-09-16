import os
import io
import re
import json
import zipfile
import shutil
import tempfile
import numpy as np
import cv2
import streamlit as st
from pdf2image import convert_from_bytes
from PIL import Image, ImageOps, ImageEnhance
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
import google.generativeai as genai

# Page Config
st.set_page_config(
    page_title="Auto Question Paper to PPT Generator",
    page_icon="📚",
    layout="wide"
)

# Custom Styling
st.markdown("""
    <style>
    .main-title { font-size: 28px; font-weight: bold; color: #FF4B4B; }
    .stButton>button { background-color: #4CAF50; color: white; font-weight: bold; font-size: 18px; border-radius: 8px; width: 100%; height: 50px;}
    </style>
""", unsafe_allow_html=True)

st.title("📚 Automated Question Paper to Subject PPT Generator")
st.write("PDF Upload karein, Sample PPT Template dein aur 1-Click me Subject-wise Dark Mode PPTs download karein!")

# Sidebar Configuration
st.sidebar.header("⚙️ Configuration Settings")

# Exam Type Selection
exam_type = st.sidebar.radio(
    "1. Select Exam Type",
    ["JEE (3 Subjects)", "NEET (4 Subjects)"],
    index=0
)

if "JEE" in exam_type:
    subjects = ["Physics", "Chemistry", "Mathematics"]
else:
    subjects = ["Physics", "Chemistry", "Botany", "Zoology"]

st.sidebar.info(f"📁 Folders/PPTs Created: **{', '.join(subjects)}**")

# Gemini API Key (Optional for precise AI cropping)
gemini_api_key = st.sidebar.text_input("Google Gemini API Key (Optional for AI OCR)", type="password", help="Agar API Key hai toh daalein, warna Smart Contour Cropper automatically kaam karega.")

# File Uploaders
st.sidebar.subheader("2. Upload Files")
pdf_file = st.sidebar.file_uploader("Upload Question Paper (PDF)", type=["pdf"])
template_ppt = st.sidebar.file_uploader("Upload Sample PPT Template (.pptx)", type=["pptx"])

# Answer Key Section
st.subheader("📝 Answer Key Input")
ans_key_text = st.text_area(
    "Paste Answer Key here (Format: 1:A, 2:C, 3:2, 4:4 or line by line)",
    height=120,
    placeholder="1: 2\n2: 4\n3: 1\n4: 3\n..."
)

# Parse Answer Key
answer_dict = {}
if ans_key_text:
    matches = re.findall(r'(\d+)[\s:\-\.]+\(?([1-4A-Da-d]+)\)?', ans_key_text)
    for q_num, ans in matches:
        answer_dict[int(q_num)] = ans.upper()

# Helper Functions
def invert_to_black_bg(pil_img):
    """ Converts cropped image to Black Background with Crisp White Text """
    if pil_img.mode != 'RGB':
        pil_img = pil_img.convert('RGB')
    
    # Invert colors (White -> Black, Black -> White)
    inverted = ImageOps.invert(pil_img)
    
    # Enhance contrast and sharpness
    enhancer_c = ImageEnhance.Contrast(inverted)
    inverted = enhancer_c.enhance(1.8)
    
    enhancer_b = ImageEnhance.Brightness(inverted)
    inverted = enhancer_b.enhance(1.1)
    
    return inverted

def auto_crop_questions_opencv(page_img):
    """ Smart OpenCV Whitespace Segmentation for Cropping Questions """
    cv_img = cv2.cvtColor(np.array(page_img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    
    # Thresholding
    _, thresh = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY_INV)
    
    # Horizontal projection profile to find question breaks
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (cv_img.shape[1], 15))
    dilated = cv2.dilate(thresh, kernel, iterations=2)
    
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    crops = []
    h_img, w_img, _ = cv_img.shape
    
    boxes = [cv2.boundingRect(c) for c in contours]
    # Sort top-to-bottom
    boxes = sorted(boxes, key=lambda b: b[1])
    
    for x, y, w, h in boxes:
        if h > 80 and w > w_img * 0.3: # Filter tiny text lines or header noise
            crop = page_img.crop((x, y, x + w, y + h))
            crops.append(crop)
            
    return crops if crops else [page_img]

def get_gemini_question_boxes(page_img, api_key):
    """ Uses Gemini Vision API to detect exact question bounding boxes """
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = """
        Detect all question numbers and their exact bounding boxes on this page.
        Return ONLY a JSON array like this:
        [
          {"q_num": 1, "box_2d": [ymin, xmin, ymax, xmax]},
          ...
        ]
        Box coordinates should be normalized from 0 to 1000. Do not include markdown code block syntax.
        """
        
        response = model.generate_content([prompt, page_img])
        clean_text = response.text.replace("```json", "").replace("
