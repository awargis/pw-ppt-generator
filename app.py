"""
PW Test PPT Generator — Automated Question Paper → Subject-wise PPT Discussion Decks
=====================================================================================

WHAT THIS FIXES vs the previous version
----------------------------------------
1. ONE QUESTION PER SLIDE — guaranteed by construction: every detected question
   becomes exactly one duplicated slide. There is no "N questions per section"
   guesswork anymore.
2. ACCURATE, "DIMENSIONALLY PERFECT" CROPPING — solved with a 3-layer approach:
      a. Gemini Vision detects a bounding box PER QUESTION (not per fixed page slice).
      b. NEIGHBOUR-CLIPPING: each box is hard-clamped against the boxes of the
         question directly above and below it, so a box can never bleed into a
         neighbouring question even if Gemini's box is a little off.
      c. AUTO-TRIM: within that safe zone we re-tighten the crop to the actual ink
         on the page (so extra white margin never survives) and then add a small,
         fixed, even padding — this is what makes every card look identical.
3. REAL SUBJECT DETECTION — instead of assuming "25 questions per subject", the
   tool detects the actual "SECTION-I (PHYSICS)" / "SECTION-II (CHEMISTRY)" ...
   banners on the page and assigns every question to the section it physically
   falls under, in true reading order (page → column → top-to-bottom).
4. SAMPLE PPT IS NEVER TOUCHED — the sample .pptx is opened, its dedicated
   "#QUESTION / Ans. (?)" slide is cloned (logo, colours, fonts, position — all of
   it) once per question, text placeholders are swapped in place, and the crop is
   dropped into the empty content area. The one throwaway template slide is then
   removed. Every run always looks pixel-identical to the sample.

REQUIREMENTS
------------
pip install streamlit pdf2image pillow python-pptx google-genai numpy
(+ poppler-utils installed on the system, for pdf2image)

RUN
---
streamlit run pw_test_ppt_generator.py
"""

import copy
import io
import json
import os
import re
import shutil
import zipfile
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import streamlit as st
from PIL import Image, ImageEnhance, ImageOps
from pdf2image import convert_from_bytes
from pptx import Presentation
from pptx.util import Emu

from google import genai
from google.genai import types

# ============================================================================
# PAGE SETUP
# ============================================================================
st.set_page_config(page_title="PW Test PPT Generator", layout="wide")
st.title("📚 Automated Question Paper → PPT Generator")
st.caption(
    "Upload the question paper PDF + your fixed sample PPT once. "
    "Get perfectly cropped, subject-wise, one-question-per-slide decks — every time."
)

# ============================================================================
# SIDEBAR CONFIG
# ============================================================================
st.sidebar.header("⚙️ Configuration")
gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password")
model_name = st.sidebar.selectbox(
    "Gemini model",
    ["gemini-2.5-flash", "gemini-3.5-flash ","gemini-3.5-flash-lite","gemini-3-flash-preview","gemini-2.5-pro"],
    help="Flash = faster/cheaper. Pro = slightly more accurate on dense/cramped pages.",
)
exam_type = st.sidebar.selectbox("Exam Type", ["JEE Main / Advanced", "NEET"])
KNOWN_SUBJECTS = (
    ["Physics", "Chemistry", "Mathematics"]
    if "JEE" in exam_type
    else ["Physics", "Chemistry", "Botany", "Zoology"]
)
st.sidebar.info(f"Expected subjects: **{', '.join(KNOWN_SUBJECTS)}**")

with st.sidebar.expander("Advanced (crop tuning)"):
    render_dpi = st.slider("PDF render DPI", 200, 400, 300, step=50)
    pad_px = st.slider("Padding around each question (px @ render DPI)", 5, 40, 18)
    col_gap_pct = st.slider("Column-gap exclusion (%)", 0.5, 4.0, 1.5, step=0.5)
    outer_margin_pct = st.slider("Outer page-margin exclusion (%)", 0.0, 3.0, 1.2, step=0.2)

# ============================================================================
# DATA MODEL
# ============================================================================
@dataclass
class DetectedItem:
    kind: str  # "question" | "section_header"
    page_index: int
    column_index: int  # 0 = left, 1 = right
    y0: int  # absolute pixel coords on the full page
    x0: int
    y1: int
    x1: int
    question_number: Optional[int] = None
    subject: Optional[str] = None

    @property
    def sort_key(self):
        return (self.page_index, self.column_index, self.y0)


# ============================================================================
# GEMINI HELPERS
# ============================================================================
DETECTION_PROMPT = """You are analysing ONE COLUMN of a scanned exam question-paper page.

Return a JSON array. Each element is ONE of the following two shapes:

1) A question (only if the question's number label is visible at the TOP of its
   own block in THIS image — skip anything that is clearly a continuation of a
   question that started above this crop):
   {{
     "type": "question",
     "question_number": <integer>,
     "box_2d": [ymin, xmin, ymax, xmax]
   }}
   The box must tightly enclose the ENTIRE question: its number, full text,
   any diagram/figure/table belonging to it, and ALL of its answer options —
   but must STOP before the next question's number begins. Do not include any
   part of the previous or next question.

2) A section header banner (e.g. "SECTION-I (PHYSICS)", "SECTION-II (CHEMISTRY)"):
   {{
     "type": "section_header",
     "subject": "<one of: {subjects}>",
     "box_2d": [ymin, xmin, ymax, xmax]
   }}

Coordinates are integers normalised 0-1000 relative to THIS image's width/height,
in [ymin, xmin, ymax, xmax] order. Return ONLY the JSON array, no commentary.
"""

ANSWER_KEY_PROMPT = """This image is an answer key for an exam. Extract every
question number and its correct option/answer. Return ONLY a JSON object
mapping question number (as a string) to the answer, e.g.:
{"1": "3", "2": "1", "3": "4"}
If the answer is a numeric-value ("integer type") answer, keep it as given.
"""


def get_client(api_key: str):
    return genai.Client(api_key=api_key)


def _extract_json(text: str):
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def detect_items_in_column(client, model_name, pil_img, subjects) -> list:
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    prompt = DETECTION_PROMPT.format(subjects=", ".join(subjects))
    resp = client.models.generate_content(
        model=model_name,
        contents=[
            types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png"),
            prompt,
        ],
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
        ),
    )
    try:
        return _extract_json(resp.text)
    except Exception:
        return []


def ocr_answer_key_image(client, model_name, pil_img) -> dict:
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    resp = client.models.generate_content(
        model=model_name,
        contents=[
            types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png"),
            ANSWER_KEY_PROMPT,
        ],
        config=types.GenerateContentConfig(temperature=0, response_mime_type="application/json"),
    )
    try:
        raw = _extract_json(resp.text)
        return {int(k): str(v).upper() for k, v in raw.items()}
    except Exception:
        return {}


def parse_answer_key_text(text: str) -> dict:
    """Robust parser for pasted answer keys: '1: (3)', '1) 3', '1-3', '1.(3)' etc."""
    ans_dict = {}
    if not text:
        return ans_dict
    matches = re.findall(r"(\d{1,3})\s*[\.\):\-]+\s*\(?\s*([1-4A-Da-d]+)\s*\)?", text)
    for q_num, ans in matches:
        ans_dict[int(q_num)] = ans.upper()
    return ans_dict


# ============================================================================
# IMAGE HELPERS
# ============================================================================
def box_2d_to_abs(box_2d, img_w, img_h, offset_x, offset_y):
    """Gemini box_2d is [ymin, xmin, ymax, xmax] normalised 0-1000 in the
    column-image's own frame. Convert to absolute pixel coords on the FULL page."""
    ymin, xmin, ymax, xmax = box_2d
    x0 = offset_x + int(xmin / 1000 * img_w)
    x1 = offset_x + int(xmax / 1000 * img_w)
    y0 = offset_y + int(ymin / 1000 * img_h)
    y1 = offset_y + int(ymax / 1000 * img_h)
    return x0, y0, x1, y1


def clip_against_neighbours(items_in_column, gap_px=6):
    """items_in_column: list of DetectedItem (questions only), sorted by y0.
    Clamp each box's top/bottom against its neighbours so adjacent crops can
    never overlap, regardless of how imprecise the raw AI box was."""
    items_in_column.sort(key=lambda it: it.y0)
    for i, item in enumerate(items_in_column):
        if i > 0:
            prev = items_in_column[i - 1]
            floor = prev.y1 + gap_px
            if item.y0 < floor:
                item.y0 = floor
        if i < len(items_in_column) - 1:
            nxt = items_in_column[i + 1]
            ceiling = nxt.y0 - gap_px
            if item.y1 > ceiling:
                item.y1 = ceiling
    return items_in_column


def autotrim(pil_img: Image.Image, pad: int = 18, bg_thresh: int = 245) -> Image.Image:
    """Tighten a crop to its actual ink content, then re-add fixed padding.
    This is what makes every slide's crop look consistently framed, independent
    of how loose/tight the upstream AI box was."""
    if pil_img.width < 4 or pil_img.height < 4:
        return pil_img
    gray = pil_img.convert("L")
    arr = np.array(gray)
    mask = arr < bg_thresh
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return pil_img
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(arr.shape[1] - 1, x1 + pad)
    y1 = min(arr.shape[0] - 1, y1 + pad)
    return pil_img.crop((x0, y0, x1, y1))


def invert_to_black_bg(pil_img: Image.Image) -> Image.Image:
    rgb_img = pil_img.convert("RGB")
    inverted_img = ImageOps.invert(rgb_img)
    return ImageEnhance.Contrast(inverted_img).enhance(1.15)


def split_columns(page_img: Image.Image, outer_margin_pct: float, col_gap_pct: float):
    """Return [(col_image, offset_x, offset_y), ...] for left & right column,
    insetting the outer page border and the centre column rule so neither ever
    ends up baked into a question crop."""
    w, h = page_img.size
    om = outer_margin_pct / 100.0
    cg = col_gap_pct / 100.0
    left_x0 = int(w * om)
    left_x1 = int(w * (0.5 - cg))
    right_x0 = int(w * (0.5 + cg))
    right_x1 = int(w * (1 - om))
    top = int(h * om)
    bottom = int(h * (1 - om))
    left_col = page_img.crop((left_x0, top, left_x1, bottom))
    right_col = page_img.crop((right_x0, top, right_x1, bottom))
    return [
        (left_col, left_x0, top),
        (right_col, right_x0, top),
    ]


# ============================================================================
# PPTX HELPERS  (duplicate / move / delete slide, text swap, image insert)
# ============================================================================
def duplicate_slide(prs: Presentation, index: int):
    src = prs.slides[index]
    layout = src.slide_layout
    new_slide = prs.slides.add_slide(layout)
    for shp in list(new_slide.shapes):
        shp._element.getparent().remove(shp._element)
    for shp in src.shapes:
        new_slide.shapes._spTree.append(copy.deepcopy(shp._element))
    for rId, rel in src.part.rels.items():
        if "notesSlide" in rel.reltype or "slideLayout" in rel.reltype:
            continue
        if rel.is_external:
            new_slide.part.rels.add_relationship(rel.reltype, rel._target, rId, is_external=True)
        else:
            new_slide.part.rels.add_relationship(rel.reltype, rel.target_part, rId)
    return new_slide


def move_slide(prs: Presentation, old_index: int, new_index: int):
    xml_slides = prs.slides._sldIdLst
    slides = list(xml_slides)
    xml_slides.remove(slides[old_index])
    xml_slides.insert(new_index, slides[old_index])


def delete_slide(prs: Presentation, index: int):
    xml_slides = prs.slides._sldIdLst
    slides = list(xml_slides)
    rId = slides[index].rId
    xml_slides.remove(slides[index])
    prs.part.drop_rel(rId)


def find_shape_by_text(slide, contains: str):
    for shp in slide.shapes:
        if shp.has_text_frame and contains in shp.text_frame.text:
            return shp
    return None


def set_text_preserve_format(shape, new_text: str):
    tf = shape.text_frame
    p = tf.paragraphs[0]
    if p.runs:
        p.runs[0].text = new_text
        for r in p.runs[1:]:
            r.text = ""
    else:
        p.text = new_text


def locate_question_template_slide(prs: Presentation) -> int:
    """Find the sample's dedicated question slide by its '#QUESTION' placeholder,
    instead of hardcoding an index — so this keeps working even if the sample
    deck is re-ordered."""
    for i, slide in enumerate(prs.slides):
        if find_shape_by_text(slide, "#QUESTION") is not None:
            return i
    raise ValueError(
        "Sample PPT me '#QUESTION' placeholder wala slide nahi mila. "
        "Kripya sample template me ek slide rakhein jisme '#QUESTION' aur 'Ans. (?)' text ho."
    )


def build_subject_ppt(template_bytes: bytes, questions: list, answers: dict, subject: str) -> bytes:
    """questions: list of dicts {number, image (PIL)} sorted by number."""
    prs = Presentation(io.BytesIO(template_bytes))
    template_idx = locate_question_template_slide(prs)

    slide_w, slide_h = prs.slide_width, prs.slide_height
    content_top = Emu(int(1.05 * 914400))
    content_left = Emu(int(0.45 * 914400))
    content_w = slide_w - Emu(int(0.9 * 914400))
    content_h = slide_h - content_top - Emu(int(0.35 * 914400))

    insert_at = template_idx  # new slides land where the template used to be
    for q in questions:
        new_slide = duplicate_slide(prs, template_idx)
        move_slide(prs, len(prs.slides) - 1, insert_at)
        insert_at += 1

        qshape = find_shape_by_text(new_slide, "#QUESTION")
        if qshape is not None:
            set_text_preserve_format(qshape, f"Q{q['number']}")
        ashape = find_shape_by_text(new_slide, "Ans. (")
        if ashape is not None:
            ans = answers.get(q["number"])
            set_text_preserve_format(ashape, f"Ans. ({ans})" if ans else "Ans. (—)")

        buf = io.BytesIO()
        q["image"].save(buf, format="PNG")
        buf.seek(0)
        iw, ih = q["image"].size
        scale = min(content_w / iw, content_h / ih)
        final_w, final_h = int(iw * scale), int(ih * scale)
        left = content_left + int((content_w - final_w) / 2)
        top = content_top + int((content_h - final_h) / 2)
        new_slide.shapes.add_picture(buf, left, top, width=final_w, height=final_h)

    # remove the now-unused bare template slide (it shifted after our insert loop)
    delete_slide(prs, insert_at)

    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()


# ============================================================================
# MAIN PIPELINE
# ============================================================================
def run_pipeline(pdf_bytes, template_bytes, ans_dict, client, model_name, progress_cb=None):
    pages = convert_from_bytes(pdf_bytes, dpi=render_dpi)
    all_questions: list[DetectedItem] = []
    all_headers: list[DetectedItem] = []

    total_steps = len(pages) * 2
    step = 0
    for page_idx, page_img in enumerate(pages):
        columns = split_columns(page_img, outer_margin_pct, col_gap_pct)
        for col_idx, (col_img, off_x, off_y) in enumerate(columns):
            step += 1
            if progress_cb:
                progress_cb(step / total_steps, f"Page {page_idx+1}/{len(pages)} — column {col_idx+1}")
            raw_items = detect_items_in_column(client, model_name, col_img, KNOWN_SUBJECTS)
            cw, ch = col_img.size
            for it in raw_items:
                try:
                    box = it["box_2d"]
                    x0, y0, x1, y1 = box_2d_to_abs(box, cw, ch, off_x, off_y)
                except Exception:
                    continue
                if it.get("type") == "question" and it.get("question_number") is not None:
                    all_questions.append(
                        DetectedItem(
                            kind="question",
                            page_index=page_idx,
                            column_index=col_idx,
                            y0=y0, x0=x0, y1=y1, x1=x1,
                            question_number=int(it["question_number"]),
                        )
                    )
                elif it.get("type") == "section_header":
                    all_headers.append(
                        DetectedItem(
                            kind="section_header",
                            page_index=page_idx,
                            column_index=col_idx,
                            y0=y0, x0=x0, y1=y1, x1=x1,
                            subject=it.get("subject"),
                        )
                    )

    if not all_questions:
        raise ValueError(
            "Koi bhi question detect nahi hua. Gemini API key check karein, "
            "ya 'Advanced (crop tuning)' settings adjust karke dobara try karein."
        )

    # --- neighbour-clip within each (page, column) group ---
    by_col = {}
    for q in all_questions:
        by_col.setdefault((q.page_index, q.column_index), []).append(q)
    for key, items in by_col.items():
        clip_against_neighbours(items)

    # --- assign subject: most recent header at/before this item in reading order ---
    all_headers.sort(key=lambda h: h.sort_key)
    all_questions.sort(key=lambda q: q.sort_key)
    header_ptr = 0
    current_subject = KNOWN_SUBJECTS[0]
    hi = 0
    for q in all_questions:
        while hi < len(all_headers) and all_headers[hi].sort_key <= q.sort_key:
            if all_headers[hi].subject:
                current_subject = all_headers[hi].subject
            hi += 1
        q.subject = current_subject

    # --- crop, autotrim, invert ---
    subject_questions = {s: [] for s in KNOWN_SUBJECTS}
    for q in all_questions:
        page_img = pages[q.page_index]
        x0, y0, x1, y1 = max(0, q.x0), max(0, q.y0), min(page_img.width, q.x1), min(page_img.height, q.y1)
        if x1 <= x0 or y1 <= y0:
            continue
        raw_crop = page_img.crop((x0, y0, x1, y1))
        trimmed = autotrim(raw_crop, pad=pad_px)
        dark = invert_to_black_bg(trimmed)
        subj = q.subject if q.subject in subject_questions else KNOWN_SUBJECTS[0]
        subject_questions[subj].append({"number": q.question_number, "image": dark})

    for subj in subject_questions:
        subject_questions[subj].sort(key=lambda d: d["number"])

    # --- build one PPT per subject ---
    work_dir = "output_processing"
    if os.path.exists(work_dir):
        shutil.rmtree(work_dir)
    os.makedirs(work_dir)

    subject_counts = {}
    for subj, qs in subject_questions.items():
        if not qs:
            subject_counts[subj] = 0
            continue
        subject_counts[subj] = len(qs)
        sub_folder = os.path.join(work_dir, subj)
        os.makedirs(sub_folder, exist_ok=True)
        ppt_bytes = build_subject_ppt(template_bytes, qs, ans_dict, subj)
        with open(os.path.join(sub_folder, f"{subj}_Discussion.pptx"), "wb") as f:
            f.write(ppt_bytes)

    zip_path = "All_Subject_PPTs.zip"
    if os.path.exists(zip_path):
        os.remove(zip_path)
    shutil.make_archive("All_Subject_PPTs", "zip", work_dir)

    return zip_path, subject_counts, subject_questions


# ============================================================================
# UI
# ============================================================================
col1, col2 = st.columns(2)
with col1:
    pdf_file = st.file_uploader("1. Question Paper (PDF)", type=["pdf"])
with col2:
    template_ppt = st.file_uploader("2. Sample PPT Template (.pptx)", type=["pptx"])

tab1, tab2 = st.tabs(["Paste Answer Key", "Upload Answer Key Image/PDF (optional, OCR'd)"])
with tab1:
    ans_key_text = st.text_area(
        "Answer key",
        placeholder="Example:\n1: (3)\n2: (1)\n3: (4) ...",
        height=120,
    )
with tab2:
    ans_key_file = st.file_uploader("Answer key image/PDF", type=["png", "jpg", "jpeg", "pdf"], key="akf")

if st.button("🚀 Process & Generate All Subject PPTs", type="primary"):
    if not pdf_file or not template_ppt:
        st.error("⚠️ Kripya Question Paper PDF aur Sample PPT Template dono upload karein!")
    elif not gemini_api_key:
        st.error("⚠️ Sidebar me Gemini API Key daalna zaroori hai!")
    else:
        try:
            client = get_client(gemini_api_key)

            ans_dict = parse_answer_key_text(ans_key_text)
            if ans_key_file is not None:
                if ans_key_file.type == "application/pdf":
                    ak_pages = convert_from_bytes(ans_key_file.read(), dpi=250)
                    for p in ak_pages:
                        ans_dict.update(ocr_answer_key_image(client, model_name, p))
                else:
                    img = Image.open(ans_key_file)
                    ans_dict.update(ocr_answer_key_image(client, model_name, img))

            progress_bar = st.progress(0.0)
            status_text = st.empty()

            def progress_cb(frac, msg):
                progress_bar.progress(min(frac, 1.0))
                status_text.text(msg)

            zip_path, subject_counts, subject_questions = run_pipeline(
                pdf_file.read(), template_ppt.read(), ans_dict, client, model_name, progress_cb
            )
            status_text.empty()
            progress_bar.empty()

            st.success("🎉 Sabhi Subject PPTs successfully generate ho gayi hain!")
            st.write("**Subject-wise question count:**")
            st.table({"Subject": list(subject_counts.keys()), "Questions": list(subject_counts.values())})

            with st.expander("Preview a few cropped slides"):
                for subj, qs in subject_questions.items():
                    if not qs:
                        continue
                    st.markdown(f"**{subj}**")
                    preview_cols = st.columns(min(3, len(qs)))
                    for i, q in enumerate(qs[:3]):
                        with preview_cols[i]:
                            st.image(q["image"], caption=f"Q{q['number']}", use_container_width=True)

            with open(zip_path, "rb") as fp:
                st.download_button(
                    label="📦 One-Click Download All PPTs (ZIP)",
                    data=fp,
                    file_name=zip_path,
                    mime="application/zip",
                )

        except Exception as e:
            st.error(f"Error aaya hai: {str(e)}")
            st.exception(e)
