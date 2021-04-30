from clients.exceptions import BadExtent
from clients.utils.geometry import Extent, SpatialReference, TileLevels
from clients.utils.geometry import extract_significant_digits, union_extent
from clients.utils.geometry import GLOBAL_EXTENT_WEB_MERCATOR, GLOBAL_EXTENT_WGS84, GLOBAL_EXTENT_WGS84_CORRECTED

from .utils import BaseTestCase, GeometryTestCase
from .utils import get_extent, get_extent_dict, get_extent_list, get_extent_object
from .utils import get_spatial_reference, get_spatial_reference_dict, get_spatial_reference_object


class ExtentTestCase(GeometryTestCase):

    def test_extent(self):
        """ Tests successful extent creation """

        extent = Extent()
        self.assert_extent(extent, props="")
        self.assertIsNone(extent._original_format)

        extent = Extent(get_extent_dict())
        self.assert_extent(extent)
        self.assertEqual(extent._original_format, "dict")

        extent = Extent(get_extent_list())
        self.assert_extent(extent)
        self.assertEqual(extent._original_format, "list")

        extent = Extent(tuple(get_extent_list()))
        self.assert_extent(extent)
        self.assertEqual(extent._original_format, "list")

        extent = get_extent()
        self.assert_extent(extent)

        extent = get_extent_object()
        self.assert_extent(extent)

    def test_invalid_extent(self):
        """ Tests invalid parameters for extent creation """

        # Invalid extent parameter
        with self.assertRaises(BadExtent):
            Extent(set(get_extent_list()))

        # Invalid extent dicts

        with self.assertRaises(BadExtent):
            extent_dict = get_extent_dict()
            extent_dict.pop("spatial_reference")
            Extent(extent_dict)

        with self.assertRaises(BadExtent):
            extent_dict = get_extent_dict()
            extent_dict.pop("xmin")
            Extent(extent_dict)

        with self.assertRaises(BadExtent):
            extent_dict = get_extent_dict()
            extent_dict["xmin"] = "abc"
            Extent(extent_dict)

        # Invalid extent lists

        with self.assertRaises(BadExtent):
            extent_list = get_extent_list()[:2]
            Extent(extent_list)

        with self.assertRaises(BadExtent):
            extent_list = get_extent_list()
            extent_list[3] = "abc"
            Extent(extent_list)

        # Invalid extent objects

        with self.assertRaises(BadExtent):
            extent_obj = get_extent_object()
            del extent_obj.spatial_reference
            Extent(extent_obj)

        with self.assertRaises(BadExtent):
            extent_obj = get_extent_object()
            del extent_obj.ymin
            Extent(extent_obj)

        with self.assertRaises(BadExtent):
            extent_obj = get_extent_object()
            extent_obj.ymin = "abc"
            Extent(extent_obj)

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

        result = get_extent().as_list()
        target = list(GLOBAL_EXTENT_WGS84)
        self.assertEqual(result, target)

        target = [-179.1234, -89.2345, 179.3456, 89.4567]
        result = Extent(target, "EPSG:4326").as_list()
        self.assertEqual(result, target)

    def test_extent_as_original(self):

        # Test as_original when there is none

        extent = Extent()
        self.assertIsNone(extent._original_format)

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
        extent = Extent(get_extent_list())

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
        extent_1 = None
        extent_2 = Extent(get_extent_list())
        target = list(GLOBAL_EXTENT_WGS84)
        result = union_extent([extent_1, extent_2]).as_list()
        self.assertEqual(result, target)

        extent_1 = Extent(get_extent_list())
        extent_2 = None
        target = list(GLOBAL_EXTENT_WGS84)
        result = union_extent([extent_1, extent_2]).as_list()
        self.assertEqual(result, target)

        extent_1 = Extent([-10, -10, 10, 10])
        extent_2 = Extent([-20, -20, 5, 5])
        target = [-20, -20, 10, 10]
        result = union_extent([extent_1, extent_2]).as_list()
        self.assertEqual(result, target)


class SpatialReferenceTestCase(GeometryTestCase):

    def test_spatial_reference(self):
        self.assert_spatial_reference(SpatialReference(), props="")
        self.assert_spatial_reference(SpatialReference("EPSG:4326"), props="srs")
        self.assert_spatial_reference(SpatialReference(get_spatial_reference_dict()))
        self.assert_spatial_reference(get_spatial_reference())
        self.assert_spatial_reference(get_spatial_reference_object())

    def test_invalid_spatial_references(self):
        # TODO: test_invalid_spatial_references
        SpatialReference

    def test_spatial_reference_as_dict(self):
        # TODO: test_spatial_reference_as_dict
        SpatialReference.as_dict

    def test_spatial_reference_as_json_string(self):
        # TODO: test_spatial_reference_as_json_string
        SpatialReference.as_json_string

    def test_spatial_reference_is_geographic(self):
        # TODO: test_spatial_reference_is_geographic
        SpatialReference.is_geographic

    def test_spatial_reference_is_web_mercator(self):
        # TODO: test_spatial_reference_is_web_mercator
        SpatialReference.is_web_mercator

    def test_spatial_reference_is_valid_proj4_projection(self):
        # TODO: test_spatial_reference_is_valid_proj4_projection
        SpatialReference.is_valid_proj4_projection


class TileLevelsTestCase(BaseTestCase):

    def test_tile_levels(self):
        # TODO: test_tile_levels
        TileLevels

    def test_tile_levels_get_nearest_tile_level_and_resolution(self):
        # TODO: test_tile_levels_get_nearest_tile_level_and_resolution
        TileLevels.get_nearest_tile_level_and_resolution

    def test_tile_levels_get_matching_resolutions(self):
        # TODO: test_tile_levels_get_matching_resolutions
        TileLevels.get_matching_resolutions

    def test_tile_levels_snap_extent_to_nearest_tile_level(self):
        # TODO: test_tile_levels_snap_extent_to_nearest_tile_level
        TileLevels.snap_extent_to_nearest_tile_level
