from .enhancement import enhance


def prepare_crop(image, style="Premium Light", transparent_background=True):
    return enhance(image, style, transparent_background=transparent_background)
