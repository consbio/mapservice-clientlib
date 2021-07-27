import types

from restle import fields
from parserutils.collections import setdefaults
from parserutils.strings import camel_to_snake

from ..utils.geometry import Extent, SpatialReference
from ..exceptions import BadSpatialReference


class DictField(fields.DictField):
    """
    Overridden to convert camel properties to snake by default,
    handle defaults and support aliases for dict keys
    """

    def __init__(self, aliases=None, convert_camel=True, defaults=None, *args, **kwargs):
        self.convert_camel = convert_camel
        self.aliases = aliases or {}
        self.defaults = defaults or []

        super(DictField, self).__init__(*args, **kwargs)

    def to_python(self, value, resource):
        """ Overridden to set defaults before recursively applying camel casing and aliases """

        value = self._to_python(value, resource)
        if self.defaults:
            value = setdefaults(value, self.defaults)

        return value

    def _to_python(self, value, resource):
        """ Recursively applies camel casing and aliases to all nested keys """

        def convert(val):
            if isinstance(val, (dict, list)):
                return self._to_python(val, resource)
            else:
                return super(DictField, self).to_python(val, resource)

        if isinstance(value, dict):
            d = {self.aliases.get(k, k): convert(v) for k, v in value.items()}
            return {camel_to_snake(k): v for k, v in d.items()} if self.convert_camel else d

        elif isinstance(value, list):
            return [convert(v) for v in value]

        else:
            return super(DictField, self).to_python(value, resource)


class ListField(fields.ListField):
    """ Overridden to wrap non-iterable values by default """

    def __init__(self, wrap=True, *args, **kwargs):
        self.wrap = wrap
        super(ListField, self).__init__(*args, **kwargs)

    def to_python(self, value, resource):
        if self.wrap and not isinstance(value, (list, tuple, set)):
            value = [] if value is None else [value]

        return super(ListField, self).to_python(value, resource)


class ObjectField(fields.ObjectField):
    """ Overridden to convert camel properties to snake by default, and to add get_data method to custom types """

    def __init__(self, class_name="AnonymousObject", aliases=None, convert_camel=True, *args, **kwargs):
        self.convert_camel = convert_camel

        super(ObjectField, self).__init__(class_name=class_name, aliases=aliases or {}, *args, **kwargs)

    def to_data(self, value):
        if isinstance(value, list):
            return [self.to_data(item) for item in value]
        return value.get_data() if hasattr(value, "get_data") else value

    def to_python(self, value, resource):
        """ Overridden to add get_data method at each level of the object instance """

        if isinstance(value, dict):
            d = {
                self.aliases.get(k, k): self.to_python(v, resource) if isinstance(v, (dict, list)) else v
                for k, v in value.items()
            }
            if self.convert_camel:
                d = {camel_to_snake(k): v for k, v in d.items()}

            val = {k: self.to_data(v) for k, v in d.items()}

            if not d:
                obj = None
            else:
                obj = type(self.class_name, (), d)
                obj.get_data = types.MethodType(lambda field: val, obj)

            return obj

        elif isinstance(value, list):
            return [self.to_python(x, resource) if isinstance(x, (dict, list)) else x for x in value]
        else:
            return value


class CommaSeparatedField(fields.TextField):
    """ Overridden to convert text values with commas into lists """

    def to_python(self, value, resource):
        if not isinstance(value, list):
            value = super(CommaSeparatedField, self).to_python(value, resource).split(",")

        return [str(val).strip() for val in value if val] if value else []

    def to_value(self, obj, resource):
        return obj if isinstance(obj, str) else ",".join(str(o) for o in obj)


class DrawingInfoField(ObjectField):

    def __init__(self, *args, **kwargs):
        self.renderer_defaults = RENDERER_DEFAULTS

        aliases = dict(DRAWING_INFO_ALIASES)
        super(DrawingInfoField, self).__init__(class_name="DrawingInfo", aliases=aliases, *args, **kwargs)

    def to_python(self, value, resource):
        """ Overridden to ensure the presence of field properties in renderer """

        if value and "renderer" in value:
            value["renderer"] = setdefaults(value["renderer"], self.renderer_defaults)

        return super(DrawingInfoField, self).to_python(value, resource)


class BaseExtentField(DictField):

    def to_python(self, value, resource):
        """ Overridden to manage conversion of multiple incoming vals """

        value = super(BaseExtentField, self).to_python(value, resource)

        if not isinstance(value, (list, tuple)):
            return self._val_to_py(value, resource)
        elif value and not isinstance(value[0], dict):
            return self._val_to_py(value, resource)
        else:
            return [self._val_to_py(v, resource) for v in value]

    def to_value(self, obj, resource):
        """ Overridden to manage conversion of multiple objects back to dict """

        if not isinstance(obj, (list, tuple)):
            return self._py_to_val(obj, resource)
        else:
            return [self._py_to_val(o, resource) for o in obj]

    def _val_to_py(self, value, resource):
        class_name = type(self).__name__
        raise NotImplementedError(f"{class_name}._val_to_py")

    def _py_to_val(self, obj, resource):
        return obj.as_dict()


class ExtentField(BaseExtentField):

    def _val_to_py(self, value, resource):
        try:
            return Extent(value)
        except BadSpatialReference:
            return Extent(value, resource.default_spatial_ref)


class SpatialReferenceField(BaseExtentField):

    def _val_to_py(self, value, resource):
        return SpatialReference(value)


class TimeInfoField(ObjectField):

    def __init__(self, *args, **kwargs):
        aliases = dict(TIME_INFO_ALIASES)
        super(TimeInfoField, self).__init__(class_name="TimeInfo", aliases=aliases, *args, **kwargs)


DRAWING_INFO_ALIASES = {
    # Labeling Info
    "labelingInfo": "labeling",
    "labelPlacement": "placement",
    "labelExpression": "expression",
    "useCodedValues": "use_coded_values",
    "minScale": "min_scale",
    "maxScale": "max_scale",
    "whereClause": "where",

    # Renderer
    "defaultSymbol": "default_symbol",
    "defaultLabel": "default_label",
    "fieldDelimiter": "field_delimiter",
    "uniqueValueInfos": "unique_values",
    "classificationMethod": "method",
    "normalizationType": "normalization",
    "normalizationField": "normalization_field",
    "normalizationTotal": "normalization_total",
    "backgroundFillSymbol": "background_fill_symbol",
    "minValue": "min",

    # Class Break Info
    "classBreakInfos": "class_breaks",
    "classMinValue": "min",
    "classMaxValue": "max",

    # Symbol
    "xoffset": "offset_x",
    "yoffset": "offset_y",
    "imageData": "image",
    "contentType": "content_type",
    "backgroundColor": "background_color",
    "borderLineSize": "border_line_width",
    "borderLineColor": "border_line_color",
    "haloSize": "halo_size",
    "haloColor": "halo_color",
    "horizontalAlignment": "horizontal_alignment",
    "verticalAlignment": "vertical_alignment",
    "rightToLeft": "is_rtl"
}

RENDERER_ALIASES = {
    "classBreakInfos": "class_breaks",
    "classMinValue": "min",
    "classMaxValue": "max",
    "classificationMethod": "method",
    "defaultLabel": "default_label",
    "defaultSymbol": "default_symbol",
    "fieldDelimiter": "field_delimiter",
    "uniqueValueInfos": "unique_values",
    "normalizationType": "normalization",
    "normalizationField": "normalization_field",
    "normalizationTotal": "normalization_total",
    "minValue": "min_val",
    "imageData": "image",
    "xoffset": "offset_x",
    "yoffset": "offset_y"
}
RENDERER_DEFAULTS = ("default_symbol", "field", "field1", "field2", "field3", "label")

TIME_INFO_ALIASES = {
    "startTimeField": "start_field",
    "endTimeField": "end_field",
    "trackIdField": "track_field",

    # Used at the map service layer level (time data is layer specific)
    "timeInterval": "interval",
    "timeIntervalUnits": "units",

    # Used at the map service level (defaults if not defined in layer)
    "defaultTimeInterval": "default_interval",
    "defaultTimeIntervalUnits": "default_units"
}
