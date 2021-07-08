import io
import pathlib

from base64 import b64decode, b64encode
from PIL import Image
from unittest import mock

from ..utils.images import base64_to_image, image_to_bytes, image_to_base64, image_to_string
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
            ok=False,
            reason="nope",
            status_code=500,
            content=b"Server Error"
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
            ok=True,
            reason="happy",
            status_code=200,
            content=b64decode(TEST_PNG_BASE64)
        )
        target = TEST_PNG_BASE64.decode("ascii")
        image_str = image_to_string("https://not/an/image.png", quality=100, optimize=True, prefix=False)
        self.assertEqual(image_str, target)

        target = (IMG_BASE64_PREFIX + target.encode("ascii")).decode()
        image_str = image_to_string(b"https://not/an/image.png", quality=100, optimize=True)
        self.assertEqual(image_str, target)

        # Test JPEG conversion (must be tested without optimization)
        mock_get.return_value = mock.Mock(
            ok=True,
            reason="happy",
            status_code=200,
            content=b64decode(TEST_JPG_BASE64)
        )
        target = TEST_JPG_BASE64.decode("ascii")
        image_str = image_to_string("https://not/an/image.jpg", image_format="JPEG", prefix=False)
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
        image_str = image_to_string(self.test_png, quality=100, optimize=True, prefix=False)
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
        image_str = image_to_string((IMG_BASE64_PREFIX + TEST_JPG_BASE64).decode(), prefix=False)
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
    b"iVBORw0KGgoAAAANSUhEUgAAACAAAAAgAgMAAAAOFJJnAAAADFBMVEXf39/"
    b"Nzc3Ozs4DAwN3qhFrAAAAIUlEQVR42mNgyATDLAYsjFA0yLASKodgwKUQrGFhDowBAB/QMmr7D/cBAAAAAElFTkSuQmCC"
)
TEST_PNG_BYTES = (
    # Generated from test.png with quality:100 and optimize:True
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00 \x00\x00\x00 \x02\x03\x00\x00\x00\x0e\x14\x92g\x00\x00\x00"
    b"\x0cPLTE\xdf\xdf\xdf\xcd\xcd\xcd\xce\xce\xce\x03\x03\x03w\xaa\x11k\x00\x00\x00!IDATx\xdac`\xc8\x04\xc3,\x06,"
    b"\x8cP4\xc8\xb0\x12*\x87`\xc0\xa5\x10\xacaa\x0e\x8c\x01\x00\x1f"
    b"\xd02j\xfb\x0f\xf7\x01\x00\x00\x00\x00IEND\xaeB`\x82"
)
TEST_STACKED_PNG = (
    b"iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAGklEQVR4nO3BAQEAAACCIP+vbkhAAQAAAO8GECAAARlDNO4AAAAASUVORK5CYII="
)
TEST_TRANPARENT_PNG = (
    b"iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAkklEQVR4nO2UwQ0EIQwDJysKoYX0XwQlQCfsl0W5uw850Cp+eoQUycZSa+"
    b"0MyjlLKaUDqKq01tw4wMVmbT8gWaaqyrdHK7n0/ogIKzNPnsZCfLp8LNVqvr8Dv/IC306kf2c+c/MXeGY+"
    b"cjihA5YZOzArdiB2wIvDCR2wzNiBWbEDsQNeHE7ogGXGDsx69Q5sP+AGkCUYuteIHK0AAAAASUVORK5CYII="
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
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x01\x01\x01\x01\x01\x01"
    b"\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01"
    b"\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01"
    b"\x01\x01\xff\xdb\x00C\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01"
    b"\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01"
    b'\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\x01\xff\xc0\x00\x11\x08\x00 \x00 \x03\x01"\x00\x02\x11'
    b"\x01\x03\x11\x01\xff\xc4\x00\x16\x00\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\n"
    b'\xff\xc4\x00&\x10\x00\x00\x04\x04\x07\x01\x00\x03\x00\x00\x00\x00\x00\x00\x00\x00\x01\x13\x12\x14\x05\x03"Bc'
    b"\x156t\x94Q\x11$\x061a\xff\xc4\x00\x14\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\xff\xc4\x00\x14\x11\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x0c\x03\x01"
    b"\x00\x02\x11\x03\x11\x00?\x00\xd5\x96\xba\xf7\xf5\x0b\xca\xc3\xc1\x10\xfb\x8f\x7f\xfd\xf8\xca\x19L\xf1\x16e\x88"
    b'\xaak\xae\xa1yXo\x8f}\xc3(e3\xc4Y\x96"\xa6\xba\xea\x17\x95\x86\xf8\xf7\xdc2\x86S<E\x99b*k\xae\xa1yXo\x8f}\xc3(e3'
    b'\xc4Y\x96"\xa0k\xae\xa1yXo\x8f}\xc3(e3\xc4Y\x96"\xaa\x02?\x9c\x8f\xa1\xe4,aa\xbe=\xf7\x0c\xa1\x94\xcf\x11fX\x8a'
    b'\xa6\xba\xea\x17\x95\x86\xf8\xf7\xdc2\x86S<E\x99b*k\xae\xa1yXo\x8f}\xc3(e3\xc4Y\x96"\xa0k\xae\xa1yXo\x8f}\xc3(e3'
    b'\xc4Y\x96"\xa6\xba\xea\x17\x95\x86\xf8\xf7\xdc2\x86S<E\x99b*\xa2\x03\xf9\xc8\xf8>B\xc6\x16\x1b\xe3\xdfp\xca\x19L'
    b'\xf1\x16e\x88\xaak\xae\xa1yXo\x8f}\xc3(e3\xc4Y\x96"\xa0k\xae\xa1yXo\x8f}\xc3(e3\xc4Y\x96"\xa6\xba\xea\x17\x95'
    b'\x86\xf8\xf7\xdc2\x86S<E\x99b*k\xae\xa1yXo\x8f}\xc3(e3\xc4Y\x96"\xab\xae\xbc\xfdB\xf2\xb0\xf4\x00~\xe3\xdf\xff'
    b"\x00>2\x86S<E\x99b*\x0f\xff\xd9"
)
TEST_STACKED_JPG = (
    b"/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PT"
    b"gyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/"
    b"wAARCAAgACADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRI"
    b"hMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqD"
    b"hIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/"
    b"8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzU"
    b"vAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanq"
    b"KmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD5/ooooAKKKKACiiigAooooA//2Q=="
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
    b"iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAxUlEQVR4nO1XURLEEBRLOu8E7n83J+AKb7/"
    b"sWFWmVdYM+SPtm0ciA621igjee5AEAKgqjDFI+RhP+FCfJA4UoKrZeZLfIk/48I2qlhuoFWlBWJyUyNrPb/DyhqYtvMTbXNK8F1/"
    b"0wAhI2lVwZ4yenpBUE+fcz7i3J7IStJ7zO/z/PZCbXCoHDmCs5inm8MBIzU8NjNZ850CKnQM7B9bKAZKn+"
    b"0b2FPS6A4Zx7Ic5PJBiqRyY410w4g14Bcm9A+4WKfG1xX0AWB72305QlfQAAAAASUVORK5CYII="
)
