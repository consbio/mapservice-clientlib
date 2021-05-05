import json

from restle.serializers import JSONSerializer, URLSerializer

from clients.query.actions import QueryAction
from clients.query.fields import DictField, ListField, ObjectField
from clients.query.fields import ExtentField, SpatialReferenceField
from clients.query.fields import CommaSeparatedField, DrawingInfoField, TimeInfoField
from clients.query.fields import DRAWING_INFO_ALIASES, TIME_INFO_ALIASES
from clients.query.serializers import XMLToJSONSerializer
from clients.utils.geometry import Extent, SpatialReference

from .utils import BaseTestCase
from .utils import get_extent, get_extent_dict, get_extent_list, get_extent_object
from .utils import get_object, get_spatial_reference, get_spatial_reference_dict


class FieldsTestCase(BaseTestCase):

    def test_dict_field(self):
        value = {
            "one": 1,
            "two": 2,
            "twentyTwo": 22,
            "abc": ["a", "b", "c"],
            "def": {"g": "ggg", "h": "hhh", "i": "iii"}
        }

        field = DictField(name="no_camel", convert_camel=False)
        result = field.to_python(value, None)
        self.assertEqual(result, value)

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

    def test_extent_field(self):

        data = (
            get_extent_dict(),
            get_extent_object(),
            get_extent_list(),
            Extent(get_extent_list(), spatial_reference=get_spatial_reference()),
        )
        for value in data:
            if not isinstance(value, list):
                field = ExtentField(name="to_python")
                target = Extent(value)
            else:
                field = ExtentField(name="to_python", default_spatial_ref="EPSG:4326")
                target = Extent(value, "EPSG:4326")

            result = field.to_python(value, None)
            self.assert_objects_are_equal(
                result, target,
                "Testing to_python with {} data".format(type(value).__name__)
            )

            obj = result
            field = ExtentField(name="to_value")
            result = field.to_value(obj, None)
            self.assertEqual(result, target.as_dict())

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

    def test_spatial_reference_field(self):

        data = (
            # TODO: more types of spatial references
            get_spatial_reference(),
            get_spatial_reference_dict(),
        )
        for value in data:
            field = SpatialReferenceField(name="to_python")
            result = field.to_python(value, None)
            target = SpatialReference(value)
            self.assert_objects_are_equal(
                result, target,
                "Testing to_python with {} data".format(type(value).__name__)
            )

            obj = result
            field = SpatialReferenceField(name="to_value")
            result = field.to_value(obj, None)
            self.assertEqual(result, target.as_dict())


class ActionsTestCase(BaseTestCase):

    def test_query_action_prepare_params(self):
        extent = get_extent()
        extent_dict = get_extent_dict()
        extent_list = get_extent_list()
        spatial_ref = get_spatial_reference()

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
