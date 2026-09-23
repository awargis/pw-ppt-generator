import streamlit as st

from config import STYLES


def render_sidebar():
    st.sidebar.markdown("## ⚙️ Production settings")
    exam_mode = st.sidebar.selectbox(
        "Exam paper mode",
        ["Auto-detect", "JEE Main", "NEET UG", "JEE Advanced"],
        index=0,
        help="Auto-detect is recommended for mixed/random uploads. You can explicitly select a mode when you already know the paper type.",
    )
    st.sidebar.caption(
        "The parser reads the uploaded paper's title, instructions, subject headings and question layout. "
        "Fixed ranges are used only for standard JEE Main/NEET structures."
    )
    dpi = st.sidebar.slider("Render quality (DPI)", 150, 360, 240, 15)
    pad_x = st.sidebar.slider("Crop safety margin", 0, 80, 18)
    pad_y = st.sidebar.slider("Top/boundary margin", 0, 60, 10)
    style = st.sidebar.selectbox("Image treatment", STYLES, index=0)
    use_ocr = st.sidebar.checkbox("OCR scanned pages automatically", value=True)
    transparent = st.sidebar.checkbox("Remove white page background", value=True)
    st.sidebar.caption("Native PDF text is always preferred. OCR is used only when native text is insufficient.")
    return {
        "subjects": [],
        "exam_mode": exam_mode,
        "pad_x": pad_x,
        "pad_y": pad_y,
        "render_dpi": dpi,
        "style": style,
        "use_ocr": use_ocr,
        "transparent_background": transparent,
    }
