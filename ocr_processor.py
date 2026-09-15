import fitz
from google.cloud import vision
import re


def detect_question_boundaries(pdf_path):
    client = vision.ImageAnnotatorClient()
    doc = fitz.open(pdf_path)
    question_data = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=300)
        img_bytes = pix.tobytes("png")

        image = vision.Image(content=img_bytes)
        response = client.text_detection(image=image)
        annotations = response.text_annotations

        if not annotations:
            continue

        page_h = page.rect.height
        detected_in_page = []

        for ann in annotations[1:]:
            text = ann.description.strip()
            if re.match(r'^(Q\d+\.|Q\.\d+|\d+\.)', text):
                vertices = ann.bounding_poly.vertices
                ymin_pt = (vertices[0].y / pix.height) * page_h
                detected_in_page.append({"q_num": text, "ymin": ymin_pt})

        detected_in_page.sort(key=lambda x: x["ymin"])
        for i in range(len(detected_in_page)):
            q_top = detected_in_page[i]["ymin"] - 5
            if i + 1 < len(detected_in_page):
                q_bottom = detected_in_page[i + 1]["ymin"] - 5
            else:
                q_bottom = page_h - 10

            question_data.append({
                "page": page_num,
                "q_num": detected_in_page[i]["q_num"],
                "ymin": max(0, q_top),
                "ymax": min(page_h, q_bottom)
            })

    return question_data