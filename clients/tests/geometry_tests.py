import json

from decimal import Decimal
from statistics import mean

from ..arcgis import ARCGIS_RESOLUTIONS
from ..exceptions import BadExtent, BadSpatialReference
from ..utils.geometry import Extent, SpatialReference, TileLevels
from ..utils.geometry import extract_significant_digits, union_extent
from ..utils.geometry import GLOBAL_EXTENT_WEB_MERCATOR, GLOBAL_EXTENT_WGS84, GLOBAL_EXTENT_WGS84_CORRECTED

from .utils import BaseTestCase, GeometryTestCase, WEB_MERCATOR_WKT
from .utils import get_extent, get_extent_dict, get_extent_list, get_extent_object, get_object
from .utils import get_spatial_reference, get_spatial_reference_dict, get_spatial_reference_object


class ExtentTestCase(GeometryTestCase):

    def test_extent(self):
        """ Tests successful extent creation """

        extent = Extent(get_extent_dict())
        self.assert_extent(extent)
        self.assertEqual(extent._original_format, "dict")

        extent = Extent(json.dumps(get_extent_dict()))
        self.assert_extent(extent)
        self.assertEqual(extent._original_format, "dict")

        # Test with camel-cased spatial reference key
        extent_dict = get_extent_dict()
        extent_dict["spatialReference"] = extent_dict.pop("spatial_reference")
        extent = Extent(extent_dict)
        self.assert_extent(extent)
        self.assertEqual(extent._original_format, "dict")

        # Test with overridden invalid spatial reference
        extent_dict = get_extent_dict()
        extent_dict["spatial_reference"] = []
        extent = Extent(extent_dict, get_spatial_reference())
        self.assert_extent(extent)
        self.assertEqual(extent._original_format, "dict")

        # Test with overridden spatial reference when missing in dict
        extent_dict = get_extent_dict()
        extent_dict.pop("spatial_reference")
        extent = Extent(extent_dict, get_spatial_reference())
        self.assert_extent(extent)
        self.assertEqual(extent._original_format, "dict")

        extent = Extent(get_extent_list(), spatial_reference="EPSG:4326")
        self.assert_extent(extent)
        self.assertEqual(extent._original_format, "list")

        extent = Extent(json.dumps(get_extent_list()), spatial_reference="EPSG:4326")
        self.assert_extent(extent)
        self.assertEqual(extent._original_format, "list")

        extent = Extent(tuple(get_extent_list()), spatial_reference="EPSG:4326")
        self.assert_extent(extent)
        self.assertEqual(extent._original_format, "list")

        self.assert_extent(get_extent())
        self.assert_extent(get_extent_object())

        # Test with overridden invalid spatial reference
        extent_obj = get_extent_object()
        extent_obj.spatial_reference = []
        extent = Extent(extent_obj, get_spatial_reference())
        self.assert_extent(extent)
        self.assertEqual(extent._original_format, "obj")

        # Test with overridden spatial reference when missing in object
        extent_obj = get_extent_object()
        delattr(extent_obj, "spatial_reference")
        extent = Extent(extent_obj, get_spatial_reference())
        self.assert_extent(extent)
        self.assertEqual(extent._original_format, "obj")

    def test_invalid_extent(self):
        """ Tests invalid parameters for extent creation """

        # Invalid extent parameters

        with self.assertRaises(BadExtent):
            Extent(None)
        with self.assertRaises(BadExtent):
            Extent(set(get_extent_list()))

        # Invalid extent dicts

        with self.assertRaises(BadExtent):
            extent_dict = get_extent_dict()
            extent_dict.pop("xmin")
            Extent(extent_dict)

        with self.assertRaises(BadExtent):
            extent_dict = get_extent_dict()
            extent_dict["xmin"] = "abc"
            Extent(extent_dict)

        with self.assertRaises(BadSpatialReference):
            extent_dict = get_extent_dict()
            extent_dict.pop("spatial_reference")
            Extent(extent_dict)

        # Invalid extent lists

        spatial_ref = SpatialReference("EPSG:4326")

        with self.assertRaises(BadExtent):
            extent_list = get_extent_list()[:2]
            Extent(extent_list, spatial_reference=spatial_ref)

        with self.assertRaises(BadExtent):
            extent_list = get_extent_list()
            extent_list[3] = "abc"
            Extent(extent_list, spatial_reference=spatial_ref)

        # Invalid extent objects

        with self.assertRaises(BadExtent):
            extent_obj = get_extent_object()
            del extent_obj.ymin
            Extent(extent_obj)

        with self.assertRaises(BadExtent):
            extent_obj = get_extent_object()
            extent_obj.ymin = "abc"
            Extent(extent_obj)

        with self.assertRaises(BadSpatialReference):
            extent_obj = get_extent_object()
            del extent_obj.spatial_reference
            Extent(extent_obj)

    def test_extent_repr(self):
        extent = get_extent()
        target = extent.as_json_string()
        result = extent.__repr__()
        self.assertEqual(result, target)

        extent = get_extent(web_mercator=True)
        target = extent.as_json_string()
        result = extent.__repr__()
        self.assertEqual(result, target)

    def test_extent_clone(self):
        extent = get_extent()
        cloned = extent.clone()

        self.assert_extent(cloned)
        self.assertIsNot(extent, cloned)
        self.assertIsNot(extent.spatial_reference, cloned.spatial_reference)

    def test_extent_as_dict(self):
        data = {
            "xmin": -179.1234,
            "ymin": -89.2345,
            "xmax": 179.3456,
            "ymax": 89.4567,
            "spatial_reference": {
                "latestWkid": "3857",
                "srs": "EPSG:3857",
                "wkid": 3857
            }
        }
        extent = Extent(data)

        # Test as_dict in ESRI format

        result = extent.as_dict(esri_format=True)
        for key in "xmin,ymin,xmax,ymax".split(","):
            self.assertEqual(result[key], data[key])

        self.assertIn("spatialReference", result)
        self.assertNotIn("spatial_reference", result)
        self.assertEqual(result["spatialReference"], {"wkid": extent.spatial_reference.wkid})

        # Test as_dict in non-ESRI format

        result = extent.as_dict(esri_format=False)
        for key in "xmin,ymin,xmax,ymax".split(","):
            self.assertEqual(result[key], data[key])

        self.assertIn("spatial_reference", result)
        self.assertNotIn("spatialReference", result)
        self.assertEqual(result["spatial_reference"], {"srs": extent.spatial_reference.srs})

        # Test as_dict with precision specified

        result = extent.as_dict(precision=2)
        for key in "xmin,ymin,xmax,ymax".split(","):
            self.assertEqual(result[key], round(data[key], 2))

    def test_extent_as_list(self):

        # Test with default WGS84 values
        target = list(GLOBAL_EXTENT_WGS84)
        result = get_extent().as_list()
        self.assertEqual(result, target)

        # Test with default WGS84 numeric string values (converts to float)
        target = list(GLOBAL_EXTENT_WGS84)
        result = Extent([str(coord) for coord in target], "EPSG:4326").as_list()
        self.assertEqual(result, target)

        # Test that raw list values are unchanged
        target = [-179.1234, -89.2345, 179.3456, 89.4567]
        result = Extent(target, "EPSG:4326").as_list()
        self.assertEqual(result, target)

    def test_extent_as_original(self):

        # Test as_original when it is a list

        extent = Extent((-179.1234, -89.2345, 179.3456, 89.4567), "EPSG:4326")
        self.assertEqual(extent._original_format, "list")
        self.assertEqual(extent.as_original(), extent.as_list())
        self.assertEqual(extent.as_original(precision=2), extent.as_list(precision=2))

        # Test as_original when it is a dict

        extent = Extent({
            "xmin": -179.1234,
            "ymin": -89.2345,
            "xmax": 179.3456,
            "ymax": 89.4567,
            "spatial_reference": {
                "latestWkid": "3857",
                "srs": "EPSG:3857",
                "wkid": 3857
            }
        })
        self.assertEqual(extent._original_format, "dict")
        self.assertEqual(extent.as_original(), extent.as_dict())
        self.assertEqual(extent.as_original(False, 2), extent.as_dict(False, 2))

        # Test as_original when it is an object

        extent = Extent(get_extent_object(web_mercator=True))
        self.assertEqual(extent._original_format, "obj")
        self.assertEqual(extent.as_original(), extent)

        target = extent.as_dict(False, 2)
        result = extent.as_original(False, 2).as_dict(False)
        self.assertEqual(result, target)

    def test_extent_as_bbox_string(self):
        extent = Extent((-179.1234, -89.2345, 179.3456, 89.4567), "EPSG:4326")

        target = "-179.1234,-89.2345,179.3456,89.4567"
        result = extent.as_bbox_string()
        self.assertEqual(result, target)

        target = "-179.12,-89.23,179.35,89.46"
        result = extent.as_bbox_string(precision=2)
        self.assertEqual(result, target)

    def test_extent_as_json_string(self):
        extent = Extent({
            "xmin": -179.1234,
            "ymin": -89.2345,
            "xmax": 179.3456,
            "ymax": 89.4567,
            "spatial_reference": {
                "latestWkid": "3857",
                "srs": "EPSG:3857",
                "wkid": 3857
            }
        })

        # Test in ESRI format
        target = (
            '{"spatialReference": {"wkid": 3857},'
            ' "xmax": 179.3456, "xmin": -179.1234, "ymax": 89.4567, "ymin": -89.2345'
            '}'
        )
        result = extent.as_json_string()
        self.assertEqual(result, target)

        # Test in non-ESRI format
        target = (
            '{"spatial_reference": {"srs": "EPSG:3857"},'
            ' "xmax": 179.3456, "xmin": -179.1234, "ymax": 89.4567, "ymin": -89.2345'
            '}'
        )
        result = extent.as_json_string(esri_format=False)
        self.assertEqual(result, target)

        # Test with precision specified
        target = (
            '{"spatialReference": {"wkid": 3857},'
            ' "xmax": 179.35, "xmin": -179.12, "ymax": 89.46, "ymin": -89.23'
            '}'
        )
        result = extent.as_json_string(precision=2)
        self.assertEqual(result, target)

    def test_extent_as_string(self):
        extent = Extent({
            "xmin": -179.1234,
            "ymin": -89.2345,
            "xmax": 179.3456,
            "ymax": 89.4567,
            "spatial_reference": {
                "latestWkid": "3857",
                "srs": "EPSG:3857",
                "wkid": 3857
            }
        })

        target = (
            '{"spatialReference": {"wkid": 3857},'
            ' "xmax": 179.3456, "xmin": -179.1234, "ymax": 89.4567, "ymin": -89.2345'
            '}'
        )
        result = str(extent)
        self.assertEqual(result, target)

    def test_extent_limit_to_global(self):

        with self.assertRaises(ValueError):
            get_extent(web_mercator=False).limit_to_global_extent()
        with self.assertRaises(ValueError):
            get_extent(web_mercator=False).limit_to_global_width()

        # Adjust x coords so they will be affected
        extent = get_extent(web_mercator=True)
        extent.xmin = -20037637.381773834
        extent.xmax = 20037637.381773834

        coords = extent.as_list()

        target = list(GLOBAL_EXTENT_WEB_MERCATOR)
        result = extent.limit_to_global_extent().as_list()
        self.assertEqual(result, target)
        self.assertEqual(extent.as_list(), coords)

        target = [GLOBAL_EXTENT_WEB_MERCATOR[0], extent.ymin, GLOBAL_EXTENT_WEB_MERCATOR[2], extent.ymax]
        result = extent.limit_to_global_width().as_list()
        self.assertEqual(result, target)
        self.assertEqual(extent.as_list(), coords)

    def test_extent_crosses_anti_meridian(self):
        with self.assertRaises(ValueError):
            get_extent(web_mercator=False).crosses_anti_meridian()

        extent = get_extent(web_mercator=True)
        self.assertFalse(extent.crosses_anti_meridian())

        extent.xmin = GLOBAL_EXTENT_WEB_MERCATOR[0]
        extent.xmax = 20037637.381773834
        self.assertTrue(extent.crosses_anti_meridian())

        extent.xmin = -20037637.381773834
        extent.xmax = GLOBAL_EXTENT_WEB_MERCATOR[2]
        self.assertTrue(extent.crosses_anti_meridian())

        extent.xmin = GLOBAL_EXTENT_WEB_MERCATOR[0]
        extent.xmax = GLOBAL_EXTENT_WEB_MERCATOR[2]
        self.assertFalse(extent.crosses_anti_meridian())

    def test_extent_negative_extent(self):
        with self.assertRaises(ValueError):
            get_extent(web_mercator=False).has_negative_extent()
        with self.assertRaises(ValueError):
            get_extent(web_mercator=False).get_negative_extent()

        extent = get_extent(web_mercator=True)
        self.assertFalse(extent.has_negative_extent())
        self.assertIsNone(extent.get_negative_extent())

        extent.xmin = -20037637.381773834
        self.assertTrue(extent.has_negative_extent())

        target = [20037379.303804655, extent.ymin, 60112525.02836773, extent.ymax]
        result = extent.get_negative_extent().as_list()
        self.assertEqual(result, target)

    def test_extent_fit_to_dimensions(self):
        extent = Extent(get_extent_list(), spatial_reference="EPSG:4326")

        # Test fit_to_dimensions

        target = [-180, -180.0, 180, 180.0]
        result = extent.fit_to_dimensions(100, 100).as_list()
        self.assertEqual(result, target)

        target = [-180, -360.0, 180, 360.0]
        result = extent.fit_to_dimensions(100, 200).as_list()
        self.assertEqual(result, target)

        target = list(GLOBAL_EXTENT_WGS84)
        result = extent.fit_to_dimensions(200, 100).as_list()
        self.assertEqual(result, target)

        target = [-360.0, -90.0, 360.0, 90.0]
        result = extent.fit_to_dimensions(400, 100).as_list()
        self.assertEqual(result, target)

        # Test fit_image_dimensions_to_extent

        target = (100, 30)
        result = extent.fit_image_dimensions_to_extent(100, 100)
        self.assertEqual(result, target)

        target = (100, -100)
        result = extent.fit_image_dimensions_to_extent(100, 200)
        self.assertEqual(result, target)

        target = (200, 100)
        result = extent.fit_image_dimensions_to_extent(200, 100)
        self.assertEqual(result, target)

        target = (118, 100)
        result = extent.fit_image_dimensions_to_extent(400, 100)
        self.assertEqual(result, target)

    def test_extent_get_center(self):

        # Test with WGS84
        target = (0.0, 0.0)
        result = get_extent().get_center()
        self.assertEqual(result, target)

        # Test with Web Mercator
        target = (0.0, -3.725290298461914e-09)
        result = get_extent(web_mercator=True).get_center()
        self.assertEqual(result, target)

        # Test with Web Mercator corrected
        target = (0.0, 0.0)
        result = Extent(GLOBAL_EXTENT_WGS84_CORRECTED, spatial_reference="EPSG:3857").get_center()
        self.assertEqual(result, target)

    def test_extent_get_dimensions(self):

        # Test with WGS84
        target = (360.0, 180.0)
        result = get_extent().get_dimensions()
        self.assertEqual(result, target)

        # Test with Web Mercator
        target = (40075016.68557849, 40074942.410274126)
        result = get_extent(web_mercator=True).get_dimensions()
        self.assertEqual(result, target)

        # Test with Web Mercator corrected
        target = (360.0, 170.1022)
        result = Extent(GLOBAL_EXTENT_WGS84_CORRECTED, spatial_reference="EPSG:3857").get_dimensions()
        self.assertEqual(result, target)

    def test_extent_get_geographic_labels(self):
        # Test WGS84 labels (not projected)
        target = ('180.00°W', '90.00°S', '180.00°E', '90.00°N')
        result = get_extent().get_geographic_labels()
        self.assertEqual(result, target)

        # Test WGS84 corrected labels (not projected)
        target = ('180.00°W', '85.05°S', '180.00°E', '85.05°N')
        result = Extent(GLOBAL_EXTENT_WGS84_CORRECTED, spatial_reference="EPSG:4326").get_geographic_labels()
        self.assertEqual(result, target)

        # Test Web Mercator labels
        target = ('180.00°W', '85.05°S', '180.00°E', '85.05°N')
        result = get_extent(web_mercator=True).get_geographic_labels()
        self.assertEqual(result, target)

    def test_extent_get_image_resolution(self):
        width = 946
        height = 627

        # Test in WGS84
        extent = get_extent(web_mercator=False)
        target = 0.33052793041913603
        result = extent.get_image_resolution(width, height)
        self.assertEqual(result, target)

        # Test in WGS84 corrected
        extent = Extent(GLOBAL_EXTENT_WGS84_CORRECTED, spatial_reference="EPSG:4326")
        target = 0.3213119494290692
        result = extent.get_image_resolution(width, height)
        self.assertEqual(result, target)

        # Test in Web Mercator
        extent = get_extent(web_mercator=True)
        target = 52034.80971876128
        result = extent.get_image_resolution(width, height)
        self.assertEqual(result, target)

    def test_extent_project_to_geographic(self):

        # Test invalid cases

        extent_dict = get_extent().as_dict()

        # Non-proj4 extent
        extent_dict["spatialReference"] = {"wkid": 44000}
        with self.assertRaises(ValueError, msg="Spatial reference is not valid for proj4"):
            Extent(extent_dict).project_to_geographic()

        # Test success cases

        geographic_srs = "EPSG:4326"

        # Test reprojection when extent is already Geographic (unchanged)
        target = list(GLOBAL_EXTENT_WGS84)
        result = get_extent().project_to_geographic()
        self.assertEqual(result.as_list(), target)
        self.assertEqual(result.spatial_reference.srs, geographic_srs)

        # Test reprojection of corrected WGS84 (unchanged)
        target = list(GLOBAL_EXTENT_WGS84_CORRECTED)
        result = Extent(GLOBAL_EXTENT_WGS84_CORRECTED, spatial_reference=geographic_srs).project_to_geographic()
        self.assertEqual(result.as_list(), target)
        self.assertEqual(result.spatial_reference.srs, geographic_srs)

        # Test reprojection of Web Mercator extent to WGS84
        target = list(GLOBAL_EXTENT_WGS84_CORRECTED)
        result = get_extent(web_mercator=True).project_to_geographic()
        self.assertEqual(result.as_list(), target)
        self.assertEqual(result.spatial_reference.srs, geographic_srs)

    def test_extent_project_to_web_mercator(self):

        extent = get_extent()

        # Test invalid cases

        extent_dict = extent.as_dict()

        # Non-proj4 extent
        extent_dict["spatialReference"] = {"wkid": 44000}
        with self.assertRaises(ValueError, msg="Spatial reference is not valid for proj4"):
            Extent(extent_dict).project_to_web_mercator()

        # Invalid projection coordinates
        extent_dict["spatialReference"] = "EPSG:9001"
        with self.assertRaises(ValueError, msg="Invalid projection coordinates"):
            Extent(extent_dict).project_to_web_mercator()

        # Test success cases

        mercator_srs = "EPSG:3857"

        # Test reprojection of WGS84 extent to Web Mercator
        target = [GLOBAL_EXTENT_WEB_MERCATOR[0], -20037471.205137067, GLOBAL_EXTENT_WEB_MERCATOR[2], 20037471.20513706]
        result = extent.project_to_web_mercator()
        self.assertEqual(result.as_list(), target)
        self.assertEqual(result.spatial_reference.srs, mercator_srs)

        # Test original WGS84 extent is corrected after reprojection
        target = list(GLOBAL_EXTENT_WGS84_CORRECTED)
        self.assertEqual(extent.as_list(), target)
        self.assertEqual(extent.spatial_reference.srs, "EPSG:4326")

        # Test reprojection when extent is already Web Mercator (unchanged)
        target = [GLOBAL_EXTENT_WEB_MERCATOR[0], -20037471.205137067, GLOBAL_EXTENT_WEB_MERCATOR[2], 20037471.20513706]
        result = Extent(target, spatial_reference=mercator_srs).project_to_web_mercator()
        self.assertEqual(result.as_list(), target)
        self.assertEqual(result.spatial_reference.srs, mercator_srs)

    def test_extent_get_scale_string(self):

        image_width = 946
        target = "350 km (220 miles)"

        # Test in WGS84
        extent = get_extent()
        result = extent.get_scale_string(image_width)
        self.assertEqual(result, target)

        # Test in WGS84 corrected
        extent = Extent(GLOBAL_EXTENT_WGS84_CORRECTED, spatial_reference="EPSG:4326")
        result = extent.get_scale_string(image_width)
        self.assertEqual(result, target)

        # Test in Web Mercator
        extent = get_extent(web_mercator=True)
        result = extent.get_scale_string(image_width)
        self.assertEqual(result, target)

    def test_extent_set_to_center_and_scale(self):
        scale = 2311162.217155
        width = 946
        height = 627
        target = [-289237.7150310926, -191704.06693921625, 289237.7150310926, 191704.0669392088]

        # Test in WGS84
        extent = get_extent(web_mercator=False)
        result = extent.set_to_center_and_scale(scale, width, height).as_list()
        self.assertEqual(result, target)

        # Test in WGS84 corrected
        extent = Extent(GLOBAL_EXTENT_WGS84_CORRECTED, spatial_reference="EPSG:4326")
        result = extent.set_to_center_and_scale(scale, width, height).as_list()
        self.assertEqual(result, target)

        # Test in Web Mercator
        extent = get_extent(web_mercator=True)
        result = extent.set_to_center_and_scale(scale, width, height).as_list()
        self.assertEqual(result, target)

    def test_extract_significant_digits(self):
        target = 4.3
        result = extract_significant_digits(4.321)
        self.assertEqual(result, target)

        target = -4.3
        result = extract_significant_digits(-4.321)
        self.assertEqual(result, target)

        target = 44
        result = extract_significant_digits(44.321)
        self.assertEqual(result, target)

        target = -44
        result = extract_significant_digits(-44.321)
        self.assertEqual(result, target)

        target = 440
        result = extract_significant_digits(444.321)
        self.assertEqual(result, target)

        target = -440
        result = extract_significant_digits(-444.321)
        self.assertEqual(result, target)

    def test_union_extent(self):
        # Test empty extent values
        self.assertIsNone(union_extent(None))
        self.assertIsNone(union_extent(""))
        self.assertIsNone(union_extent([]))
        self.assertIsNone(union_extent([None, "", []]))

        with self.assertRaises(ValueError):
            union_extent([get_extent(), "nope"])

        extent_1 = None
        extent_2 = Extent(get_extent_list(), spatial_reference="EPSG:4326")
        target = list(GLOBAL_EXTENT_WGS84)
        result = union_extent([extent_1, extent_2]).as_list()
        self.assertEqual(result, target)

        extent_1 = Extent(get_extent_list(), spatial_reference="EPSG:4326")
        extent_2 = None
        target = list(GLOBAL_EXTENT_WGS84)
        result = union_extent([extent_1, extent_2]).as_list()
        self.assertEqual(result, target)

        extent_1 = Extent([-10, -10, 10, 10], spatial_reference="EPSG:4326")
        extent_2 = Extent([-20, -20, 5, 5], spatial_reference="EPSG:4326")
        target = [-20, -20, 10, 10]
        result = union_extent([extent_1, extent_2]).as_list()
        self.assertEqual(result, target)


class SpatialReferenceTestCase(GeometryTestCase):

    def test_spatial_reference(self):
        # Test with primitive values
        self.assert_spatial_reference(SpatialReference("CRS:84"), props="srs,wkid")
        self.assert_spatial_reference(SpatialReference("EPSG:4326"), props="srs,wkid")
        self.assert_spatial_reference(SpatialReference(4326), props="wkid")
        self.assert_spatial_reference(SpatialReference(4326.0), props="wkid")

        # Test with valid spatial reference dicts
        self.assert_spatial_reference(SpatialReference(get_spatial_reference_dict()))
        self.assert_spatial_reference(SpatialReference({"srs": "CRS:84"}), props="srs,wkid")
        self.assert_spatial_reference(SpatialReference({"srs": "EPSG:4326"}), props="srs,wkid")
        self.assert_spatial_reference(SpatialReference({"wkid": "4326"}), props="wkid")
        self.assert_spatial_reference(SpatialReference({"wkt": WEB_MERCATOR_WKT}), props="wkt")

        # Test with compatible spatial reference objects
        self.assert_spatial_reference(get_spatial_reference())
        self.assert_spatial_reference(get_spatial_reference_object())

    def test_invalid_spatial_references(self):
        # Test invalid parameters
        with self.assertRaises(BadSpatialReference):
            SpatialReference(None)
        with self.assertRaises(BadSpatialReference):
            SpatialReference([])
        with self.assertRaises(BadSpatialReference):
            SpatialReference(())
        with self.assertRaises(BadSpatialReference):
            SpatialReference(get_object({"srs": "", "wkid": "", "wkt": ""}))
        with self.assertRaises(BadSpatialReference):
            SpatialReference(get_object({"wkid": "nope"}))

        # Test with empty parameters
        with self.assertRaises(BadSpatialReference):
            SpatialReference("")
        with self.assertRaises(BadSpatialReference):
            SpatialReference({})
        with self.assertRaises(BadSpatialReference):
            SpatialReference(get_object({"latest_wkid": 4326}))

    def test_spatial_reference_repr(self):
        data = {"wkt": WEB_MERCATOR_WKT}

        target = f"wkt: {WEB_MERCATOR_WKT}"
        result = SpatialReference(data).__repr__()
        self.assertEqual(result, target)

        data["wkid"] = 3857

        target = "wkid: 3857"
        result = SpatialReference(data).__repr__()
        self.assertEqual(result, target)

        data["srs"] = "EPSG:3857"

        target = "srs: EPSG:3857"
        result = SpatialReference(data).__repr__()
        self.assertEqual(result, target)

    def test_spatial_reference_as_dict(self):
        data = {
            "latestWkid": "3857",
            "srs": "EPSG:3857",
            "wkid": 3857,
            "wkt": WEB_MERCATOR_WKT
        }

        # Test as_dict in non-ESRI format

        result = SpatialReference(data).as_dict(esri_format=False)
        self.assertEqual(result, {"srs": "EPSG:3857"})

        # Test as_dict in ESRI format

        result = SpatialReference("3857").as_dict(esri_format=True)
        self.assertEqual(result, {"srs": "3857"})

        result = SpatialReference(data).as_dict(esri_format=True)
        self.assertEqual(result, {"wkid": 3857})

        data.pop("srs")
        data.pop("wkid")

        result = SpatialReference(data).as_dict(esri_format=True)
        self.assertEqual(result, {"wkt": WEB_MERCATOR_WKT})

    def test_spatial_reference_as_json_string(self):
        data = {
            "latestWkid": "3857",
            "srs": "EPSG:3857",
            "wkid": 3857,
            "wkt": WEB_MERCATOR_WKT
        }

        # Test as_json_string in non-ESRI format

        result = SpatialReference(data).as_json_string(esri_format=False)
        self.assertEqual(result, json.dumps({"srs": "EPSG:3857"}))

        # Test as_json_string in ESRI format

        result = SpatialReference(data).as_json_string(esri_format=True)
        self.assertEqual(result, json.dumps({"wkid": 3857}))

        data.pop("srs")
        data.pop("wkid")

        result = SpatialReference(data).as_json_string(esri_format=True)
        self.assertEqual(result, json.dumps({"wkt": WEB_MERCATOR_WKT}))

    def test_spatial_reference_clone(self):
        spatial_ref = get_spatial_reference()
        cloned = spatial_ref.clone()

        self.assert_spatial_reference(cloned)
        self.assertIsNot(spatial_ref, cloned)

    def test_spatial_reference_is_geographic(self):

        self.assertTrue(SpatialReference("EPSG:4326").is_geographic())
        self.assertTrue(SpatialReference({"wkid": 4326}).is_geographic())
        self.assertTrue(get_spatial_reference(web_mercator=False).is_geographic())

        for wkid in (3857, 102100, 102113):
            self.assertFalse(SpatialReference({"wkid": wkid}).is_geographic())

        for srs in ("EPSG:3857", "EPSG:3785", "EPSG:900913", "EPSG:102113"):
            self.assertFalse(SpatialReference(srs).is_geographic())

    def test_spatial_reference_is_web_mercator(self):

        self.assertFalse(SpatialReference("EPSG:4326").is_web_mercator())
        self.assertFalse(SpatialReference({"wkid": 4326}).is_web_mercator())
        self.assertFalse(get_spatial_reference(web_mercator=False).is_web_mercator())

        for wkid in (3857, 102100, 102113):
            self.assertTrue(SpatialReference({"wkid": wkid}).is_web_mercator())

        for srs in ("EPSG:3857", "EPSG:3785", "EPSG:900913", "EPSG:102113"):
            self.assertTrue(SpatialReference(srs).is_web_mercator())

    def test_spatial_reference_is_valid_proj4_projection(self):

        self.assertFalse(SpatialReference({"srs": 4326}).is_valid_proj4_projection())
        self.assertFalse(SpatialReference({"wkid": 33000}).is_valid_proj4_projection())

        self.assertTrue(get_spatial_reference(web_mercator=True).is_valid_proj4_projection())

        for wkid in (1, 3857, 102100, 102113, 32999):
            self.assertTrue(SpatialReference({"wkid": wkid}).is_valid_proj4_projection())

        for srs in ("EPSG:3857", "EPSG:3785", "EPSG:900913", "EPSG:102113", "EPSG:4326"):
            self.assertTrue(SpatialReference(srs).is_valid_proj4_projection())


class TileLevelsTestCase(BaseTestCase):

    def test_tile_levels(self):

        # Invalid tile level resolutions
        with self.assertRaises(ValueError):
            TileLevels(None)
        with self.assertRaises(ValueError):
            TileLevels("")
        with self.assertRaises(ValueError):
            TileLevels([])
        with self.assertRaises(ValueError):
            TileLevels(["nope"])
        with self.assertRaises(ValueError):
            TileLevels(ARCGIS_RESOLUTIONS[0])

        target = list(ARCGIS_RESOLUTIONS)

        result = TileLevels(ARCGIS_RESOLUTIONS).resolutions
        self.assertEqual(result, target)

        result = TileLevels([str(res) for res in target]).resolutions
        self.assertEqual(result, target)

    def test_tile_levels_get_matching_resolutions(self):
        source_resolutions = ARCGIS_RESOLUTIONS[:15]
        target_resolutions = ARCGIS_RESOLUTIONS[-15:]
        tile_levels = TileLevels(source_resolutions)

        with self.assertRaises(ValueError):
            tile_levels.get_matching_resolutions(None)
        with self.assertRaises(ValueError):
            tile_levels.get_matching_resolutions("nope")

        # Resolutions overlap by the middle 10 (20 in all)
        overlapping_resolutions = {Decimal(res) for res in ARCGIS_RESOLUTIONS[-15:15]}

        target = {round(res) for res in overlapping_resolutions}
        result = tile_levels.get_matching_resolutions(target_resolutions, None)
        self.assertEqual(result, target)

        target = {round(res, 5) for res in overlapping_resolutions}
        result = tile_levels.get_matching_resolutions(target_resolutions)
        self.assertEqual(result, target)

        target = {round(res, 3) for res in overlapping_resolutions}
        result = tile_levels.get_matching_resolutions(target_resolutions, 3)
        self.assertEqual(result, target)

    def test_tile_levels_get_nearest_tile_level_and_resolution(self):
        tile_levels = TileLevels(ARCGIS_RESOLUTIONS)

        with self.assertRaises(ValueError):
            tile_levels.get_nearest_tile_level_and_resolution(None)
        with self.assertRaises(ValueError):
            tile_levels.get_nearest_tile_level_and_resolution("nope")

        sorted_resolutions = sorted(tile_levels.resolutions)

        res = sorted_resolutions[0]
        target = (19, 0.298582141647617)
        result = tile_levels.get_nearest_tile_level_and_resolution(res)
        self.assertEqual(result, target)

        res = sorted_resolutions[-1]
        target = (0, 156543.033928)
        result = tile_levels.get_nearest_tile_level_and_resolution(res)
        self.assertEqual(result, target)

        idx = int(len(sorted_resolutions) / 2)
        res = sorted_resolutions[idx]
        target = (9, 305.748113140558)
        result = tile_levels.get_nearest_tile_level_and_resolution(res)
        self.assertEqual(result, target)

        res = mean(sorted_resolutions[:10])
        target = (12, 38.2185141425366)
        result = tile_levels.get_nearest_tile_level_and_resolution(res)
        self.assertEqual(result, target)

        res = mean(sorted_resolutions[10:])
        target = (2, 39135.7584820001)
        result = tile_levels.get_nearest_tile_level_and_resolution(res, True)
        self.assertEqual(result, target)

    def test_tile_levels_snap_extent_to_nearest_tile_level(self):
        tile_levels = TileLevels(ARCGIS_RESOLUTIONS)

        width = 946
        height = 627

        geo_extent_data = (
            get_extent(),
            get_extent_dict(),
            get_extent_object(),
            json.dumps(get_extent_dict())
        )
        for data in geo_extent_data:
            target = [-282.4587061237935, -187.21100289600264, 282.4587061237935, 187.21100289600264]
            result = tile_levels.snap_extent_to_nearest_tile_level(data, width, height).as_list()
            self.assertEqual(result, target)

        web_extent_data = (
            get_extent(web_mercator=True),
            get_extent_dict(web_mercator=True),
            get_extent_object(web_mercator=True),
            json.dumps(get_extent_dict(web_mercator=True))
        )
        for data in web_extent_data:
            target = [-37022427.52397195, -24538120.56821397, 37022427.52397195, 24538120.568213962]
            result = tile_levels.snap_extent_to_nearest_tile_level(data, width, height).as_list()
            self.assertEqual(result, target)
