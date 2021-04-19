""" General image utilities """
import io
import requests

from base64 import b64decode, b64encode
from pathlib import Path

from PIL import Image


IMG_BASE64_PREFIX = b"data:image/png;base64,"
IMG_FORMATS_BY_EXT = {
    ".bmp": "BMP", ".dib": "DIB", ".gif": "GIF",
    ".tif": "TIFF", ".tiff": "TIFF",
    ".jfif": "JPEG", ".jpe": "JPEG", ".jpg": "JPEG", ".jpeg": "JPEG",
    ".pbm": "PPM", ".pgm": "PPM", ".ppm": "PPM", ".pnm": "PPM",
    ".png": "PNG", ".apng": "PNG", "": "PNG"
}
IMG_SUPPORTED_FORMATS = set(IMG_FORMATS_BY_EXT.values())


def base64_to_image(base64_string):
    """ Converts a base64 string of an image into a PIL image """
    return Image.open(io.BytesIO(b64decode(base64_string)))


def image_to_base64(image, image_format=None, quality=75, optimize=False):
    """ Converts a PIL image into base64 string with PIL params by default """
    return b64encode(image_to_bytes(image, image_format, quality, optimize))


def image_to_bytes(image, image_format=None, quality=100, optimize=True):
    """ Converts a PIL image into raw bytes overriding PIL params by default """

    if not image:
        raise ValueError("Image is required")

    image_ext = Path(getattr(image, "filename", "")).suffix
    if not image_format:
        image_format = IMG_FORMATS_BY_EXT[image_ext.lower()]

    image_format = image_format.upper()
    if image_format not in IMG_SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported image format: {image_format}")

    if image_format == "JPEG":
        image = image.convert("RGB")

    image_kwargs = {}
    if quality is not None:
        image_kwargs["quality"] = quality
    if optimize is not None:
        image_kwargs["optimize"] = optimize

    output = io.BytesIO()
    image.save(output, format=image_format, **image_kwargs)
    return output.getvalue()


def image_to_string(image, image_format=None, quality=None, optimize=None, prefix=True):
    """ Converts a PIL image, or a base64 string or bytes into a base64 image string """

    if not image:
        return None
    elif isinstance(image, Image.Image):
        image_str = image_to_base64(image, image_format, quality, optimize)
    elif isinstance(image, str):
        image_str = image.encode("ascii")
    elif isinstance(image, bytes):
        image_str = image
    else:
        raise ValueError("Image must be a PIL image, image string, or image bytes")

    if image_str.startswith(b"http"):
        response = requests.get(image)
        status_code = response.status_code

        if status_code != 200:
            raise ValueError(f"Image request failed with {status_code} for: {image_str}")
        else:
            image = Image.open(io.BytesIO(response.content))
            return image_to_string(image, image_format, quality, optimize, prefix)

    if not prefix and image_str.startswith(IMG_BASE64_PREFIX):
        image_str = image_str[len(IMG_BASE64_PREFIX):]
    elif prefix and not image_str.startswith(IMG_BASE64_PREFIX):
        image_str = (IMG_BASE64_PREFIX + image_str)

    return image_str.decode("ascii")


def count_colors(image):
    """ :return: count of an image's colors, if possible """

    try:
        if not image.palette:
            return len(image.getcolors())
        else:
            # Assume RGB, and 4 chars per color, plus 1 (based on testing)
            return (len(image.palette.palette) / 12) + 1
    except Exception:
        return 0  # Could not obtain colors in normal way


def overlay_images(images, background_color=(255, 255, 255, 255)):
    """ Merges images into a single image, ordered from bottom to top. Images must be same dimensions """

    if not images:
        raise ValueError("Images are required")
    elif len(images) < 2:
        raise ValueError("More than one image is required to overlay images")

    size = images[0].size
    image = Image.new("RGBA", size, background_color)

    for next_image in images:
        if next_image.mode != "RGBA":
            next_image = next_image.convert("RGBA")

        # Use composite, not paste, to keep alpha of images
        image = Image.alpha_composite(image, next_image)

    return image


def make_color_transparent(image, replace_color, with_color=None):
    """ Image must already be RGBA mode, color is an RGBA tuple """

    if not image:
        raise ValueError("Image is required")
    elif image.mode != "RGBA":
        image = image.convert("RGBA")

    if with_color is None:
        with_color = (255, 255, 255, 0)

    pixdata = image.load()
    for y in range(image.size[1]):
        for x in range(image.size[0]):
            if pixdata[x, y] == replace_color:
                pixdata[x, y] = with_color

    return image


def stack_images_vertically(images, background_color=(0, 0, 0, 0)):
    """ Stacks images vertically, expanding width as necessary to fit widest image """

    if not images:
        raise ValueError("Images are required")

    height = sum([image.size[1] for image in images])
    width = max([image.size[0] for image in images])
    image = Image.new("RGBA", (width, height), background_color)

    height_offset = 0
    for next_image in images:
        if next_image.mode != "RGBA":
            next_image = next_image.convert("RGBA")
        image.paste(next_image, (0, height_offset), image)
        height_offset += next_image.size[1]

    return image
