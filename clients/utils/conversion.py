import json

from parserutils.strings import camel_to_snake

from ..query.fields import RENDERER_ALIASES
from ..query.fields import DictField, ObjectField

from .geometry import Extent


def to_words(cls_instance_or_name, as_string=True):

    if isinstance(cls_instance_or_name, type):
        class_name = cls_instance_or_name.__name__
    elif not isinstance(cls_instance_or_name, str):
        class_name = type(cls_instance_or_name).__name__
    else:
        class_name = cls_instance_or_name

    class_words = camel_to_snake(class_name).split("_")

    return " ".join(class_words) if as_string else class_words


def to_object(json_or_dict, aliases=None, from_camel=True, defaults=None):
    """ Transforms JSON data into an object """

    if isinstance(json_or_dict, str):
        json_or_dict = json.loads(json_or_dict)
    elif hasattr(json_or_dict, "get_data"):
        json_or_dict = json_or_dict.get_data()

    if aliases or defaults:
        json_or_dict = DictField(
            aliases=aliases, convert_camel=from_camel, defaults=defaults
        ).to_python(json_or_dict, None)

    return ObjectField(convert_camel=from_camel).to_python(json_or_dict, None)


def to_renderer(json_or_dict, from_camel=True):
    """
    Shortcut to build a renderer object from a dict or JSON
    :param json_or_dict: the value to convert into a renderer
    :param from_camel: implies conversion back to ESRI values if False
    """

    aliases = dict(RENDERER_ALIASES)
    defaults = ["symbol", "field", "field1", "field2", "field3", "label"]

    if from_camel:
        defaults.append("default_symbol")
    else:
        defaults.append("defaultSymbol")
        aliases = {v: k for k, v in aliases.items()}

    renderer = to_object(json_or_dict, aliases, from_camel, defaults)

    if getattr(renderer, "min", None) is None:
        setattr(renderer, "min", getattr(renderer, "min_val", None))

    if from_camel:
        if renderer.symbol:
            renderer.symbol = to_symbol(renderer.symbol, from_camel)
        if renderer.default_symbol:
            renderer.default_symbol = to_symbol(renderer.default_symbol, from_camel)

    return renderer


def to_symbol(json_or_dict, from_camel=True):
    """
    Shortcut to build a symbol object from a dict or JSON
    :param json_or_dict: the value to convert into a renderer
    :param from_camel: implies conversion back to ESRI values if False
    """

    aliases = {
        "imageData": "image",
        "xoffset": "offset_x",
        "yoffset": "offset_y"
    }
    defaults = [
        "type", "style", "color", "width", "height"
    ]

    if from_camel:
        defaults.extend(("offset_x", "offset_y"))
    else:
        defaults.extend(("xoffset", "yoffset"))
        aliases = {v: k for k, v in aliases.items()}

    if not is_symbol(json_or_dict):
        symbol = None
    else:
        symbol = to_object(json_or_dict, from_camel=from_camel, aliases=aliases, defaults=defaults)
        symbol.outline = to_symbol(getattr(symbol, "outline", None), from_camel)

    return symbol


def is_symbol(json_or_dict, key=None):
    if json_or_dict is None:
        return False

    if hasattr(json_or_dict, "get_data"):
        json_or_dict = json_or_dict.get_data()
    elif isinstance(json_or_dict, str):
        json_or_dict = json.loads(json_or_dict)

    if key is not None:
        return is_symbol(json_or_dict.get(key))
    else:
        return bool(json_or_dict and json_or_dict.get("type"))


def extent_to_polygon_wkt(extent_or_dict, **kwargs):
    """ Generates a quadrilateral POLYGON(...) from extent data """

    if extent_or_dict is None:
        raise ValueError("Extent or dict is required")

    if isinstance(extent_or_dict, dict):
        extent = extent_or_dict
    elif isinstance(extent_or_dict, Extent):
        extent = extent_or_dict.as_dict()
    else:
        extent = Extent(extent_or_dict).as_dict()

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
    if points is None:
        raise ValueError("A points array is required")
    return ", ".join(("{0} {1}".format(*p[0:2]) for p in points))


def _multi_points_to_str(multi_points):
    if multi_points is None:
        raise ValueError("An array of points arrays is required")
    return ", ".join("({})".format(_points_to_str(points)) for points in multi_points)
