from flask import Flask, render_template, request, send_file, jsonify
import os
import json
import zipfile
from ocr_processor import detect_question_boundaries
from pdf_cropper import crop_and_invert
from ppt_generator import build_subject_ppt

# --- Google Vision credentials from env var (Railway-safe) ---
creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
if creds_json:
    creds_path = "/tmp/google_key.json"
    with open(creds_path, "w") as f:
        f.write(creds_json)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path

app = Flask(__name__)

UPLOAD_DIR = 'static/uploads'
OUTPUT_DIR = 'static/outputs'
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/process', methods=['POST'])
def process():
    paper_type = request.form.get('paper_type', 'JEE')
    pdf_file = request.files.get('question_paper')

    if not pdf_file:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400

    pdf_path = os.path.join(UPLOAD_DIR, pdf_file.filename)
    pdf_file.save(pdf_path)

    questions = detect_question_boundaries(pdf_path)
    total_q = len(questions)

    if total_q == 0:
        return jsonify({"status": "error", "message": "No questions detected in PDF"}), 400

    subjects = ['Physics', 'Chemistry', 'Mathematics'] if paper_type == 'JEE' \
        else ['Physics', 'Chemistry', 'Botany', 'Zoology']
    q_per_subj = max(1, total_q // len(subjects))

    generated_ppts = []

    for idx, subj in enumerate(subjects):
        if idx < len(subjects) - 1:
            subj_q_list = questions[idx * q_per_subj:(idx + 1) * q_per_subj]
        else:
            subj_q_list = questions[idx * q_per_subj:]

        cropped_imgs = []
        for q_idx, q_info in enumerate(subj_q_list):
            crop_path = os.path.join(OUTPUT_DIR, paper_type, subj, f"Q_{q_idx+1}.png")
            crop_and_invert(pdf_path, q_info["page"], q_info["ymin"], q_info["ymax"], crop_path)
            cropped_imgs.append(crop_path)

        ppt_path = os.path.join(OUTPUT_DIR, paper_type, f"{subj}.pptx")
        build_subject_ppt('templates/template.pptx', cropped_imgs, ppt_path)
        generated_ppts.append(ppt_path)

    zip_name = f"{paper_type}_Output_PPTs.zip"
    zip_path = os.path.join(OUTPUT_DIR, zip_name)
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for ppt in generated_ppts:
            zipf.write(ppt, os.path.basename(ppt))

    return jsonify({"status": "success", "download_url": f"/download?file={zip_path}"})


@app.route('/download')
def download():
    file_path = request.args.get('file')
    # basic safety: only allow files inside OUTPUT_DIR
    if not file_path or not os.path.abspath(file_path).startswith(os.path.abspath(OUTPUT_DIR)):
        return jsonify({"status": "error", "message": "Invalid file"}), 400
    return send_file(file_path, as_attachment=True)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)