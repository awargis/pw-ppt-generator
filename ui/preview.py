import streamlit as st

def render_question_preview(subject_questions: dict):
    with st.expander("Preview Processed Questions (Dark Mode)"):
        for subject, questions in subject_questions.items():
            if not questions: continue
            st.markdown(f"### {subject}")
            cols = st.columns(min(3, len(questions)))
            for idx, q in enumerate(questions[:3]):
                with cols[idx]: st.image(q["image"], caption=f"Q{q['number']}", use_container_width=True)
