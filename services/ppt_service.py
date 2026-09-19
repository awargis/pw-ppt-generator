import copy
import io
from pptx import Presentation
from pptx.util import Emu

RELATIONSHIP_NAMESPACE = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

def duplicate_slide(prs, source_index):
    source = prs.slides[source_index]
    new_slide = prs.slides.add_slide(source.slide_layout)
    
    # Clear auto-generated shapes from the layout
    for shape in list(new_slide.shapes): 
        shape._element.getparent().remove(shape._element)
    
    rel_map = {}
    for old_id, rel in source.part.rels.items():
        if "notesSlide" in rel.reltype or "slideLayout" in rel.reltype: continue
        rel_map[old_id] = new_slide.part.relate_to(
            rel.target_ref if rel.is_external else rel.target_part, 
            rel.reltype, 
            is_external=rel.is_external
        )
        
    for shape in source.shapes:
        copied_el = copy.deepcopy(shape._element)
        for el in copied_el.iter():
            for attr, val in list(el.attrib.items()):
                if attr.startswith(RELATIONSHIP_NAMESPACE) and val in rel_map: 
                    el.set(attr, rel_map[val])
        new_slide.shapes._spTree.append(copied_el)
    return new_slide

def build_subject_ppt(template_bytes: bytes, questions: list[dict], answers: dict) -> bytes:
    prs = Presentation(io.BytesIO(template_bytes))
    
    # Define Content Coordinates
    c_left, c_top = Emu(int(0.45 * 914400)), Emu(int(1.50 * 914400))
    c_width = prs.slide_width - Emu(int(0.9 * 914400))
    c_height = prs.slide_height - c_top - Emu(int(0.35 * 914400))

    for q in questions:
        # 1. ALWAYS duplicate the clean master template (Index 0)
        new_slide = duplicate_slide(prs, 0)
        
        # 2. Hard-replace the text to guarantee the answer key updates
        for shape in new_slide.shapes:
            if shape.has_text_frame:
                text = shape.text
                if "#QUESTION" in text:
                    shape.text_frame.text = text.replace("#QUESTION", f"Q{q['number']}")
                elif "Ans." in text:
                    ans_val = answers.get(q['number'], answers.get(str(q['number']), " "))
                    shape.text_frame.text = f"Ans. ({ans_val})"

        # 3. Scale and insert the dark-mode image
        img_buf = io.BytesIO()
        q["image"].save(img_buf, format="PNG")
        img_buf.seek(0)
        
        iw, ih = q["image"].size
        scale = min(int(c_width) / iw, int(c_height) / ih)
        fw, fh = max(1, int(iw * scale)), max(1, int(ih * scale))
        left, top = int(c_left) + (int(c_width) - fw) // 2, int(c_top) + (int(c_height) - fh) // 2
        
        new_slide.shapes.add_picture(img_buf, left, top, width=fw, height=fh)

    # 4. Delete the master template (Index 0) so it doesn't appear in the final PPT
    xml_slides = prs.slides._sldIdLst
    xml_slides.remove(xml_slides[0])
    
    out = io.BytesIO()
    prs.save(out)
    return out.getvalue()
