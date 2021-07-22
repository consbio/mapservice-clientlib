import json

from restle.serializers import JSONSerializer, URLSerializer

from ..query.actions import QueryAction
from ..query.fields import DictField, ListField, ObjectField
from ..query.fields import BaseExtentField, ExtentField, SpatialReferenceField
from ..query.fields import CommaSeparatedField, DrawingInfoField, TimeInfoField
from ..query.fields import DRAWING_INFO_ALIASES, TIME_INFO_ALIASES
from ..query.serializers import XMLToJSONSerializer
from ..resources import ClientResource
from ..utils.geometry import Extent, SpatialReference

from .utils import BaseTestCase
from .utils import get_extent, get_extent_dict, get_extent_list, get_extent_object
from .utils import get_object, get_spatial_reference, get_spatial_reference_dict, get_spatial_reference_object


class FieldsTestCase(BaseTestCase):

    def test_dict_field(self):
        # Test with simple flat values (no conversion)

        flat_values = (
            123, "456", [7, 8, 9], list("abc"),
            {"a": "aaa", "b": "bbb", "c": "ccc"}
        )
        for value in flat_values:
            target = value
            result = DictField().to_python(value, None)
            self.assertEqual(result, target)

        # Test with complex dict values

        value = {
            "one": 1,
            "two": 2,
            "twentyTwo": 22,
            "abc": ["a", "b", "c"],
            "def": {"g": "ggg", "h": "hhh", "i": "iii"}
        }

        # Test without camel casing
        field = DictField(name="no_camel", convert_camel=False)
        target = value
        result = field.to_python(value, None)
        self.assertEqual(result, target)

        # Test with aliases
        aliases = {"one": "1", "two": "2", "twentyTwo": "22"}
        field = DictField(name="camel_aliases", aliases=aliases, convert_camel=True)
        target = {
            "1": 1,
            "2": 2,
            "22": 22,
            "abc": ["a", "b", "c"],
            "def": {"g": "ggg", "h": "hhh", "i": "iii"}
        }
        result = field.to_python(value, None)
        self.assertEqual(result, target)

        # Test with defaults
        defaults = {"three": "3", "four": "4", "ghi": None}
        field = DictField(name="defaults", defaults=defaults)
        target = {
            "one": 1,
            "two": 2,
            "three": "3",
            "four": "4",
            "twenty_two": 22,
            "abc": ["a", "b", "c"],
            "def": {"g": "ggg", "h": "hhh", "i": "iii"},
            "ghi": None
        }
        result = field.to_python(value, None)
        self.assertEqual(result, target)

    def test_list_field(self):
        field = ListField(name="wrap", wrap=True)

        value = None
        result = field.to_python(value, None)
        self.assertEqual(result, [])

        for value in (list("abc"), set("def"), tuple("ghi")):
            result = field.to_python(value, None)
            self.assertEqual(result, list(value))

        value = "abcdefghi"
        result = field.to_python(value, None)
        self.assertEqual(result, ["abcdefghi"])

    def test_object_field(self):
        value = {
            "one": 1,
            "two": 2,
            "twentyTwo": 22,
            "abc": ["a", "b", "c"],
            "def": {"g": "ggg", "h": "hhh", "i": "iii"}
        }

        field = ObjectField(name="no_camel", convert_camel=False)
        result = field.to_python(value, None)
        target = get_object(value)
        setattr(target, "def", get_object(getattr(target, "def")))
        self.assert_objects_are_equal(result, target)

        field = ObjectField(name="camel", convert_camel=True)
        result = field.to_python(value, None)
        target = get_object({
            "one": 1,
            "two": 2,
            "twenty_two": 22,
            "abc": ["a", "b", "c"],
            "def": {"g": "ggg", "h": "hhh", "i": "iii"}
        })
        setattr(target, "def", get_object(getattr(target, "def")))
        self.assert_objects_are_equal(result, target)

        aliases = {"one": "1", "two": "2", "twentyTwo": "22"}
        field = ObjectField(name="camel_aliases", aliases=aliases, convert_camel=True)
        result = field.to_python(value, None)
        target = get_object({
            "1": 1,
            "2": 2,
            "22": 22,
            "abc": ["a", "b", "c"],
            "def": {"g": "ggg", "h": "hhh", "i": "iii"}
        })
        setattr(target, "def", get_object(getattr(target, "def")))
        self.assert_objects_are_equal(result, target)

    def test_comma_separated_field(self):
        value = "  , abc ,def,\n123\t"
        field = CommaSeparatedField(name="split_text")
        result = field.to_python(value, None)
        target = ["", "abc", "def", "123"]
        self.assertEqual(result, target)

        value = ["  ", " abc ", "def", 123]
        field = CommaSeparatedField(name="split_list")
        result = field.to_python(value, None)
        target = ["", "abc", "def", "123"]
        self.assertEqual(result, target)

        obj = "abc"
        field = CommaSeparatedField(name="join_text")
        result = field.to_value(obj, None)
        target = "abc"
        self.assertEqual(result, target)

        obj = ["  ", " abc ", "def", 123]
        field = CommaSeparatedField(name="join_list")
        result = field.to_value(obj, None)
        target = "  , abc ,def,123"
        self.assertEqual(result, target)

    def test_drawing_info_field(self):

        # Create test data from constant: key:reversed_key for each item in dict
        value = {k: DRAWING_INFO_ALIASES[k][::-1] for k in DRAWING_INFO_ALIASES}
        field = DrawingInfoField(name="aliases")
        result = field.to_python(value, None)
        # The target will have aliased properties for each value in the test data
        target = get_object({
            v: DRAWING_INFO_ALIASES[k][::-1] for k, v in DRAWING_INFO_ALIASES.items()
        })
        self.assert_objects_are_equal(result, target)

        value = {"a": "aaa", "b": "bbb", "c": "ccc", "renderer": {"field2": "second field val"}}
        field = DrawingInfoField(name="renderer_fields")
        result = field.to_python(value, None)
        target = get_object({
            "a": "aaa",
            "b": "bbb",
            "c": "ccc",
            "renderer": {
                "default_symbol": None,
                "field": None,
                "field1": None,
                "field2": "second field val",
                "field3": None,
                "label": None
            }
        })
        setattr(target, "renderer", get_object(getattr(target, "renderer")))
        self.assert_objects_are_equal(result, target)

    def test_base_extent_field(self):
        field = BaseExtentField(name="to_python")

        with self.assertRaises(NotImplementedError):
            field.to_python(None, None)
        with self.assertRaises(NotImplementedError):
            field.to_python("value", None)
        with self.assertRaises(NotImplementedError):
            field.to_python(["value"], None)

        data = (get_extent(), get_spatial_reference())

        target = data[0].as_dict()
        result = field.to_value(data[0], None)
        self.assertEqual(result, target)

        target = data[1].as_dict()
        result = field.to_value(data[1], None)
        self.assertEqual(result, target)

        target = [d.as_dict() for d in data]
        result = field.to_value(data, None)
        self.assertEqual(result, target)

    def test_extent_field(self):

        for web_mercator in (True, False):
            spatial_ref = get_spatial_reference_dict(web_mercator)
            resource = ClientResource(default_spatial_ref=spatial_ref["srs"])

            extent_data = (
                get_extent_dict(web_mercator),
                get_extent_object(web_mercator),
                get_extent_list(web_mercator),
                Extent(
                    get_extent_list(web_mercator),
                    spatial_reference=get_spatial_reference(web_mercator)
                )
            )

            # Test each form of an extent individually
            for extent in extent_data:
                field = ExtentField(name="to_python")
                target = Extent(extent, spatial_ref).as_dict()

                result = field.to_python(extent, resource)
                self.assertEqual(result.as_dict(), target)

                obj = result
                field = ExtentField(name="to_value")
                result = field.to_value(obj, resource)
                self.assertEqual(result, target)

            # Test multiple extent values in a list

            extent_data = (get_extent_dict(), get_extent_list())
            spatial_ref = get_spatial_reference_dict()
            resource = ClientResource(default_spatial_ref=spatial_ref["srs"])

            field = ExtentField(name="to_python")
            target = [Extent(e, spatial_ref).as_dict() for e in extent_data]

            result = field.to_python(extent_data, resource)
            self.assertEqual([r.as_dict() for r in result], target)

            objects = result
            field = ExtentField(name="to_value")
            result = field.to_value(objects, resource)
            self.assertEqual(result, target)

    def test_spatial_reference_field(self):

        data = (
            get_spatial_reference(),
            get_spatial_reference_dict(),
            get_spatial_reference_object()
        )

        # Test each form of a spatial reference individually
        for value in data:
            field = SpatialReferenceField(name="to_python")
            target = SpatialReference(value)

            result = field.to_python(value, None)
            self.assert_objects_are_equal(result, target)

            obj = result
            field = SpatialReferenceField(name="to_value")
            result = field.to_value(obj, None)
            self.assertEqual(result, target.as_dict())

        # Test multiple spatial reference values in a list

        data = (
            get_spatial_reference_dict(True),
            get_spatial_reference_dict(False)
        )

        field = SpatialReferenceField(name="to_python")
        target = [SpatialReference(v) for v in data]

        result = field.to_python(data, None)
        self.assert_objects_are_equal(result, target)

        objects = result
        field = SpatialReferenceField(name="to_value")
        target = [t.as_dict() for t in target]
        result = field.to_value(objects, None)
        self.assertEqual(result, target)

    def test_time_info_field(self):

        # Create test data from constant: key:reversed_key for each item in dict
        value = {k: TIME_INFO_ALIASES[k][::-1] for k in TIME_INFO_ALIASES}
        field = TimeInfoField(name="aliases")
        result = field.to_python(value, None)
        # The target will have aliased properties for each value in the test data
        target = get_object({
            v: TIME_INFO_ALIASES[k][::-1] for k, v in TIME_INFO_ALIASES.items()
        })
        self.assert_objects_are_equal(result, target)


class ActionsTestCase(BaseTestCase):

    def test_query_action_prepare_params(self):

        for web_mercator in (True, False):
            extent = get_extent(web_mercator)
            extent_dict = get_extent_dict(web_mercator)
            extent_list = get_extent_list(web_mercator)
            spatial_ref = get_spatial_reference(web_mercator)

            action = QueryAction("/", deserializer=JSONSerializer)

            params = action.prepare_params({
                "extent_obj": extent,
                "extent_dict": extent_dict,
                "extent_list": extent_list,
                "spatial_reference": spatial_ref
            })
            target = {
                "extent_obj": extent.as_json_string(),
                "extent_dict": json.dumps(extent_dict),
                "extent_list": json.dumps(extent_list),
                "spatial_reference": spatial_ref.as_json_string()
            }
        self.assertEqual(params[0], URLSerializer.to_string(target))


class SerializersTestCase(BaseTestCase):

    def test_xml_to_json_serializer(self):
        serializer = XMLToJSONSerializer()
        serialized = '<a root="true"><b first="true">bbb</b><c>ccc</c>aaa</a>'
        deserialized = {"b": {"first": "true", "value": "bbb"}, "c": ["ccc", "aaa"], "root": "true"}

        self.assertEqual(serializer.to_dict(serialized), deserialized)
