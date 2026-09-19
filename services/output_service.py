import io
import zipfile

def create_subject_outputs(template_bytes: bytes, subject_questions: dict, answers: dict, build_ppt_function):
    zip_buffer = io.BytesIO()
    
    # Memory-safe zipping prevents user collision
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for subject, questions in subject_questions.items():
            if not questions: continue
            ppt_bytes = build_ppt_function(template_bytes, questions, answers)
            zip_file.writestr(f"{subject}/{subject}_Discussion.pptx", ppt_bytes)
            
    zip_buffer.seek(0)
    return zip_buffer
