import os
import shutil


def create_subject_outputs(
    output_directory: str,
    template_bytes: bytes,
    subject_questions: dict,
    answers: dict,
    build_ppt_function,
):
    if os.path.exists(output_directory):
        shutil.rmtree(output_directory)

    os.makedirs(output_directory, exist_ok=True)

    output_files = []

    for subject, questions in subject_questions.items():
        if not questions:
            continue

        subject_directory = os.path.join(
            output_directory,
            subject,
        )

        os.makedirs(subject_directory, exist_ok=True)

        ppt_bytes = build_ppt_function(
            template_bytes,
            questions,
            answers,
        )

        output_path = os.path.join(
            subject_directory,
            f"{subject}_Discussion.pptx",
        )

        with open(output_path, "wb") as file:
            file.write(ppt_bytes)

        output_files.append(output_path)

    archive_path = shutil.make_archive(
        "All_Subject_PPTs",
        "zip",
        output_directory,
    )

    return archive_path, output_files
