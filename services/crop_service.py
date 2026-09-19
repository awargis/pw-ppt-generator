from models import BoundingBox
from utils.image_utils import validate_crop, apply_dark_mode

def normalized_box_to_absolute(box_2d, image_width: int, image_height: int, offset_x: int, offset_y: int) -> BoundingBox:
    ymin, xmin, ymax, xmax = [float(value) for value in box_2d]
    return BoundingBox(
        x0 = offset_x + int((xmin / 1000) * image_width),
        y0 = offset_y + int((ymin / 1000) * image_height),
        x1 = offset_x + int((xmax / 1000) * image_width),
        y1 = offset_y + int((ymax / 1000) * image_height)
    )

def crop_question(page_image, item, pad_x: int, pad_y: int):
    box = item.box
    # Apply adjustable dimensions dynamically
    x0 = max(0, box.x0 - pad_x)
    y0 = max(0, box.y0 - pad_y)
    x1 = min(page_image.width, box.x1 + pad_x)
    y1 = min(page_image.height, box.y1 + pad_y)

    raw_crop = page_image.crop((x0, y0, x1, y1))
    validate_crop(raw_crop, item.question_number)
    
    return apply_dark_mode(raw_crop)
