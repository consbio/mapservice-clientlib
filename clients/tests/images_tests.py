import io
import pathlib

from base64 import b64decode, b64encode
from PIL import Image
from unittest import mock

from ..utils.images import (
    base64_to_image,
    image_to_bytes,
    image_to_base64,
    image_to_string,
)
from ..utils.images import count_colors, make_color_transparent
from ..utils.images import overlay_images, stack_images_vertically
from ..utils.images import IMG_BASE64_PREFIX

from .utils import BaseTestCase


def get_base64_for(image, image_format):
    output = io.BytesIO()
    image.save(output, format=image_format)
    return b64encode(output.getvalue())


class ImagesTestCase(BaseTestCase):
    def setUp(self):
        super(ImagesTestCase, self).setUp()

        self.test_jpg = Image.open(pathlib.Path(self.data_directory) / "test.jpeg")
        self.test_png = Image.open(pathlib.Path(self.data_directory) / "test.png")

    def test_image_to_base64(self):
        """ Tests conversion of test PNG image to base64 and back """

        with self.assertRaises(ValueError):
            image_to_base64(None)

        # Test PNG conversion

        test_base64 = image_to_base64(self.test_png, quality=100, optimize=True)
        self.assertEqual(test_base64, TEST_PNG_BASE64)

        test_image = base64_to_image(TEST_PNG_BASE64)
        test_base64 = image_to_base64(test_image, quality=100, optimize=True)
        self.assertEqual(test_base64, TEST_PNG_BASE64)

        # Test JPEG conversion (must be tested without optimization)

        test_base64 = image_to_base64(self.test_jpg)
        self.assertEqual(test_base64, TEST_JPG_BASE64)

        test_image = base64_to_image(TEST_JPG_BASE64)
        test_base64 = image_to_base64(test_image, image_format="JPEG")
        self.assertEqual(test_base64, TEST_JPG_BASE64)

    def test_image_to_bytes(self):

        with self.assertRaises(ValueError):
            image_to_bytes(None)
        with self.assertRaises(ValueError):
            image_to_bytes("")
        with self.assertRaises(ValueError):
            image_to_bytes([])
        with self.assertRaises(ValueError):
            image_to_bytes(self.test_png, image_format="nope")

        # Test PNG conversion

        test_bytes = image_to_bytes(self.test_png, quality=100, optimize=True)
        self.assertEqual(test_bytes, TEST_PNG_BYTES)

        # Test JPEG conversion

        test_bytes = image_to_bytes(self.test_jpg, quality=100, optimize=True)
        self.assertEqual(test_bytes, TEST_JPG_BYTES)

    @mock.patch("clients.utils.images.requests.get")
    def test_image_to_string(self, mock_get):

        # Test invalid cases

        mock_get.return_value = mock.Mock(
            ok=False, reason="nope", status_code=500, content=b"Server Error"
        )

        with self.assertRaises(ValueError):
            image_to_string("https://not/an/image.png")
        with self.assertRaises(ValueError):
            image_to_string(Image)

        self.assertIsNone(image_to_string(None))
        self.assertIsNone(image_to_string(""))
        self.assertIsNone(image_to_string([]))

        # Test valid URL cases

        # Test PNG conversion
        mock_get.return_value = mock.Mock(
            ok=True, reason="happy", status_code=200, content=b64decode(TEST_PNG_BASE64)
        )
        target = TEST_PNG_BASE64.decode("ascii")
        image_str = image_to_string(
            "https://not/an/image.png", quality=100, optimize=True, prefix=False
        )
        self.assertEqual(image_str, target)

        target = (IMG_BASE64_PREFIX + target.encode("ascii")).decode()
        image_str = image_to_string(
            b"https://not/an/image.png", quality=100, optimize=True
        )
        self.assertEqual(image_str, target)

        # Test JPEG conversion (must be tested without optimization)
        mock_get.return_value = mock.Mock(
            ok=True, reason="happy", status_code=200, content=b64decode(TEST_JPG_BASE64)
        )
        target = TEST_JPG_BASE64.decode("ascii")
        image_str = image_to_string(
            "https://not/an/image.jpg", image_format="JPEG", prefix=False
        )
        self.assertEqual(image_str, target)

        target = (IMG_BASE64_PREFIX + target.encode("ascii")).decode()
        image_str = image_to_string(b"https://not/an/image.jpg", image_format="JPEG")
        self.assertEqual(image_str, target)

        # Test all other valid cases

        # Test PNG conversion from image with prefix
        target = (IMG_BASE64_PREFIX + TEST_PNG_BASE64).decode()
        image_str = image_to_string(self.test_png, quality=100, optimize=True)
        self.assertEqual(image_str, target)

        # Test PNG conversion from image without prefix
        target = TEST_PNG_BASE64.decode()
        image_str = image_to_string(
            self.test_png, quality=100, optimize=True, prefix=False
        )
        self.assertEqual(image_str, target)

        # Test JPEG conversion from image with prefix
        target = (IMG_BASE64_PREFIX + TEST_JPG_BASE64).decode()
        image_str = image_to_string(self.test_jpg, image_format="JPEG")
        self.assertEqual(image_str, target)

        # Test JPEG conversion from image without prefix
        target = TEST_JPG_BASE64.decode()
        image_str = image_to_string(self.test_jpg, image_format="JPEG", prefix=False)
        self.assertEqual(image_str, target)

        # Test conversion from PNG string with prefix
        target = (IMG_BASE64_PREFIX + TEST_PNG_BASE64).decode()
        image_str = image_to_string(TEST_PNG_BASE64.decode(), prefix=True)
        self.assertEqual(image_str, target)

        # Test conversion from JPG string without prefix
        target = TEST_JPG_BASE64.decode()
        image_str = image_to_string(TEST_JPG_BASE64.decode(), prefix=False)
        self.assertEqual(image_str, target)

        # Test conversion from JPG string with truncated prefix
        target = TEST_JPG_BASE64.decode()
        image_str = image_to_string(
            (IMG_BASE64_PREFIX + TEST_JPG_BASE64).decode(), prefix=False
        )
        self.assertEqual(image_str, target)

        # Test conversion from PNG bytes with prefix
        target = (IMG_BASE64_PREFIX + TEST_PNG_BASE64).decode()
        image_str = image_to_string(TEST_PNG_BASE64, prefix=True)
        self.assertEqual(image_str, target)

        # Test conversion from JPG bytes without prefix
        target = TEST_JPG_BASE64.decode()
        image_str = image_to_string(TEST_JPG_BASE64, prefix=False)
        self.assertEqual(image_str, target)

        # Test conversion from JPG bytes with truncated prefix
        target = TEST_JPG_BASE64.decode()
        image_str = image_to_string((IMG_BASE64_PREFIX + TEST_JPG_BASE64), prefix=False)
        self.assertEqual(image_str, target)

    def test_count_colors(self):
        color_count = count_colors(None)
        self.assertEqual(color_count, 0)

        color_count = count_colors(self.test_png)
        self.assertEqual(color_count, 1.75)

        color_count = count_colors(self.test_jpg)
        self.assertEqual(color_count, 6)

    def test_overlay_images(self):

        with self.assertRaises(ValueError):
            overlay_images(None)
        with self.assertRaises(ValueError):
            overlay_images("")
        with self.assertRaises(ValueError):
            overlay_images([])
        with self.assertRaises(ValueError):
            overlay_images([self.test_png])

        overlaid = overlay_images([self.test_png, self.test_jpg])
        result = get_base64_for(overlaid, "PNG")
        self.assertEqual(result, TEST_OVERLAID_PNG_JPG)

    def test_make_color_transparent(self):

        with self.assertRaises(ValueError):
            make_color_transparent(None, (0, 0, 0, 0))
        with self.assertRaises(ValueError):
            make_color_transparent("", (0, 0, 0, 0))
        with self.assertRaises(ValueError):
            make_color_transparent([], (0, 0, 0, 0))

        transparent = make_color_transparent(self.test_png, (205, 205, 205, 255))
        result = get_base64_for(transparent, "PNG")
        self.assertEqual(result, TEST_TRANPARENT_PNG)

        transparent = make_color_transparent(self.test_jpg, (205, 205, 205, 255))
        result = get_base64_for(transparent.convert("RGB"), "JPEG")
        self.assertEqual(result, TEST_TRANPARENT_JPG)

    def test_stack_images_vertically(self):

        with self.assertRaises(ValueError):
            stack_images_vertically(None)
        with self.assertRaises(ValueError):
            stack_images_vertically("")
        with self.assertRaises(ValueError):
            stack_images_vertically([])

        stacked = stack_images_vertically([self.test_png])
        result = get_base64_for(stacked, "PNG")
        self.assertEqual(result, TEST_STACKED_PNG)

        stacked = stack_images_vertically([self.test_jpg])
        result = get_base64_for(stacked.convert("RGB"), "JPEG")
        self.assertEqual(result, TEST_STACKED_JPG)


TEST_PNG_BASE64 = (
    # Generated from test.png with quality:100 and optimize:True
    b"iVBORw0KGgoAAAANSUhEUgAAACAAAAAgAgMAAAAOFJJnAAAACVBMVEXf39/Nzc3Ozs5AK8nSAAAAOklEQVR42mNgyGTIZMhkyGJigAIkxhuGNwxvG"
    b"F4zhEIhUwiDCIMIgwiSmjVQRQwwRUxQJaJD2xwYAwAomidhJiUUQAAAAABJRU5ErkJggg=="
)
TEST_PNG_BYTES = (
    # Generated from test.png with quality:100 and optimize:True
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00 \x00\x00\x00 \x02\x03\x00\x00\x00\x0e\x14\x92g\x00\x00\x00\tPLTE"
    b"\xdf\xdf\xdf\xcd\xcd\xcd\xce\xce\xce@+\xc9\xd2\x00\x00\x00:IDATx\xdac`\xc8d\xc8d\xc8d\xc8bb\x80\x02$\xc6\x1b\x867"
    b"\x0co\x18^3\x84B!S\x08\x83\x08\x83\x08\x83\x08\x92\x9a5PE\x0c0ELP%\xa2C\xdb\x1c\x18\x03\x00(\x9a'a&%\x14@\x00\x00"
    b"\x00\x00IEND\xaeB`\x82"
)
TEST_STACKED_PNG = (
    b"iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAiElEQVR4nO2XQQrAMAgEVXxB/v+3/CBfsNiTSNpekkhh5xSyF8nKsuHeu1FgjEHMf"
    b"J/NjFprtEt3hIqR6gF0dulP98ZKXd2TyMyznbrGhXiaPC7Val2oGP3ya/dO6GnPs66nPY+6U78DNAE5kEEOGHIggRww9IEE+oChDyTQBwz/gj/9C6"
    b"R6gAsU7QuXQ0M9cAAAAABJRU5ErkJggg=="
)
TEST_TRANPARENT_PNG = (
    b"iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAjUlEQVR4nO2X0QnAIAxEE8kgrpD9h3AE3cRiv9Jg2x9tKNz7zCEE7wgJ11o7GXLOX"
    b"Eo5a6rKrbVt+iBRMCm6AZkVx9c9PVqpc+8Xi2jm2U5dbCDuOrehWq0nCkbe/NqdCfnac6/L155bfRCfAZqAOeDBHFDMAQfmgGIfcGAfUOwDDuwDir"
    b"vgT3dBim7gAJAlGLoqFiEVAAAAAElFTkSuQmCC"
)
TEST_JPG_BASE64 = (
    # Generated from test.jpg with quality and optimization unspecified
    b"/9j/4AAQSkZJRgABAQAAAQABAAD/"
    b"2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/"
    b"2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/"
    b"wAARCAAgACADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/"
    b"8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdIS"
    b"UpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+"
    b"Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/"
    b"8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERU"
    b"ZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna"
    b"4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD1b/j6/wBnb+PWj/j6/wBnb+NH/H1/s7fxo/4+v9nb+NAB/wAfX+zt/Gj/AI+f9nb+NH/"
    b"H1/s7fxo/4+v9nb+NAB/x9f7O38aP+Pr/AGdv40f8fP8As7fxo/4+v9nb+NAB/wAfX+zt/Gj/AI+v9nb+NH/H1/s7fxo/4+v9nb+PWgD/2Q=="
)
TEST_JPG_BYTES = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x01\x01\x01\x01\x01\x01\x01"
    b"\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01"
    b"\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01"
    b"\x01\xff\xdb\x00C\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01"
    b"\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01"
    b'\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\xff\xc0\x00\x11\x08\x00 \x00 \x03\x01"\x00\x02\x11\x01\x03'
    b"\x11\x01\xff\xc4\x00\x16\x00\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\n\xff\xc4"
    b'\x00&\x10\x00\x00\x04\x04\x07\x01\x00\x03\x00\x00\x00\x00\x00\x00\x00\x00\x01\x12\x13\x14\x03\x05"B\x11\x156Qct'
    b"\x94$\x061a\xff\xc4\x00\x14\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xc4\x00"
    b"\x14\x11\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01\x00\x02\x11"
    b"\x03\x11\x00?\x00\xd5\x96\xba\xc7\xf5+\xca\xc3\x01\x10\xfb\x97\x7f\xfd\xf8\xd2\x18L\xf9\x0e\xa5\x84\xaak\xad"
    b"\xa5yXw\x97}\xe3Ha3\xe4:\x96\x12\xa6\xba\xdaW\x95\x87yw\xde4\x86\x13>C\xa9a*k\xad\xa5yXw\x97}\xe3Ha3\xe4:\x96\x12"
    b"\xa0k\xad\xa5yXw\x97}\xe3Ha3\xe4:\x96\x12\xaa\x02?\x9c\x8e!\x84\xacea\xde]\xf7\x8d!\x84\xcf\x90\xeaXJ\xa6\xba"
    b"\xdaW\x95\x87yw\xde4\x86\x13>C\xa9a*k\xad\xa5yXw\x97}\xe3Ha3\xe4:\x96\x12\xa0k\xad\xa5yXw\x97}\xe3Ha3\xe4:\x96"
    b"\x12\xa6\xba\xdaW\x95\x87yw\xde4\x86\x13>C\xa9a*\xa2\x03\xf9\xc8\xe08J\xc6V\x1d\xe5\xdfx\xd2\x18L\xf9\x0e\xa5\x84"
    b"\xaak\xad\xa5yXw\x97}\xe3Ha3\xe4:\x96\x12\xa0k\xad\xa5yXw\x97}\xe3Ha3\xe4:\x96\x12\xa6\xba\xdaW\x95\x87yw\xde4"
    b"\x86\x13>C\xa9a*k\xad\xa5yXw\x97}\xe3Ha3\xe4:\x96\x12\xab\xae\xb0\xfdJ\xf2\xb0\xc4\x00~\xe5\xdf\xff\x00>4\x86"
    b"\x13>C\xa9a*\x0f\xff\xd9"
)
TEST_STACKED_JPG = (
    b"/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0"
    b"Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/"
    b"wAARCAAgACADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/"
    b"8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0"
    b"RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19"
    b"jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAx"
    b"EEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0"
    b"dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/"
    b"9oADAMBAAIRAxEAPwD1b/j6/wBnb+PWj/j6/wBnb+NH/H1/s7fxo/4+v9nb+NAB/wAfX+zt/Gj/AI+f9nb+NH/H1/s7fxo/4+v9nb+NAB/"
    b"x9f7O38aP+Pr/AGdv40f8fP8As7fxo/4+v9nb+NAB/wAfX+zt/Gj/AI+v9nb+NH/H1/s7fxo/4+v9nb+PWgD/2Q=="
)
TEST_TRANPARENT_JPG = (
    b"/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PT"
    b"gyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAA"
    b"gACADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJ"
    b"xFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKT"
    b"lJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/"
    b"8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzU"
    b"vAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqO"
    b"kpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD2UqixKXSYAyBgGHlnK/nxz+"
    b"lSf8ev/PX/AFn+5nb+eQc0f8ev/PX/AFn+5nb+eQc0f8ev/PX/AFn+5nb+eQc0AH/Hr/z1/wBZ/uZ2/nkHNRzQosRjkWUgyem37vcdcjmpP+PX/"
    b"nr/AKz/AHM7fzyDmj/j1/56/wCs/wBzO388g5oAP+PX/nr/AKz/AHM7fzyDmj/j1/56/wCs/wBzO388g5qOGZFiEkbSkGT12/d7Hrkc1J/x6/"
    b"8APX/Wf7mdv55BzQAf8ev/AD1/1n+5nb+eQc0f8ev/AD1/1n+5nb+eQc0f8ev/AD1/1n+5nb+eQc1GGRYmCPMAZCpKnyzlfz45/SgD/9k="
)
TEST_OVERLAID_PNG_JPG = (
    b"iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAw0lEQVR4nO2X6w2FIAyF26YTsP9uTAAr1GDShIAXclWKUb4/Po40xVMroPdeICPGC"
    b"Ii4n4sIOOeg1HPO6Bo/HQkapASOSAM1yBldn0nxmwn0glxBJ8ctsTf4Dp3v8PSKzvlrbnk+SieYDJdZaXVa1QSXnoQQTGuCRnzn/+gEk2H4eh8ga8"
    b"9LCJ5QA2LoeZWAM/Z89YESru6sPnDA6gPylj6AiNV6gy3XgHqd/xcIJsPw9fUAP2JfgAZ7wF/sb2Ck573JbVge9t/la3LdAAAAAElFTkSuQmCC"
)
