import unittest

from clients.utils.geometry import Extent, SpatialReference


BUILTIN_SIMPLE = (bool, str, int, float)
BUILTIN_COMPLEX = (dict, list, set, tuple)
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


def get_extent():
    return Extent(get_extent_dict())


def get_extent_dict():
    return {
        "xmin": -180, "ymin": -90, "xmax": 180, "ymax": 90,
        "spatial_reference": get_spatial_reference_dict()
    }


def get_extent_list():
    return [-180, -90, 180, 90]


def get_extent_object():
    extent_dict = get_extent_dict()
    extent_dict["spatial_reference"] = get_spatial_reference()

    return get_object(extent_dict)


def get_object(props):
    return type("object", (), props)


def get_object_properties(obj):
    return {
        prop for prop in dir(obj)
        if not prop.startswith("__")
        and not callable(getattr(obj, prop))
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


class BaseTestCase(unittest.TestCase):

    def assert_object_values(self, obj, target, props=None):

        if props is None:
            props = set(target.keys())
        elif isinstance(props, str):
            props = set(props.split(","))

        for prop in props:
            self.assertTrue(not prop or prop in target, f'Invalid test property "{prop}"')

        for prop in target:
            if prop not in props:
                self.assertTrue(hasattr(obj, prop), f'Missing property "{prop}"')
            else:
                test_val = getattr(obj, prop, None)
                if prop != "get_data":
                    self.assert_objects_are_equal(test_val, target[prop], f'Invalid value for "{prop}"')
                else:
                    self.assertTrue(callable(test_val), f'Uncallable value for "get_data"')
                    self.assertEqual(obj.get_data(), target[prop])

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
            if type(first) is not type(second):
                self.assertEqual(first, second, msg)
            elif isinstance(first, BUILTIN_SIMPLE):
                self.assertEqual(first, second, msg)
            elif isinstance(first, (dict, set)):
                self.assertEqual(first, second, msg)
            elif isinstance(first, (list, tuple)):
                self.assertEqual(len(first), len(second))
                for idx, val in enumerate(first):
                    self.assert_objects_are_equal(val, second[idx], msg)
            else:
                self.assertEqual(first, second, msg)


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
