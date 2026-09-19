import copy, io
from pptx import Presentation
from pptx.util import Emu

RELATIONSHIP_NAMESPACE = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

def find_shape_by_text(slide, text: str):
    for shape in slide.shapes:
        if shape.has_text_frame and text in shape.text_frame.text: return shape
    return None

def set_shape_text(shape, text: str):
    shape.text_frame.paragraphs[0].text = text

def duplicate_slide(prs, source_index):
    source = prs.slides[source_index]
    new_slide = prs.slides.add_slide(source.slide_layout)
    for shape in list(new_slide.shapes): shape._element.getparent().remove(shape._element)
    
    rel_map = {}
    for old_id, rel in source.part.rels.items():
        if "notesSlide" in rel.reltype or "slideLayout" in rel.reltype: continue
        rel_map[old_id] = new_slide.part.relate_to(rel.target_ref if rel.is_external else rel.target_part, rel.reltype, is_external=rel.is_external)
        
    for shape in source.shapes:
        copied_el = copy.deepcopy(shape._element)
        for el in copied_el.iter():
            for attr, val in list(el.attrib.items()):
                if attr.startswith(RELATIONSHIP_NAMESPACE) and val in rel_map: el.set(attr, rel_map[val])
        new_slide.shapes._spTree.append(copied_el)
    return new_slide

def move_and_delete(prs, insert_idx, delete_idx):
    slides = list(prs.slides._sldIdLst)
    prs.slides._sldIdLst.insert(insert_idx, slides.pop(-1))
    prs.slides._sldIdLst.remove(list(prs.slides._sldIdLst)[delete_idx])

def build_subject_ppt(template_bytes: bytes, questions: list[dict], answers: dict) -> bytes:
    prs = Presentation(io.BytesIO(template_bytes))
    template_index = next((i for i, s in enumerate(prs.slides) if find_shape_by_text(s, "#QUESTION")), 0)
    
    c_left, c_top = Emu(int(0.45 * 914400)), Emu(int(1.50 * 914400))
    c_width, c_height = prs.slide_width - Emu(int(0.9 * 914400)), prs.slide_height - c_top - Emu(int(0.35 * 914400))
    insert_index = template_index

    for q in questions:
        slide = duplicate_slide(prs, template_index)
        
        if q_shape := find_shape_by_text(slide, "#QUESTION"):
            set_shape_text(q_shape, f"Q{q['number']}")
            
        if ans_shape := find_shape_by_text(slide, "Ans. ("):
            set_shape_text(ans_shape, f"Ans. ({answers.get(q['number'], '?')})")

        img_buf = io.BytesIO()
        q["image"].save(img_buf, format="PNG")
        img_buf.seek(0)
        
        iw, ih = q["image"].size
        scale = min(int(c_width) / iw, int(c_height) / ih)
        fw, fh = max(1, int(iw * scale)), max(1, int(ih * scale))
        left, top = int(c_left) + (int(c_width) - fw) // 2, int(c_top) + (int(c_height) - fh) // 2
        
        slide.shapes.add_picture(img_buf, left, top, width=fw, height=fh)
        
        slides_list = list(prs.slides._sldIdLst)
        prs.slides._sldIdLst.insert(insert_index, slides_list.pop(-1))
        insert_index += 1

    prs.slides._sldIdLst.remove(list(prs.slides._sldIdLst)[insert_index])
    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()
