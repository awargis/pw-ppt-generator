from PIL import Image, ImageOps

def preprocess(image: Image.Image) -> Image.Image:
    return ImageOps.exif_transpose(image).convert("RGB")
