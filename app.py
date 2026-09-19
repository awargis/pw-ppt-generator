import os
import streamlit as st
from pdf2image import convert_from_bytes

from services.answer_key_service import parse_answer_key_text
from services.crop_service import clip_neighbour_boxes, crop_question, normalized_box_to_absolute
from services.gemini_service import GeminiService
from services.output_service import create_subject_outputs
from services.pdf_service import render_pdf, split_page_columns
from services.ppt_service import build_subject_ppt
from services.subject_service import normalize_subject
from ui.preview import render_question_preview
from ui.report import render_counts, render_download
from ui.sidebar import render_sidebar
from models import BoundingBox, DetectedItem

st.set_page_config(page_title="PW Test PPT Generator", layout="wide")
st.title("📚 PW Test PPT Generator")

settings = render_sidebar()

pdf_file = st.file_uploader("1. Question Paper PDF", type=["pdf"])
template_file = st.file_uploader("2. Sample PPT Template", type=["pptx"])
answer_key_text = st.text_area("Answer key", placeholder="1: (3)\n2: (1)\n3: (4)")
answer_key_file = st.file_uploader("Optional answer key image/PDF", type=["png", "jpg", "jpeg", "pdf"])

def run_detection(pdf_bytes: bytes, gemini: GeminiService):
    pages = render_pdf(pdf_bytes, dpi=settings["render_dpi"])
    questions, headers = [], []
    total = len(pages) * 2
    progress, status = st.progress(0), st.empty()
    completed = 0

    for page_index, page in enumerate(pages):
        columns = split_page_columns(
            page,
            outer_margin_percent=settings["outer_margin"],
            column_gap_percent=settings["column_gap"],
        )

        for column_index, (column_image, offset_x, offset_y) in enumerate(columns):
            completed += 1
            progress.progress(min(completed / total, 1.0))
            status.text(f"Analyzing page {page_index + 1}/{len(pages)}, column {column_index + 1}/2")

            detected = gemini.detect_column_items(column_image, settings["subjects"])

            for item in detected:
                if not isinstance(item, dict): continue
                box_data = item.get("box_2d")
                if not isinstance(box_data, list) or len(box_data) != 4: continue

                try:
                    box = normalized_box_to_absolute(box_data, column_image.width, column_image.height, offset_x, offset_y)
                except Exception:
                    continue

                item_type = item.get("type")
                confidence = float(item.get("confidence", 0.8))

                if item_type == "question":
                    try:
                        question_number = int(item["question_number"])
                    except (KeyError, TypeError, ValueError):
                        continue

                    questions.append(DetectedItem(
                        kind="question", page_index=page_index, column_index=column_index,
                        box=box, question_number=question_number, confidence=confidence,
                        question_format=item.get("question_format", "unknown"),
                    ))

                elif item_type == "section_header":
                    if subject := normalize_subject(item.get("subject"), settings["subjects"]):
                        headers.append(DetectedItem(
                            kind="section_header", page_index=page_index, column_index=column_index,
                            box=box, subject=subject, confidence=confidence,
                        ))

    progress.empty()
    status.empty()

    if not questions:
        raise ValueError("No questions detected. Check the PDF quality, API key, or crop settings.")

    return pages, questions, headers

def build_question_groups(pages, questions, headers):
    grouped = {subject: [] for subject in settings["subjects"]}
    grouped["Unclassified"] = []

    questions.sort(key=lambda item: item.sort_key)
    headers.sort(key=lambda item: item.sort_key)

    current_subject = None
    header_index = 0

    for question in questions:
        while header_index < len(headers) and headers[header_index].sort_key <= question.sort_key:
            current_subject = headers[header_index].subject
            header_index += 1
        question.subject = current_subject

    columns = {}
    for question in questions:
        columns.setdefault((question.page_index, question.column_index), []).append(question)

    for items in columns.values():
        clip_neighbour_boxes(items)

    for question in questions:
        try:
            image = crop_question(pages[question.page_index], question, padding=settings["crop_padding"], invert=settings["invert_images"])
        except ValueError:
            continue

        subject = question.subject or "Unclassified"
        grouped.setdefault(subject, []).append({
            "number": question.question_number,
            "image": image,
            "page_index": question.page_index,
            "confidence": question.confidence,
            "question_format": question.question_format,
        })

    for subject in grouped:
        grouped[subject].sort(key=lambda item: item["number"])

    return grouped

if st.button("🚀 Process & Generate All Subject PPTs", type="primary"):
    if not pdf_file or not template_file or not settings["api_key"]:
        st.error("Please upload required files and enter your Gemini API key.")
        st.stop()

    try:
        gemini = GeminiService(api_key=settings["api_key"], model_name=settings["model_name"])
        answers = parse_answer_key_text(answer_key_text)

        if answer_key_file:
            if answer_key_file.type == "application/pdf":
                for page in convert_from_bytes(answer_key_file.read(), dpi=250):
                    answers.update(gemini.extract_answer_key(page))
            else:
                from PIL import Image
                answers.update(gemini.extract_answer_key(Image.open(answer_key_file)))

        pages, questions, headers = run_detection(pdf_file.read(), gemini)
        subject_questions = build_question_groups(pages, questions, headers)
        
        zip_path, output_files = create_subject_outputs(
            output_directory="output_processing",
            template_bytes=template_file.read(),
            subject_questions=subject_questions,
            answers=answers,
            build_ppt_function=build_subject_ppt,
        )

        subject_counts = {s: len(i) for s, i in subject_questions.items()}
        st.success("All PPT files were generated successfully.")

        render_counts(subject_counts)
        render_question_preview(subject_questions)
        render_download(zip_path)

    except Exception as error:
        st.error(f"Processing failed: {error}")
        st.exception(error)
