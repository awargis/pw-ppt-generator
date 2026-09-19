
import streamlit as st


def render_question_preview(subject_questions: dict):
    with st.expander("Preview detected questions"):
        for subject, questions in subject_questions.items():
            if not questions:
                continue

            st.markdown(f"### {subject}")

            columns = st.columns(min(3, len(questions)))

            for index, question in enumerate(questions[:3]):
                with columns[index]:
                    st.image(
                        question["image"],
                        caption=f"Q{question['number']}",
                        use_container_width=True,
                    )
