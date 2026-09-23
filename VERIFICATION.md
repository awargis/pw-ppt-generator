# Verification Record

Executed against the final repository build.

## Static / unit verification

```text
python -m compileall .  -> PASS
pytest -q              -> 19 passed
```

## Supplied PW sample-paper verification

The supplied `PW_Milestone_Test-01_Class-11th_Phase-05_Main_13-09-2026_Questions_ROI+KPM.pdf`
was added under `examples/` as a regression fixture and processed through the
local pipeline.

```text
Exam detected: JEE Main
Expected questions: 75
Detected questions: 75
Unique question numbers: 1–75
Physics: 25
Chemistry: 25
Mathematics: 25
Instruction-page false questions: 0
Integer-type questions classified: 15
MCQ questions classified: 60
```

Representative MCQ crops were checked to ensure the question and its options
remain in one raster crop. Representative Integer-type crops retain their
original paper format.

The cleanup layer produces RGBA crops and removes the light institutional
page/watermark background when the default transparent-background mode is used.

## Real production PPT smoke test

The supplied 75-question sample was processed with the included premium PPT
template.

```text
Physics PPT:     25 slides
Chemistry PPT:   25 slides
Mathematics PPT: 25 slides
Question crops:  75
Manifest entries: 75
ZIP integrity: PASS
```

All three generated PPTX files were reopened with `python-pptx` and their slide
counts verified.

## Not executed in this environment

```text
flake8 . --select=E9,F63,F7,F82
```

Reason: `flake8` is not installed in the execution environment and this
environment cannot reach PyPI to install it.

The GitHub Actions workflow installs `flake8` and `pytest` before running CI.

## Application UI

The Streamlit application source passes Python compilation, but Streamlit is
not installed in the build environment used for this verification. It is
declared in `requirements.txt` and will be installed by the normal setup
command.


## New regression coverage

```text
Answer-key parser: option letters + option numbers + numerical values + arbitrary order -> PASS
NEET subject anchors: cover/instruction page excluded; Physics/Chemistry/Botany/Zoology ranges -> PASS
JEE Advanced: subject-local question ranges may restart at Q1 -> PASS
Supplied JEE Main sample after changes: 75/75 questions; 25 per subject; 75/75 answers parsed -> PASS
Production PPT smoke after changes: 25 + 25 + 25 slides -> PASS
```
