# Vidyapeeth Test Presentation Studio

A production-oriented, local-first Streamlit application for turning JEE Main, JEE Advanced and NEET UG question-paper PDFs into **reviewable, subject-wise discussion PPTX files**.

> No Gemini/OpenAI API is required by the active pipeline.

## What the application does

```text
Question PDF + discussion PPT
    ↓
Automatic exam detection (JEE Main / JEE Advanced / NEET)
    ↓
Paper instructions + section structure extraction
    ↓
PyMuPDF native extraction
    ↓
Tesseract OCR fallback (only when native text is insufficient)
    ↓
Page layout / column analysis
    ↓
Question-marker detection (NOT option-marker detection)
    ↓
Exact question segmentation (MCQ + all options / Integer type)
    ↓
Subject-wise validation and 25-question boundary checks
    ↓
Content crop + background/watermark removal + clarity enhancement
    ↓
Human review
    ↓
Uploaded PPT template cloning
    ↓
Physics / Chemistry / Mathematics PPTX + crops + manifest ZIP
```

## Quick start

### 1. Install Python

Python 3.10–3.12 is recommended.

### 2. Install Python dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 3. Install Tesseract OCR

**Ubuntu/Debian**

```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr
```

**Windows**

Install Tesseract OCR and ensure `tesseract.exe` is on PATH. If it is not on PATH, set `pytesseract.pytesseract.tesseract_cmd` in `pipeline/ocr_engine.py` to your local executable.

### 4. Start the application

```bash
streamlit run app.py
```

Then upload:

1. Question-paper PDF
2. Discussion PPT template
3. Optional answer key

The answer-key parser is order-independent and format-flexible. It accepts
option letters, option numbers, and numerical/numerical-value answers, for
example:

```text
1: (4), 2: (4), 23: (246), 24: (100), 75: (1.00)
```

These are also accepted: `1:A`, `Q2-B`, `3) C`, `4 -> D`, `18 B`, and mixed
entries in any order. Parentheses around answers are ignored. Values such as
`0`, `246`, `332`, `-2.5`, and `1.00` are preserved as answer values rather
than being restricted to options 1–4.

The included demo assets are:

- `examples/demo_question_paper.pdf`
- `examples/demo_answer_key.txt`
- `templates/Vidyapeeth_Premium_Discussion_Template.pptx`

## Template contract

The first slide of the uploaded PPTX becomes the visual master.

Supported text tokens:

| Token | Replaced with |
|---|---|
| `#QUESTION` | `Q1`, `Q2`, ... |
| `#SUBJECT` | Physics, Chemistry, Mathematics, etc. |
| `#ANSWER` | Answer-key value |

For exact question-image placement, create a shape on the first slide and rename it:

```text
QUESTION_IMAGE
```

The application replaces that shape with the detected question crop. If it is absent, a safe centered image area is used.

The question crop is the original PDF raster, not AI-generated/retyped text. MCQ
options remain part of the same question crop. Integer/Numerical questions are
kept in their original paper format. The default image treatment removes the
white/light-grey page background (including light institutional watermark
artifacts) while preserving dark mathematical text and diagrams.

More detail: `docs/TEMPLATE_GUIDE.md`.

## Subject classification

- **JEE Main:** Q1–25 Physics, Q26–50 Chemistry, Q51–75 Mathematics. The paper itself is first checked for section headers/instructions, then these ranges are used as a structural validation guard.
- **NEET UG:** Q1–45 Physics, Q46–90 Chemistry, Q91–135 Botany, Q136–180 Zoology. Subject headings are anchored to real question pages so cover-page topics and numbered instructions are excluded.
- **JEE Advanced:** no JEE Main-style 1–75 mapping is imposed. Subject/section windows are inferred from the uploaded paper, and question numbering may restart inside another subject/section without global number de-duplication.

This keeps JEE Advanced classification explainable rather than guessing.

## Native extraction vs OCR

Native PDF text is preferred because it provides cleaner characters and precise source coordinates. Tesseract is invoked only when the native text payload is too small, which is typical of scanned/image-only papers.

All downstream crop coordinates are normalized to **rendered-image pixels**, so the crop engine does not mix PDF points and image pixels.

## Output ZIP

The production ZIP contains:

```text
presentations/
  Physics/Physics_Discussion.pptx
  Chemistry/Chemistry_Discussion.pptx

crops/
  Physics/Q001.png
  Chemistry/Q026.png

manifest.json
```

The manifest records subject, answer, confidence, page and crop path for every included question.

## Verification

Run:

```bash
python -m compileall .
pytest -q
flake8 . --select=E9,F63,F7,F82
```

The CI workflow installs `flake8` and `pytest` automatically. If `flake8` is not installed in your local environment, install it with:

```bash
python -m pip install flake8 pytest
```

## Current engineering scope

The project is deliberately deterministic and reviewable. It does not pretend that arbitrary JEE PDFs can always be segmented perfectly: unusual multi-page layouts, heavily graphical questions and malformed scans can still require human review. The UI therefore exposes confidence and manual correction before PPT export.
