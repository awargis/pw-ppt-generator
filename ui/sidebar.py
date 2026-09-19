
import streamlit as st

from config import MODEL_CHOICES, get_subjects


def render_sidebar():
    st.sidebar.header("⚙️ Configuration")

    api_key = st.sidebar.text_input(
        "Gemini API Key",
        type="password",
    )

    model_name = st.sidebar.selectbox(
        "Gemini Model",
        MODEL_CHOICES,
    )

    exam_type = st.sidebar.selectbox(
        "Exam Type",
        ["JEE Main / Advanced", "NEET"],
    )

    subjects = get_subjects(exam_type)

    st.sidebar.info(
        f"Expected subjects: {', '.join(subjects)}"
    )

    with st.sidebar.expander("Advanced"):
        render_dpi = st.slider(
            "PDF render DPI",
            200,
            400,
            300,
            step=50,
        )

        crop_padding = st.slider(
            "Crop padding",
            5,
            40,
            18,
        )

        column_gap = st.slider(
            "Column gap (%)",
            0.5,
            4.0,
            1.5,
            step=0.5,
        )

        outer_margin = st.slider(
            "Outer page margin (%)",
            0.0,
            3.0,
            1.2,
            step=0.2,
        )

        invert_images = st.checkbox(
            "Invert images",
            value=False,
        )

    return {
        "api_key": api_key,
        "model_name": model_name,
        "exam_type": exam_type,
        "subjects": subjects,
        "render_dpi": render_dpi,
        "crop_padding": crop_padding,
        "column_gap": column_gap,
        "outer_margin": outer_margin,
        "invert_images": invert_images,
    }
