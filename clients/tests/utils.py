import os
import pathlib
import requests
import types
import unittest

from hashlib import md5
from io import BytesIO
from PIL import Image
from unittest import mock

from ..utils.geometry import Extent, SpatialReference
from ..wms import WMS_EXCEPTION_FORMAT


BUILTIN_SIMPLE = (bool, str, int, float)
BUILTIN_COMPLEX = (dict, list, set, tuple)
BUILTIN_INDEXED = (list, tuple)
BUILTIN_TYPES = BUILTIN_SIMPLE + BUILTIN_COMPLEX

WEB_MERCATOR_WKT = """
GEOGCS["WGS 84",
    DATUM["WGS_1984",
        SPHEROID["WGS 84",6378137,298.257223563,
            AUTHORITY["EPSG","7030"]],
        AUTHORITY["EPSG","6326"]],
    PRIMEM["Greenwich",0,
        AUTHORITY["EPSG","8901"]],
    UNIT["degree",0.0174532925199433,
        AUTHORITY["EPSG","9122"]],
    AUTHORITY["EPSG","4326"]]
"""

DEFAULT_IMG_HASH = "93d44c4c38607ac0834c68fc2b3dc92b"
DEFAULT_IMG_DIMS = (32, 32)
MAPSERVICE_IMG_DIMS = (946, 627)


def get_default_image():
    test_png = get_test_directory() / "data" / "test.png"
    with open(test_png, mode="rb") as image_data:
        return Image.open(BytesIO(image_data.read())).convert("RGBA")


def get_test_directory():
    return pathlib.Path(os.path.dirname(os.path.abspath(__file__)))


def get_extent(web_mercator=False):
    return Extent(get_extent_dict(web_mercator))


def get_extent_dict(web_mercator=False):
    extent_dict = {
        "xmin": -180.0, "ymin": -90.0, "xmax": 180.0, "ymax": 90.0,
        "spatial_reference": get_spatial_reference_dict(web_mercator)
    }
    if web_mercator:
        extent_dict.update({
            "xmin": -20037508.342789244,
            "ymin": -20037471.205137067,
            "xmax": 20037508.342789244,
            "ymax": 20037471.20513706
        })

    return extent_dict


def get_extent_list(web_mercator=False):
    if not web_mercator:
        return [-180.0, -90.0, 180.0, 90.0]
    else:
        return [-20037508.342789244, -20037471.205137067, 20037508.342789244, 20037471.20513706]


def get_extent_object(web_mercator=False):
    extent_dict = get_extent_dict(web_mercator)
    extent_dict["spatial_reference"] = get_spatial_reference(web_mercator)

    return get_object(extent_dict)


def get_object(props):
    return type("object", (), props)


def get_object_properties(obj):
    def is_callable(val):
        return isinstance(val, (types.FunctionType, types.MethodType))  # callable(val)

    return {
        prop for prop in dir(obj)
        if not prop.startswith("__")
        and not is_callable(getattr(obj, prop))
    }


def get_spatial_reference(web_mercator=False):
    return SpatialReference(get_spatial_reference_dict(web_mercator))


def get_spatial_reference_dict(web_mercator=False):
    return {
        "latestWkid": "3857" if web_mercator else "4326",
        "srs": "EPSG:3857" if web_mercator else "EPSG:4326",
        "wkid": 3857 if web_mercator else 4326,
        "wkt": WEB_MERCATOR_WKT,
    }


def get_spatial_reference_object(web_mercator=False):
    spatial_reference_dict = get_spatial_reference_dict(web_mercator)
    spatial_reference_dict["latest_wkid"] = spatial_reference_dict.pop("latestWkid")

    return get_object(spatial_reference_dict)


def mock_thread(target, args, kwargs=None):
    target(*args, **(kwargs or {}))


class BaseTestCase(unittest.TestCase):

    def setUp(self):
        self.data_directory = get_test_directory() / "data"

    def _assert_props(self, target_data, props):
        if props is None:
            props = set(target_data.keys())
        elif isinstance(props, str):
            props = set(props.split(","))

        self.assertTrue(bool(props))

        for prop in props:
            self.assertTrue(not prop or prop in target_data, f'Invalid test property "{prop}"')

        return props

    def assert_object_field(self, obj_or_objects, target_data, props=None):
        if isinstance(target_data, BUILTIN_INDEXED):
            self.assertEqual(len(obj_or_objects), len(target_data))
            for idx, obj in enumerate(obj_or_objects):
                self.assert_object_field(obj, target_data[idx])
        else:
            props = self._assert_props(target_data, props)
            obj_data = {k: v for k, v in obj_or_objects.get_data().items() if k in props}

            self.assertEqual(obj_data, target_data)

    def assert_object_values(self, obj, target_data, props=None):

        props = self._assert_props(target_data, props)

        for prop in target_data:
            if prop not in props:
                self.assertTrue(hasattr(obj, prop), f'Missing property "{prop}"')
            else:
                test_val = getattr(obj, prop, None)
                if hasattr(test_val, "get_data"):
                    test_val = test_val.get_data()

                target_val = target_data[prop]
                if hasattr(target_val, "get_data"):
                    target_val = target_val.get_data()

                self.assert_objects_are_equal(test_val, target_val, f'Invalid value for "{prop}"')

    def assert_objects_are_equal(self, first, second, msg=None):

        first_is_primative = isinstance(first, BUILTIN_TYPES)
        second_is_primative = isinstance(second, BUILTIN_TYPES)

        try:
            if first_is_primative or second_is_primative:
                raise ValueError

            first_props = get_object_properties(first)
            second_props = get_object_properties(second)

            if not first_props == second_props:
                raise ValueError

            for prop in first_props:
                first_val = getattr(first, prop)
                second_val = getattr(second, prop)
                self.assert_objects_are_equal(first_val, second_val, msg)

        except ValueError:
            if not isinstance(first, BUILTIN_INDEXED):
                self.assertEqual(first, second, msg)
            else:
                self.assertTrue(isinstance(second, BUILTIN_INDEXED))
                self.assertEqual(len(first), len(second))

                for idx, val in enumerate(first):
                    self.assert_objects_are_equal(val, second[idx], msg)


class GeometryTestCase(BaseTestCase):

    extent_props = {
        "xmin": -180, "ymin": -90, "xmax": 180, "ymax": 90,
    }

    spatial_reference_props = {
        "latest_wkid": "4326",
        "srs": "EPSG:4326",
        "wkid": 4326,
        "wkt": WEB_MERCATOR_WKT,
    }

    def assert_extent(self, extent, props="xmin,ymin,xmax,ymax"):
        self.assertTrue(extent is not None)

        self.assert_object_values(extent, self.extent_props, props)
        self.assert_spatial_reference(getattr(extent, "spatial_reference", None), props="")

    def assert_spatial_reference(self, spatial_reference, props="latest_wkid,srs,wkid,wkt"):
        self.assertTrue(spatial_reference is not None)
        self.assert_object_values(spatial_reference, self.spatial_reference_props, props)


class ResourceTestCase(BaseTestCase):

    def setUp(self):
        super(ResourceTestCase, self).setUp()

        self.cookies = None
        self.headers = {"content-type": WMS_EXCEPTION_FORMAT}

    def assert_get_image(self, client, target_hash=DEFAULT_IMG_HASH, extent=None, dimensions=None, **image_params):
        client._session = self.mock_mapservice_session(
            self.data_directory / "test.png",
            mode="rb",
            headers={"content-type": "image/png"}
        )

        if dimensions is None:
            dimensions = DEFAULT_IMG_DIMS
        img = client.get_image(extent or client.full_extent, *dimensions, **image_params)

        self.assertEqual(img.size, dimensions)
        self.assertEqual(img.mode, "RGBA")
        self.assertEqual(md5(img.tobytes()).hexdigest(), target_hash)

    def mock_mapservice_request(
        self, mock_method, service_url, data_path, mode="r", ok=True, cookies=None, headers=None
    ):

        with open(data_path, mode=mode) as mapservice_data:
            return mock_method(
                service_url,
                status_code=200 if ok else 500,
                text=mapservice_data.read(),
                cookies=self.cookies if cookies is None else cookies,
                headers=self.headers if headers is None else headers
            )

    def mock_mapservice_session(self, data_path, mode="r", ok=True, headers=None):

        mock_headers = self.headers if headers is None else headers

        mock_session = mock.Mock(get=mock.Mock())
        mock_session.headers = mock.Mock()
        mock_session.headers.__getitem__ = mock.Mock()
        mock_session.headers.__getitem__.side_effect = mock_headers.__getitem__
        mock_session.headers.__setitem__ = mock.Mock()
        mock_session.headers.__setitem__.side_effect = mock_headers.__setitem__

        with open(data_path, mode=mode) as mapservice_data:

            mapservice_text = mapservice_content = mapservice_data.read()
            if isinstance(mapservice_content, str):
                mapservice_content = mapservice_text.encode()

            response = mock_session.get.return_value = mock.Mock(
                ok=ok,
                status_code=200 if ok else 500,
                content=mapservice_content,
                text=mapservice_text,
                headers=mock_headers
            )
            if not ok:
                response.raise_for_status.side_effect = requests.exceptions.HTTPError

        return mock_session
