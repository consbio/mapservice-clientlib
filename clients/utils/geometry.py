import copy
import json
import re

from bisect import bisect_left
from decimal import Decimal
from itertools import product
from math import cos, fabs, radians, sqrt
from parserutils.numbers import is_number
from pyproj import Proj, transform

from ..exceptions import BadExtent, BadSpatialReference


EXTENT_KEYS = ("xmin", "ymin", "xmax", "ymax")
SPATIAL_REF_KEYS = ("wkid", "wkt", "srs")
GLOBAL_EXTENT_WEB_MERCATOR = (-20037508.342789244, -20037342.166152496, 20037508.342789244, 20037342.16615247)
GLOBAL_EXTENT_WGS84 = (-180.0, -90.0, 180.0, 90.0)
GLOBAL_EXTENT_WGS84_CORRECTED = (-180.0, -85.0511, 180.0, 85.0511)
SQL_BOX_REGEX = re.compile("BOX\((.*) (.*),(.*) (.*)\)")


def extract_significant_digits(number):
    is_negative = number < 0
    if is_negative:
        number = 0 - number

    dijits = 0
    if 0.1 <= number < 10:
        dijits = 1
    elif 10 <= number < 100:
        dijits = 0
    elif number >= 100:
        dijits = -1

    rounded = round(number, dijits)
    if dijits < 1:
        rounded = int(rounded)  # In this case, we have a whole number, so return that
    if is_negative:
        rounded = 0 - rounded

    return rounded


def union_extent(extents):
    extents = [e for e in (extents or "") if e]
    if not extents:
        return None

    if any(not isinstance(e, Extent) for e in extents):
        extent_types = ", ".join(type(e).__name__ for e in extents)
        raise ValueError(f'Invalid extent type: expected Extent, got "{extent_types}"')

    extent = extents[0].clone()

    for next_extent in extents[1:]:
        extent.xmin = min(extent.xmin, next_extent.xmin)
        extent.ymin = min(extent.ymin, next_extent.ymin)
        extent.xmax = max(extent.xmax, next_extent.xmax)
        extent.ymax = max(extent.ymax, next_extent.ymax)

    return extent


class Extent(object):
    """ Provides easy handling of extent through various functions below, and abstract out ESRI / WMS differences """

    def __init__(self, extent, spatial_reference=None):
        self.xmin = None
        self.ymin = None
        self.xmax = None
        self.ymax = None

        self._original_format = None

        if isinstance(extent, str):
            extent = json.loads(extent)

        if isinstance(extent, dict):
            self._original_format = "dict"

            try:
                for key in EXTENT_KEYS:
                    setattr(self, key, extent[key])
            except KeyError:
                raise BadExtent("Invalid extent: missing required keys", extent=extent)

            if spatial_reference is None:
                spatial_reference = extent.get("spatialReference", extent.get("spatial_reference"))

        elif isinstance(extent, (list, tuple)):
            self._original_format = "list"

            try:
                self.xmin = extent[0]
                self.ymin = extent[1]
                self.xmax = extent[2]
                self.ymax = extent[3]
            except IndexError:
                raise BadExtent("Invalid extent: insufficient length", extent=extent)

        elif all(hasattr(extent, prop) for prop in EXTENT_KEYS):
            self._original_format = "obj"

            for key in EXTENT_KEYS:
                setattr(self, key, getattr(extent, key))
            if spatial_reference is None:
                spatial_reference = getattr(extent, "spatial_reference", None)

        else:
            extent_type = type(extent).__name__
            raise BadExtent(
                f"Invalid extent: must be dict, tuple or compatible object, not {extent_type}",
                extent=extent
            )

        if any(not is_number(coord) for coord in (self.xmin, self.ymin, self.xmax, self.ymax)):
            raise BadExtent("Invalid extent coordinates", extent=extent)
        else:
            self.xmin, self.ymin, self.xmax, self.ymax = (
                float(self.xmin),
                float(self.ymin),
                float(self.xmax),
                float(self.ymax)
            )

        if spatial_reference is None:
            raise BadSpatialReference("Spatial reference required for Extent", extent=extent)
        else:
            self.spatial_reference = SpatialReference(spatial_reference)

    def __repr__(self):
        return self.as_json_string()

    def clone(self):
        return copy.deepcopy(self)

    def as_dict(self, esri_format=True, precision=None):
        extent = {}
        for key in EXTENT_KEYS:
            val = getattr(self, key)
            extent[key] = val if precision is None else round(val, precision)
        if self.spatial_reference:
            srs_key = "spatialReference" if esri_format else "spatial_reference"
            extent[srs_key] = self.spatial_reference.as_dict(esri_format)
        return extent

    def as_list(self, precision=None):
        extent = (getattr(self, key) for key in EXTENT_KEYS)
        if precision is None:
            return list(extent)
        else:
            return [round(val, precision) for val in extent]

    def as_original(self, esri_format=True, precision=None):
        if self._original_format == "dict":
            return self.as_dict(esri_format, precision)
        elif self._original_format == "list":
            return self.as_list(precision)
        elif precision is not None:
            return Extent(self.as_dict(esri_format, precision))
        else:
            return self

    def as_bbox_string(self, precision=4):
        return ",".join(str(xy) for xy in self.as_list(precision))

    def as_json_string(self, esri_format=True, precision=4):
        return json.dumps(self.as_dict(esri_format, precision), sort_keys=True)

    def limit_to_global_extent(self):

        if not self.spatial_reference.is_web_mercator():
            raise ValueError("Extent must be Web Mercator in order to limit global extent")

        new_extent = self.clone()
        new_extent.xmin = max(GLOBAL_EXTENT_WEB_MERCATOR[0], new_extent.xmin)
        new_extent.ymin = max(GLOBAL_EXTENT_WEB_MERCATOR[1], new_extent.ymin)
        new_extent.xmax = min(GLOBAL_EXTENT_WEB_MERCATOR[2], new_extent.xmax)
        new_extent.ymax = min(GLOBAL_EXTENT_WEB_MERCATOR[3], new_extent.ymax)

        return new_extent

    def limit_to_global_width(self):

        if not self.spatial_reference.is_web_mercator():
            raise ValueError("Extent must be Web Mercator in order to limit global width")

        new_extent = self.clone()
        new_extent.xmin = max(GLOBAL_EXTENT_WEB_MERCATOR[0], new_extent.xmin)
        new_extent.xmax = min(GLOBAL_EXTENT_WEB_MERCATOR[2], new_extent.xmax)

        return new_extent

    def crosses_anti_meridian(self):

        if not self.spatial_reference.is_web_mercator():
            raise ValueError("Extent must be Web Mercator in order to test antimeridian")

        return self.xmin < GLOBAL_EXTENT_WEB_MERCATOR[0] or self.xmax > GLOBAL_EXTENT_WEB_MERCATOR[2]

    def has_negative_extent(self):

        if not self.spatial_reference.is_web_mercator():
            raise ValueError("Extent must be Web Mercator in order to test for negative extent")

        return self.xmin < GLOBAL_EXTENT_WEB_MERCATOR[0]

    def get_negative_extent(self):
        """
        Extents normalized by ArcGIS on the front end may have a negative extent for the area to the left of the
        meridian. This method returns that component as an extent that can be sent to image retrieval routines.
        The negative_extent will have the same height and same width as the original extent, but the xmin and
        xmax will be different.
        """
        if self.has_negative_extent():
            new_extent = self.clone()
            new_extent.xmin = GLOBAL_EXTENT_WEB_MERCATOR[2] - (GLOBAL_EXTENT_WEB_MERCATOR[0] - self.xmin)
            new_extent.xmax = new_extent.xmin + self.get_dimensions()[0]
            return new_extent

    def fit_to_dimensions(self, width, height):
        """ Expand self as necessary to fit dimensions of image """

        new_extent = self.clone()
        img_aspect_ratio = float(height) / float(width)
        x_diff, y_diff = new_extent.get_dimensions()
        extent_aspect_ratio = 1 if x_diff == 0 else y_diff / x_diff

        if img_aspect_ratio > extent_aspect_ratio:
            # img is taller than extent
            diff_extent_units = ((img_aspect_ratio * x_diff) - y_diff) / 2.0
            new_extent.ymin -= diff_extent_units
            new_extent.ymax += diff_extent_units
        elif img_aspect_ratio < extent_aspect_ratio:
            # img is wider than extent
            diff_extent_units = ((y_diff / img_aspect_ratio) - x_diff) / 2.0
            new_extent.xmin -= diff_extent_units
            new_extent.xmax += diff_extent_units

        return new_extent

    def fit_image_dimensions_to_extent(self, width, height, target_resolution=None):
        """
        Return image dimensions that fit the extent's aspect ratio.
        If target_resolution is provided, use that for calculating dimensions instead (useful for WMS client)
        """

        resolution = target_resolution or self.get_image_resolution(width, height)
        img_aspect_ratio = float(height) / float(width)
        x_diff, y_diff = self.get_dimensions()
        extent_aspect_ratio = y_diff / x_diff

        if img_aspect_ratio > extent_aspect_ratio:
            # img is taller than extent
            diff_extent_units = ((img_aspect_ratio * x_diff) - y_diff) / 2.0
            offset_pixels = int(round(diff_extent_units / resolution, 0))
            height = height - 2 * offset_pixels
        elif img_aspect_ratio < extent_aspect_ratio:
            # img is wider than extent
            diff_extent_units = ((y_diff / img_aspect_ratio) - x_diff) / 2.0
            offset_pixels = int(round(diff_extent_units / resolution, 0))
            width = width - 2 * offset_pixels

        return width, height

    def get_image_resolution(self, width, height):
        x_diff, y_diff = self.get_dimensions()
        return sqrt((x_diff * y_diff) / (width * height))

    def project_to_web_mercator(self):
        """ Project self to Web Mercator (only some ESRI extents are valid here) """

        new_extent = self.clone()
        if self.spatial_reference.is_web_mercator():
            return new_extent

        if not self.spatial_reference.is_valid_proj4_projection():
            raise ValueError("Spatial reference is not valid for proj4, must use a different service to project")

        new_extent.xmin, new_extent.ymin, new_extent.xmax, new_extent.ymax = self._get_projected_extent("EPSG:3857")
        new_extent.spatial_reference.wkid = 3857
        new_extent.spatial_reference.srs = "EPSG:3857"

        return new_extent

    def project_to_geographic(self):
        """ Project self to geographic (only some ESRI extents are valid here) """

        new_extent = self.clone()
        if self.spatial_reference.is_geographic():
            return new_extent

        if not self.spatial_reference.is_valid_proj4_projection():
            raise ValueError("Spatial reference is not valid for proj4, must use a different service to project")

        new_extent.xmin, new_extent.ymin, new_extent.xmax, new_extent.ymax = self._get_projected_extent("EPSG:4326")
        new_extent.spatial_reference.wkid = 4326
        new_extent.spatial_reference.srs = "EPSG:4326"
        return new_extent

    def _correct_for_projection(self):

        if self.spatial_reference.is_web_mercator():
            self.spatial_reference.srs = "EPSG:3857"
        elif self.spatial_reference.wkid:
            self.spatial_reference.srs = f"EPSG:{self.spatial_reference.wkid}"

        # Apply y-axis corrections to avoid singularities in projection at latitude -90 or 90
        if self.spatial_reference.srs == "EPSG:4326":
            # Corrections applied as per open layers convention
            if self.ymin <= -90:
                self.ymin = -85.0511
            if self.ymax >= 90:
                self.ymax = 85.0511

    def _get_projected_extent(self, target_srs):
        """
        Densifies the edges with edge_points points between corners, and projects all of them.
        Geographic latitudes must first be bounded to the following or calculations will fail!
            -85.0511 <= y <= 85.0511
        :return: the outer bounds of the projected coordinates.
        """

        self._correct_for_projection()

        source_srs = self.spatial_reference.srs
        from_epsg = source_srs.strip().upper().startswith("EPSG:")
        source_proj = Proj(init=source_srs) if from_epsg else Proj(str(source_srs))
        target_proj = Proj(init=target_srs) if ":" in target_srs else Proj(str(target_srs))

        edge_points = 9

        samples = list(range(0, edge_points))
        x_diff, y_diff = self.get_dimensions()
        xstep = x_diff / (edge_points - 1)
        ystep = y_diff / (edge_points - 1)
        x_values, y_values = [], []

        for i, j in product(samples, samples):
            x_values.append(self.xmin + xstep * i)
            y_values.append(self.ymin + ystep * j)

        # TODO: check for bidirectional consistency, as is done in ncserve BoundingBox.project() method
        x_values, y_values = transform(source_proj, target_proj, x_values, y_values)

        projected_values = min(x_values), min(y_values), max(x_values), max(y_values)
        if any(not is_number(coord) for coord in projected_values):
            raise ValueError(f'Invalid projection coordinates for "{source_srs}": {projected_values}')

        return projected_values

    def get_scale_string(self, image_width):
        """
        This is modified to use the extent's southern latitude to mimic how ArcGIS displays the front end scale.
        :return: string representation of the current extent's scale
        """

        pixels_per_inch = 96

        web_mercator_extent = self.project_to_web_mercator()
        geo_extent = self.project_to_geographic()

        x_diff = web_mercator_extent.get_dimensions()[0]
        resolution = abs(x_diff / image_width)
        meters_per_inch = resolution * pixels_per_inch
        kilometers_per_inch = meters_per_inch / 1000
        southern_latitude = geo_extent.ymin

        scale_in_km = extract_significant_digits(kilometers_per_inch / self._calc_scale_factor(southern_latitude))
        scale_in_mi = extract_significant_digits(scale_in_km * 0.621371192237)

        return f"{scale_in_km} km ({scale_in_mi} miles)"

    def _calc_scale_factor(self, lat_degrees):
        """ Based on http://en.wikipedia.org/wiki/Mercator_projection#Scale_factor """
        return 1 / cos(radians(lat_degrees))

    def get_center(self):
        x_diff, y_diff = self.get_dimensions()
        return self.xmax - (x_diff / 2), self.ymax - (y_diff / 2)

    def get_dimensions(self):
        """ :return: the width, height of the extent """
        return float(self.xmax - self.xmin), float(self.ymax - self.ymin)

    def get_geographic_labels(self):
        extent = self.project_to_geographic()
        label = "{0:0.2f}\u00B0{1}"

        xmin_label = label.format(fabs(extent.xmin), "W" if extent.xmin < 0 else "E")
        xmax_label = label.format(fabs(extent.xmax), "W" if extent.xmax < 0 else "E")
        ymin_label = label.format(fabs(extent.ymin), "S" if extent.ymin < 0 else "N")
        ymax_label = label.format(fabs(extent.ymax), "S" if extent.ymax < 0 else "N")

        return xmin_label, ymin_label, xmax_label, ymax_label

    def set_to_center_and_scale(self, scale, width_in_pixels, height_in_pixels):
        """
        Centers on the current extent, then changes extent to the given scale and viewport's width and height
        :return: a new centered and scaled extent object, projected to Web Mercator
        """

        # This is the ratio from the LODS that we use
        resolution = scale / 3779.52

        projected = self.project_to_web_mercator()
        x_center, y_center = projected.get_center()

        x_units_from_center = (width_in_pixels / 2.0) * resolution
        y_units_from_center = (height_in_pixels / 2.0) * resolution

        projected.xmax = x_center + x_units_from_center
        projected.xmin = x_center - x_units_from_center
        projected.ymax = y_center + y_units_from_center
        projected.ymin = y_center - y_units_from_center

        return projected


class SpatialReference(object):

    def __init__(self, spatial_reference):
        self.srs = None          # WMS: spatial reference system (EPSG)
        self.wkid = None         # ESRI: well known id
        self.wkt = None          # ESRI: well known text
        self.latest_wkid = None  # Used by feature services

        if isinstance(spatial_reference, str):
            self.srs = spatial_reference

        elif isinstance(spatial_reference, (int, float)):
            self.wkid = spatial_reference

        elif isinstance(spatial_reference, dict):
            self.srs = spatial_reference.get("srs")

            # ESRI format: well-known text or id
            self.wkid = spatial_reference.get("wkid")
            self.wkt = spatial_reference.get("wkt")
            self.latest_wkid = spatial_reference.get("latestWkid", spatial_reference.get("latest_wkid"))

        elif any(hasattr(spatial_reference, prop) for prop in SPATIAL_REF_KEYS):

            self.wkid = getattr(spatial_reference, "wkid", None)
            for att in ("wkt", "srs", "latest_wkid"):
                setattr(self, att, getattr(spatial_reference, att, None))

        else:
            spatial_ref_type = type(spatial_reference).__name__
            raise BadSpatialReference(
                f"Invalid spatial reference: must be dict, string or compatible object, not {spatial_ref_type}",
                spatial_reference=spatial_reference
            )

        self.srs = str(self.srs or "").upper()

        if self.srs == "CRS:84":
            self.srs = "EPSG:4326"
        if not self.wkid and self.srs.startswith("EPSG:"):
            self.wkid = self.srs.split(":")[-1]

        if not (self.srs or self.wkid or self.wkt):
            raise BadSpatialReference("Invalid spatial reference: empty coordinate identifier")
        elif isinstance(self.wkid, str):
            try:
                self.wkid = int(self.wkid or 0)
            except ValueError:
                raise BadSpatialReference(f"Invalid wkid value: {self.wkid}")

    def __repr__(self):
        if self.srs:
            return f"srs: {self.srs}"
        elif self.wkid:
            return f"wkid: {self.wkid}"
        else:
            return f"wkt: {self.wkt}"

    def clone(self):
        return copy.deepcopy(self)

    def as_dict(self, esri_format=True):
        if not esri_format and self.srs:
            return {"srs": self.srs}
        elif self.wkid:
            return {"wkid": self.wkid}
        elif self.wkt:
            return {"wkt": self.wkt}
        else:
            return {"srs": self.srs}

    def as_json_string(self, esri_format=True):
        return json.dumps(self.as_dict(esri_format))

    def is_geographic(self):
        return (self.wkid == 4326 or self.srs == "EPSG:4326")

    def is_web_mercator(self):
        return (
            self.wkid in (3857, 102100, 102113) or
            self.srs in ("EPSG:3857", "EPSG:3785", "EPSG:900913", "EPSG:102113")
        )

    def is_valid_proj4_projection(self):
        """ If true, this can be projected using proj4; otherwise, need to use some external service to project """

        srs_prefix, srs_val = None, None
        if ":" in self.srs:
            srs_prefix, srs_val = self.srs.split(":", 1)

        # Only WKIDs < 33000 map to EPSG codes, as per
        #    http://gis.stackexchange.com/questions/18651/do-arcgis-spatialreference-object-factory-codes-correspond-with-epsg-numbers
        return (
            self.is_web_mercator() or
            bool(self.wkid and self.wkid < 33000) or
            (srs_prefix == "EPSG" and is_number(srs_val))
        )


class TileLevels(object):

    def __init__(self, resolutions):

        if not (resolutions and isinstance(resolutions, (list, tuple))):
            resolutions_type = type(resolutions).__name__
            raise ValueError(f"Resolutions must be list or tuple, not {resolutions_type}")

        try:
            # Values are resolutions, indexes are the tile levels
            self.resolutions = [float(res) for res in resolutions]
        except (TypeError, ValueError):
            raise ValueError(f"Resolutions must all be numeric: {resolutions}")

    def get_matching_resolutions(self, target_resolutions, precision=5):
        """ Get matching resolutions. Any resolution that matches within 5 decimal places is considered a match """

        if not (isinstance(target_resolutions, (list, tuple))):
            resolutions_type = type(target_resolutions).__name__
            raise ValueError(f"Target resolutions must be list or tuple, not {resolutions_type}")

        source = set([round(Decimal(res), precision) for res in self.resolutions])
        target = set([round(Decimal(res), precision) for res in target_resolutions])
        return source.intersection(target)

    def get_nearest_tile_level_and_resolution(self, target_resolution, allow_lower_resolution=False):
        """ Get the nearest tile level and resolution to best fit target extent. Expand to next level if necessary """

        if not is_number(target_resolution):
            resolutions_type = type(target_resolution).__name__
            raise ValueError(f"Target resolution must be a number, not {resolutions_type}")

        if allow_lower_resolution:
            diffs = [fabs(target_resolution - res) for res in self.resolutions]
            zoom_level = diffs.index(min(diffs))
        else:
            sorted_resolutions = sorted(round(res, 5) for res in self.resolutions)

            # Find the nearest index with resolution that is >= target_resolution
            last_index = len(sorted_resolutions) - 1
            nearest_index = min(last_index, bisect_left(sorted_resolutions, round(target_resolution, 5)))
            zoom_level = last_index - nearest_index

        return zoom_level, self.resolutions[zoom_level]

    def snap_extent_to_nearest_tile_level(self, extent, width, height, must_contain_extent=True):
        """
        Updates extent (in place) to fit the resolution that best contains extent.
        Aspect ratio of image / extent must be clean before calling this, and extent must be an Extent object
        """

        if not isinstance(extent, Extent):
            extent = Extent(extent)

        target_resolution = extent.get_image_resolution(width, height)
        resolution = self.get_nearest_tile_level_and_resolution(target_resolution, not must_contain_extent)[1]

        if fabs(resolution - target_resolution) > 0.0001:
            # Recalculate extent to fit new width from resolution
            new_extent = extent.clone()
            x_diff = (resolution * width) - (extent.xmax - extent.xmin)
            y_diff = (resolution * height) - (extent.ymax - extent.ymin)
            new_extent.xmin -= (x_diff / 2.0)
            new_extent.ymin -= (y_diff / 2.0)
            new_extent.xmax += (x_diff / 2.0)
            new_extent.ymax += (y_diff / 2.0)
            return new_extent.fit_to_dimensions(width, height)

        return extent
