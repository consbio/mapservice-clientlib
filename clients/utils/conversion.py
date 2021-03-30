import json

from parserutils.numbers import is_number

from clients.query.fields import DictField, ExtentField, ObjectField

from .geometry import Extent


def to_extent(extent_data):
    """ Utilizes ExtentField to transform JSON, dict or extent-like object to an Extent """

    if isinstance(extent_data, Extent):
        return extent_data
    elif isinstance(extent_data, str):
        extent_data = json.loads(extent_data)
    elif hasattr(extent_data, "get_data"):
        extent_data = extent_data.get_data()

    return ExtentField().to_python(
        value={k: float(v) if is_number(v) else v for k, v in extent_data.items()},
        resource=None
    )


def to_object(json_or_dict, aliases=None, from_camel=True, defaults=None):
    """ Transforms JSON data into an object """

    if hasattr(json_or_dict, "get_data"):
        json_or_dict = json_or_dict.get_data()
    if isinstance(json_or_dict, str):
        json_or_dict = json.loads(json_or_dict)
    if aliases or defaults:
        json_or_dict = DictField(
            aliases=aliases, convert_camel=from_camel, defaults=defaults
        ).to_python(json_or_dict, None)

    return ObjectField(convert_camel=from_camel).to_python(json_or_dict, None)


def to_renderer(json_or_dict, from_camel=True):
    """ Shortcut to build a renderer object from a dict or JSON """

    aliases = {
        "classBreakInfos": "class_breaks",
        "classMinValue": "min",
        "classMaxValue": "max",
        "uniqueValueInfos": "unique_values",
        "classificationMethod": "method",
        "normalizationType": "normalization",
        "minValue": "min",
        "imageData": "image",
        "xoffset": "offset_x",
        "yoffset": "offset_y"
    }

    if from_camel:
        defaults = ["symbol", "default_symbol", "field", "field1", "field2", "field3", "label"]
    else:
        aliases = {v: k for k, v in aliases.items()}
        aliases["default_symbol"] = "defaultSymbol"  # May have been added from defaults
        defaults = []

    renderer = to_object(json_or_dict, aliases, from_camel, defaults)

    if hasattr(renderer, "symbol"):
        renderer.symbol = to_symbol(renderer.symbol)
    if hasattr(renderer, "default_symbol"):
        renderer.default_symbol = to_symbol(renderer.default_symbol)

    return renderer


def to_symbol(json_or_dict):
    """ Shortcut to build a symbol object from a dict or JSON """

    aliases = {
        "imageData": "image",
        "xoffset": "offset_x",
        "yoffset": "offset_y"
    }
    defaults = [
        "type", "style", "color", "offset_x", "offset_y", "width", "height"
    ]

    if not _is_symbol(json_or_dict):
        symbol = None
    else:
        symbol = to_object(json_or_dict, aliases=aliases, defaults=defaults)
        symbol.outline = to_symbol(getattr(symbol, "outline", None))

    return symbol


def _is_symbol(json_or_dict, key=None):
    if json_or_dict is None:
        return False

    if hasattr(json_or_dict, "get_data"):
        symbol = json_or_dict.get_data()
    elif isinstance(json_or_dict, str):
        symbol = json.loads(json_or_dict)
    else:
        symbol = json_or_dict

    symbol = symbol if key is None else symbol.get(key)

    return symbol and symbol.get("type")


def extent_to_polygon_wkt(extent_or_dict):

    if isinstance(extent_or_dict, dict):
        extent = extent_or_dict
    else:
        extent = extent_or_dict.as_dict()

    return "POLYGON(({xmin} {ymin}, {xmax} {ymin}, {xmax} {ymax}, {xmin} {ymax}, {xmin} {ymin}))".format(**extent)


def point_to_wkt(x, y, **kwargs):
    return f"POINT({x} {y})"


def multipoint_to_wkt(points, **kwargs):
    """ Generates MULTIPOINT(x1 y1, x2 y2, ...) from an array of point values """

    point_str = _points_to_str(points)
    return f"MULTIPOINT({point_str})"


def polyline_to_wkt(paths, **kwargs):
    """ Generates MULTILINESTRING((x1 y1, x2 y2), ...) from an array of path values """

    multi_point_str = _multi_points_to_str(paths)
    return f"MULTILINESTRING({multi_point_str})"


def polygon_to_wkt(rings, **kwargs):
    """ Generates POLYGON((x1 y1, x2 y2), ...) from an array of ring values """

    multi_point_str = _multi_points_to_str(rings)
    return f"POLYGON({multi_point_str})"


def _points_to_str(points):
    return ", ".join((f"{p[0]} {p[1]}" for p in points))


def _multi_points_to_str(multi_points):
    return ", ".join(f"({_points_to_str(points)})" for points in multi_points)
