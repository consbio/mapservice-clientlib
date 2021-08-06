from restle.actions import Action
from restle.serializers import URLSerializer, JSONSerializer

from .actions import QueryAction


FEATURE_LAYER_PARAMS = (
    "f", "where", "object_ids", "geometry", "geometry_type", "in_sr", "spatial_rel", "relation_param", "time",
    "distance", "units", "out_fields", "return_geometry", "max_allowable_offset", "geometry_precision",
    "out_sr", "gdb_version", "return_distinct_values", "return_ids_only", "return_count_only",
    "return_extent_only", "order_by_fields", "group_by_fields_for_statistics", "out_statistics", "return_z",
    "return_m", "multipatch_option", "result_offset", "result_record_count", "token"
)
FEATURE_LAYER_QUERY = QueryAction(
    "query",
    http_method="POST",
    optional_params=FEATURE_LAYER_PARAMS,
    param_defaults={"f": "json"},
    param_aliases={
        "object_ids": "objectIds",
        "geometry_type": "geometryType",
        "in_sr": "inSR",
        "spatial_rel": "spatialRel",
        "relation_param": "relationParam",
        "out_fields": "outFields",
        "return_geometry": "returnGeometry",
        "max_allowable_offset": "maxAllowableOffset",
        "geometry_precision": "geometryPrecision",
        "out_sr": "outSR",
        "gdb_version": "gdbVersion",
        "return_distinct_values": "returnDistinctValues",
        "return_ids_only": "returnIdsOnly",
        "return_count_only": "returnCountOnly",
        "return_extent_only": "returnExtentOnly",
        "order_by_fields": "orderByFields",
        "group_by_fields_for_statistics": "groupByFieldsForStatistics",
        "out_statistics": "outStatistics",
        "return_z": "returnZ",
        "return_m": "returnM",
        "multipatch_option": "multipatchOption",
        "result_offset": "resultOffset",
        "result_record_count": "resultRecordCount"
    },
    params_via_post=True,
    serializer=URLSerializer,
    deserializer=JSONSerializer,
    response_type=Action.DICT_RESPONSE
)

FEATURE_LAYER_TIME_PARAMS = ("f", "token")
FEATURE_LAYER_TIME_QUERY = QueryAction(
    "time-query",
    http_method="POST",
    optional_params=FEATURE_LAYER_TIME_PARAMS,
    param_defaults={"f": "json"},
    param_aliases={},
    params_via_post=True,
    serializer=URLSerializer,
    deserializer=JSONSerializer,
    response_type=Action.DICT_RESPONSE
)


FEATURE_SERVER_PARAMS = (
    "f", "layer_defs", "geometry", "geometry_type", "in_sr", "spatial_rel", "time", "out_sr", "gdb_version",
    "return_geometry", "max_allowable_offset", "return_ids_only", "return_count_only", "return_z", "return_m",
    "geometry_precision"
)
FEATURE_SERVER_QUERY = QueryAction(
    "query",
    http_method="POST",
    optional_params=FEATURE_SERVER_PARAMS,
    param_defaults={"f": "json"},
    param_aliases={
        "layer_defs": "layerDefs",
        "geometry_type": "geometryType",
        "in_sr": "inSR",
        "spatial_rel": "spatialRel",
        "gdb_version": "gdbVersion",
        "return_geometry": "returnGeometry",
        "max_allowable_offset": "maxAllowableOffset",
        "return_ids_only": "returnIdsOnly",
        "return_count_only": "returnCountOnly",
        "return_z": "returnZ",
        "return_m": "returnM",
        "geometry_precision": "geometryPrecision"
    },
    params_via_post=True,
    serializer=URLSerializer,
    response_type=Action.DICT_RESPONSE
)
