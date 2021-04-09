""" General image utilities """
import io
import requests

from base64 import b64decode, b64encode

from PIL import Image, ImageChops


IMG_BASE64_PREFIX = b"data:image/png;base64,"


def base64_to_image(base64_string):
    """ Converts a base64 string of an image into a PIL image """
    return Image.open(io.BytesIO(b64decode(base64_string)))


def image_to_base64(image, image_format="PNG", quality=75, optimize=False):
    """ Converts a PIL image into base64 string with PIL params by default """
    return b64encode(image_to_bytes(image, image_format, quality, optimize))


def image_to_bytes(image, image_format="PNG", quality=100, optimize=True):
    """ Converts a PIL image into raw bytes overriding PIL params by default """

    if image_format.upper() == "JPEG":
        image = image.convert("RGB")

    output = io.BytesIO()
    image.save(output, format=image_format, quality=quality, optimize=optimize)
    return output.getvalue()


def image_to_string(image, prefix=True):
    """ Converts a PIL image, or a base64 string or bytes into a base64 image string """

    if image is None:
        return None
    elif isinstance(image, Image.Image):
        image_str = image_to_base64(image)
    elif isinstance(image, str):
        image_str = image.encode("ascii")
    else:
        image_str = image  # Assume base64 encoded bytes

    if image_str.startswith(b"http"):
        return image_to_string(Image.open(io.BytesIO(requests.get(image).content)), prefix)

    if not prefix and image_str.startswith(IMG_BASE64_PREFIX):
        image_str = image_str[len(IMG_BASE64_PREFIX):]
    elif prefix and not image_str.startswith(IMG_BASE64_PREFIX):
        image_str = (IMG_BASE64_PREFIX + image_str)

    return image_str.decode("ascii")


def count_colors(img):
    """ :return: count of colors, if possible """

    try:
        if not img.palette:
            return len(img.getcolors())
        else:
            # Assume RGB, and 4 chars per color, plus 1 (based on testing)
            return (len(img.palette.palette) / 12) + 1
    except Exception:
        return 0  # Could not obtain colors in normal way


def crop_image(img, padding=0, background_color=(255, 255, 255, 255)):
    """ Crops a given image, using the background_color to denote "whitespace" (defaults to white) """

    if img.mode != "RGBA":
        img = img.convert("RGBA")

    background_image = Image.new("RGBA", img.size, background_color)
    diff = ImageChops.difference(img, background_image)
    bbox = diff.getbbox()

    if bbox:
        bbox_list = list(bbox)
        bbox_list[0] = min(0, bbox_list[0] - padding)
        bbox_list[1] = min(0, bbox_list[1] - padding)
        bbox_list[2] += padding
        bbox_list[3] += padding
        return img.crop(tuple(bbox_list))
    return img


def overlay_images(images, background_color=(255, 255, 255, 255)):
    """ Merges images into a single image, ordered from bottom to top. Images must be same dimensions """

    if len(images) <= 1:
        raise ValueError("More than one image is required to overlay images")

    size = images[0].size
    img = Image.new("RGBA", size, background_color)

    for current_image in images:
        current_image = current_image.convert("RGBA")

        # Use composite, not paste, to keep alpha of images
        img = Image.alpha_composite(img, current_image)

    return img


def make_color_transparent(img, color):  # May be needed for certain ArcGIS services
    """ Image must already be RGBA mode, color is a RGBA tuple """

    pixdata = img.load()
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            if pixdata[x, y] == color:
                # TODO: Consider replacing this with a function passed in that evaluates true/false
                pixdata[x, y] = (255, 255, 255, 0)


def set_image_transparency(img, transparency):
    """ Makes image transparent (0-100% scale), preserving already transparent areas """

    transparent_color = int(round(255 * (float(100 - transparency) / 100.0), 0))
    img.putalpha(Image.new("L", img.size, color=transparent_color))  # Note: turns transparent pixels gray!
    make_color_transparent(img, (0, 0, 0, transparent_color))


def stack_images_vertically(images, background_color=None):
    """ Stacks images vertically, expanding width as necessary to fit widest image """

    if background_color is None:
        background_color = (0, 0, 0, 0)  # Empty background

    height = sum([image.size[1] for image in images])
    width = max([image.size[0] for image in images])

    img = Image.new("RGBA", (width, height), background_color)
    offset = 0
    for image in images:
        if not image.mode == "RGBA":
            image = image.convert("RGBA")
        img.paste(image, (0, offset), image)
        offset += image.size[1]
    return img
