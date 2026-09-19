
import streamlit as st


def render_counts(subject_counts: dict[str, int]):
    st.subheader("Subject-wise question count")

    rows = [
        {
            "Subject": subject,
            "Questions": count,
        }
        for subject, count in subject_counts.items()
    ]

    st.table(rows)


def render_download(zip_path: str):
    with open(zip_path, "rb") as file:
        st.download_button(
            label="📦 Download All Subject PPTs",
            data=file,
            file_name="All_Subject_PPTs.zip",
            mime="application/zip",
        )
