import copy
import json
import types

from ..query.fields import ObjectField
from ..utils.conversion import to_words, to_object, to_renderer, to_symbol, is_symbol
from ..utils.conversion import extent_to_polygon_wkt, polygon_to_wkt, polyline_to_wkt
from ..utils.conversion import multipoint_to_wkt, point_to_wkt

from .utils import GeometryTestCase
from .utils import get_extent, get_extent_dict, get_extent_object


class ConversionTestCase(GeometryTestCase):

    def test_to_words(self):
        target_str = "conversion test case"
        target_list = ["conversion", "test", "case"]

        result = to_words(ConversionTestCase)
        self.assertEqual(result, target_str)

        result = to_words(ConversionTestCase, as_string=False)
        self.assertEqual(result, target_list)

        result = to_words(self)
        self.assertEqual(result, target_str)

        result = to_words(self, as_string=False)
        self.assertEqual(result, target_list)

        result = to_words("ConversionTestCase")
        self.assertEqual(result, target_str)

        result = to_words("ConversionTestCase", as_string=False)
        self.assertEqual(result, target_list)

    def test_to_object(self):
        object_dict = {"a": "aaa", "b": "bbb", "c": "ccc", "aBc": "def"}

        # Test with camel casing

        kwargs = {"from_camel": True}
        target = copy.deepcopy(object_dict)
        target["a_bc"] = target.pop("aBc")
        props = "a,b,c,a_bc"

        obj = to_object(object_dict, **kwargs)
        self.assert_object_values(obj, target, props)
        obj = to_object(json.dumps(object_dict), **kwargs)
        self.assert_object_values(obj, target, props)
        obj = to_object(ObjectField().to_python(object_dict, None), **kwargs)
        self.assert_object_values(obj, target, props)

        # Test without camel casing

        kwargs = {"from_camel": False}
        target = copy.deepcopy(object_dict)
        props = "a,b,c,aBc"

        obj = to_object(object_dict, **kwargs)
        self.assert_object_values(obj, target, props)
        obj = to_object(json.dumps(object_dict), **kwargs)
        self.assert_object_values(obj, target, props)
        obj = to_object(ObjectField(convert_camel=False).to_python(object_dict, None), **kwargs)
        self.assert_object_values(obj, target, props)

        # Test with aliases and camel casing

        kwargs = {"aliases": {"aBc": "xYz"}}
        target = copy.deepcopy(object_dict)
        target["x_yz"] = target.pop("aBc")
        props = "a,b,c,x_yz"

        obj = to_object(object_dict, **kwargs)
        self.assert_object_values(obj, target, props)
        obj = to_object(json.dumps(object_dict), **kwargs)
        self.assert_object_values(obj, target, props)
        obj = to_object(ObjectField(aliases={"aBc": "xYz"}).to_python(object_dict, None), **kwargs)
        self.assert_object_values(obj, target, props)

        # Test with defaults and no camel casing

        kwargs = {"defaults": {"xYz": "xyz"}, "from_camel": False}
        target = copy.deepcopy(object_dict)
        target["xYz"] = "xyz"
        props = "a,b,c,aBc,xYz"

        obj = to_object(object_dict, **kwargs)
        self.assert_object_values(obj, target, props)
        obj = to_object(json.dumps(object_dict), **kwargs)
        self.assert_object_values(obj, target, props)
        obj = to_object(ObjectField(convert_camel=False).to_python(object_dict, None), **kwargs)
        self.assert_object_values(obj, target, props)

    def test_to_renderer(self):
        test_defaults = ("defaultSymbol", "field1", "label")

        renderer_symbol = {
            "label": "symbol label",
            "value": "symbol val",
            "description": "symbol desc",
            "height": None,
            "width": None,
            "color": [0, 0, 0, 0],
            "outline": {},
            "style": "esriSFSSolid",
            "type": "esriSFS",
            "offset_x": None,
            "offset_y": None
        }
        renderer_dict = {
            "symbol": copy.deepcopy(renderer_symbol),
            "default_label": None,
            "default_symbol": copy.deepcopy(renderer_symbol),
            "description": "",
            "field_delimiter": ", ",
            "field": "field val",
            "field2": "field two val",
            "field3": None,
            "unique_values": [copy.deepcopy(renderer_symbol)],
            "class_breaks": [copy.deepcopy(renderer_symbol)],
            "type": "classBreaks",
            "max": .000009,
            "min": .000001,
            "method": "esriClassifyQuantile",
            "normalization": "quantile",
            "image": "image val",
            "offset_x": "x offset",
            "offset_y": "y offset"
        }
        esri_renderer_dict = {
            "symbol": copy.deepcopy(renderer_symbol),
            "defaultLabel": None,
            "defaultSymbol": copy.deepcopy(renderer_symbol),
            "description": "",
            "fieldDelimiter": ", ",
            "field": "field val",
            "field2": "field two val",
            "field3": None,
            "uniqueValueInfos": [copy.deepcopy(renderer_symbol)],
            "classBreakInfos": [copy.deepcopy(renderer_symbol)],
            "type": "classBreaks",
            "classMaxValue": .000009,
            "classMinValue": .000001,
            "classificationMethod": "esriClassifyQuantile",
            "normalizationType": "quantile",
            "imageData": "image val",
            "xoffset": "x offset",
            "yoffset": "y offset"
        }

        # Test with camel casing (to ESRI format)

        kwargs = {"from_camel": False}

        target_symbol = to_symbol(renderer_symbol, **kwargs)
        target = copy.deepcopy(esri_renderer_dict)
        target.update({}.fromkeys(test_defaults))
        target["symbol"] = target_symbol
        target["defaultSymbol"] = target_symbol
        target["classBreakInfos"] = [target_symbol]
        target["uniqueValueInfos"] = [target_symbol]

        renderer = to_renderer(renderer_dict, **kwargs)
        self.assert_object_values(renderer, target)
        renderer = to_renderer(json.dumps(renderer_dict), **kwargs)
        self.assert_object_values(renderer, target)

        # Test without camel casing (from ESRI format)

        kwargs = {"from_camel": True}

        target_symbol = to_symbol(renderer_symbol, **kwargs)
        target = copy.deepcopy(renderer_dict)
        target.update({}.fromkeys(test_defaults))
        target["symbol"] = target_symbol
        target["default_symbol"] = target_symbol
        target["class_breaks"] = [target_symbol]
        target["unique_values"] = [target_symbol]

        renderer = to_renderer(esri_renderer_dict, **kwargs)
        self.assert_object_values(renderer, target)
        renderer = to_renderer(json.dumps(esri_renderer_dict), **kwargs)
        self.assert_object_values(renderer, target)

    def test_to_symbol(self):
        test_defaults = ("height", "width")

        symbol_outline = {
            "color": [1, 1, 1, 1],
            "width": 2,
            "style": "esriSLSSolid",
            "type": "esriSLS"
        }
        symbol_dict = {
            "label": "symbol label",
            "value": "symbol val",
            "description": "symbol desc",
            "color": [0, 0, 0, 0],
            "outline": copy.deepcopy(symbol_outline),
            "style": "esriSFSSolid",
            "type": "esriSFS",
            "image": "image val",
            "offset_x": "x offset",
            "offset_y": "y offset"
        }
        esri_symbol_dict = {
            "label": "symbol label",
            "value": "symbol val",
            "description": "symbol desc",
            "color": [0, 0, 0, 0],
            "outline": copy.deepcopy(symbol_outline),
            "style": "esriSFSSolid",
            "type": "esriSFS",
            "imageData": "image val",
            "xoffset": "x offset",
            "yoffset": "y offset"
        }

        # Test with camel casing (to ESRI format)

        kwargs = {"from_camel": False}

        target = copy.deepcopy(esri_symbol_dict)
        target["outline"] = to_symbol(symbol_outline, **kwargs)
        target.update({}.fromkeys(test_defaults))

        symbol = to_symbol(symbol_dict, **kwargs)
        self.assert_object_values(symbol, target)
        symbol = to_symbol(json.dumps(symbol_dict), **kwargs)
        self.assert_object_values(symbol, target)

        # Test without camel casing (from ESRI format)

        kwargs = {"from_camel": True}

        target = copy.deepcopy(symbol_dict)
        target["outline"] = to_symbol(symbol_outline, **kwargs)
        target.update({}.fromkeys(test_defaults))

        symbol = to_symbol(esri_symbol_dict, **kwargs)
        self.assert_object_values(symbol, target)
        symbol = to_symbol(json.dumps(esri_symbol_dict), **kwargs)
        self.assert_object_values(symbol, target)

    def test_is_symbol_invalid(self):
        renderer = {"type": "simple", "label": ""}
        symbol = {"label": "symbol label", "value": "symbol val"}

        empty_obj = type("Empty", (), {})
        empty_obj.get_data = types.MethodType(lambda field: {}, empty_obj)

        symbol_obj = type("Invalid", (), symbol)
        symbol_obj.get_data = types.MethodType(lambda field: symbol, symbol_obj)

        invalid_symbols = (None, {}, symbol, "{}", json.dumps(symbol), empty_obj, symbol_obj)
        for invalid in invalid_symbols:
            symbol_type = type(invalid).__name__

            self.assertFalse(is_symbol(invalid), f"Invalid symbol passed: {symbol_type}")
            self.assertFalse(is_symbol(renderer, "nope"), f"Missing symbol passed: {symbol_type}")

            renderer["symbol"] = invalid
            self.assertFalse(is_symbol(renderer, "symbol"), f'Invalid keyed symbol passed: {symbol_type}')

    def test_is_symbol_valid(self):
        renderer = {"type": "simple", "label": ""}
        symbol = {
            "color": [0, 0, 0, 0],
            "width": 3,
            "type": "esriSLS",
            "style": "esriSLSSolid"
        }

        symbol_obj = type("Valid", (), symbol)
        symbol_obj.get_data = types.MethodType(lambda field: symbol, symbol_obj)

        for valid in (symbol, json.dumps(symbol), symbol_obj):
            symbol_type = type(valid).__name__
            self.assertTrue(is_symbol(symbol), "Valid symbol dict failed: {symbol_type}")
            renderer["symbol"] = valid
            self.assertTrue(is_symbol(renderer, "symbol"), f"Valid keyed symbol failed: {symbol_type}")

    def test_extent_to_polygon_wkt(self):

        with self.assertRaises(ValueError):
            extent_to_polygon_wkt(None)

        target = "POLYGON((-180.0 -90.0, 180.0 -90.0, 180.0 90.0, -180.0 90.0, -180.0 -90.0))"

        self.assertEqual(extent_to_polygon_wkt(get_extent()), target)
        self.assertEqual(extent_to_polygon_wkt(get_extent_dict()), target)
        self.assertEqual(extent_to_polygon_wkt(get_extent_object()), target)

    def test_point_to_wkt(self):
        target = "POINT(180 -90)"

        self.assertEqual(point_to_wkt(x=180, y=-90, nope=False), target)
        self.assertEqual(point_to_wkt(180, -90, yep=True), target)
        self.assertEqual(point_to_wkt(x="180", y=-90, nope=False), target)
        self.assertEqual(point_to_wkt(180, "-90", yep=True), target)

    def test_multipoint_to_wkt(self):

        with self.assertRaises(ValueError):
            multipoint_to_wkt(None)

        target = "MULTIPOINT(180 -90, -180 90)"

        points = [("180", "-90"), ("-180", "90")]
        self.assertEqual(multipoint_to_wkt(points), target)

        points = [(180, -90), (-180, 90)]
        self.assertEqual(multipoint_to_wkt(points), target)

    def test_polyline_to_wkt(self):
        with self.assertRaises(ValueError):
            polyline_to_wkt(None)

        target = "MULTILINESTRING((180 -90, -180 90), (-180 -90, 180 90))"

        paths = ([("180", "-90"), ("-180", "90")], [("-180", "-90"), ("180", "90")])
        self.assertEqual(polyline_to_wkt(paths), target)

        paths = ([(180, -90), (-180, 90)], [(-180, -90), (180, 90)])
        self.assertEqual(polyline_to_wkt(paths), target)

    def test_polygon_to_wkt(self):
        with self.assertRaises(ValueError):
            polygon_to_wkt(None)

        target = "POLYGON((180 -90, -180 90), (-180 -90, 180 90))"

        rings = ([("180", "-90"), ("-180", "90")], [("-180", "-90"), ("180", "90")])
        self.assertEqual(polygon_to_wkt(rings), target)

        rings = ([(180, -90), (-180, 90)], [(-180, -90), (180, 90)])
        self.assertEqual(polygon_to_wkt(rings), target)
