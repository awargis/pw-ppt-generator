from models import BoundingBox
from utils.image_utils import autotrim, validate_crop, invert_to_black_background


def normalized_box_to_absolute(
    box_2d,
    image_width: int,
    image_height: int,
    offset_x: int,
    offset_y: int,
) -> BoundingBox:
    ymin, xmin, ymax, xmax = [float(value) for value in box_2d]

    x0 = offset_x + int((xmin / 1000) * image_width)
    y0 = offset_y + int((ymin / 1000) * image_height)
    x1 = offset_x + int((xmax / 1000) * image_width)
    y1 = offset_y + int((ymax / 1000) * image_height)

    return BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)


def clip_neighbour_boxes(items, gap: int = 6):
    items = sorted(items, key=lambda item: item.box.y0)

    for index, item in enumerate(items):
        if index > 0:
            previous = items[index - 1]
            item.box.y0 = max(
                item.box.y0,
                previous.box.y1 + gap,
            )

        if index + 1 < len(items):
            following = items[index + 1]
            item.box.y1 = min(
                item.box.y1,
                following.box.y0 - gap,
            )

    return items


def crop_question(
    page_image,
    item,
    padding: int,
    invert: bool = False,
):
    box = item.box

    x0 = max(0, box.x0)
    y0 = max(0, box.y0)
    x1 = min(page_image.width, box.x1)
    y1 = min(page_image.height, box.y1)

    if x1 <= x0 or y1 <= y0:
        raise ValueError(
            f"Invalid crop coordinates for Q{item.question_number}."
        )

    raw_crop = page_image.crop((x0, y0, x1, y1))
    trimmed = autotrim(raw_crop, padding=padding)

    validate_crop(trimmed, item.question_number)

    return (
        invert_to_black_background(trimmed)
        if invert
        else trimmed.convert("RGB")
    )
