from models import BoundingBox


def normalized_box_to_absolute(box_2d, image_width: int, image_height: int, offset_x: int = 0, offset_y: int = 0) -> BoundingBox:
    ymin, xmin, ymax, xmax = [float(value) for value in box_2d]
    return BoundingBox(
        offset_x + int((xmin / 1000) * image_width),
        offset_y + int((ymin / 1000) * image_height),
        offset_x + int((xmax / 1000) * image_width),
        offset_y + int((ymax / 1000) * image_height),
    )


def crop_question(page_image, item, pad_x: int = 24, pad_y: int = 14):
    box = item.box.clamp(page_image.width, page_image.height)
    x0 = max(0, box.x0 - pad_x)
    y0 = max(0, box.y0 - pad_y)
    x1 = min(page_image.width, box.x1 + pad_x)
    y1 = min(page_image.height, box.y1 + pad_y)
    if x1 <= x0 or y1 <= y0:
        raise ValueError(f"Invalid crop for question {item.number}")
    return page_image.crop((x0, y0, x1, y1))
