import streamlit as st


def render_report(report):
    st.subheader("Quality report")
    cols = st.columns(4)
    cols[0].metric("Pages", report.pages)
    cols[1].metric("Questions", report.questions)
    cols[2].metric("Subjects", len(report.subject_counts))
    cols[3].metric("Needs review", len(report.low_confidence))
    st.json({
        "subject_counts": report.subject_counts,
        "warnings": report.warnings,
        "low_confidence": report.low_confidence,
        "missing_answers": report.missing_answers,
    })
