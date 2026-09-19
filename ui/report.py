import streamlit as st

def render_counts(subject_counts: dict[str, int]):
    st.subheader("Subject-wise question count")
    st.table([{"Subject": s, "Questions": c} for s, c in subject_counts.items()])
