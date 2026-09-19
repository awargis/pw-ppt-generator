import streamlit as st
from config import MODEL_CHOICES, get_subjects

def render_sidebar():
    st.sidebar.header("⚙️ Configuration")
    api_key = st.sidebar.text_input("Gemini API Key", type="password")
    model_name = st.sidebar.selectbox("Gemini Model", MODEL_CHOICES)
    exam_type = st.sidebar.selectbox("Exam Type", ["JEE Main / Advanced", "NEET"])
    
    st.sidebar.subheader("📐 Adjustable Crop Dimensions")
    pad_x = st.slider("Horizontal Padding (Left/Right)", 0, 40, 15)
    pad_y = st.slider("Vertical Padding (Top/Bottom)", 0, 40, 10)

    return {
        "api_key": api_key, "model_name": model_name, "exam_type": exam_type,
        "subjects": get_subjects(exam_type), "pad_x": pad_x, "pad_y": pad_y
    }
