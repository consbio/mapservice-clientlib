import io
import json
import logging
import math
import re
import requests

from PIL import Image
from threading import Thread
from urllib.parse import urlparse, urlsplit

from ags import exceptions as ags
from ags.admin.server import ServerAdmin
from parserutils.collections import accumulate_items, setdefaults
from parserutils.urls import get_base_url
from restle.fields import TextField, IntegerField, BooleanField, NumberField, ToManyField

from .exceptions import BadExtent, BadTileScheme, ContentError, HTTPError, ImageError, NoLayers, ServiceError
from .query.arcgis import FEATURE_LAYER_QUERY, FEATURE_LAYER_TIME_QUERY, FEATURE_SERVER_QUERY
from .query.arcgis import FEATURE_LAYER_PARAMS, FEATURE_LAYER_TIME_PARAMS
from .query.fields import CommaSeparatedField, DrawingInfoField, ExtentField
from .query.fields import ObjectField, SpatialReferenceField, TimeInfoField
from .resources import ClientResource, DEFAULT_USER_AGENT
from .utils import classproperty
from .utils.conversion import to_renderer
from .utils.geometry import Extent, TileLevels, SpatialReference
from .utils.images import base64_to_image, count_colors, image_to_base64, overlay_images
from .utils.images import stack_images_vertically


logger = logging.getLogger(__name__)


ARCGIS_MULTIPLIER = 1.333333
ARCGIS_SERVICE_ID_PATTERN = re.compile("(?<=services/).*(?=/MapServer)")
DEFAULT_ARCGIS_BACKGROUND_COLOR = (255, 255, 254, 255)
MAX_FEATURE_REQUEST = 1000

# From http://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer (12/16/2013); index = zoom level
ARCGIS_RESOLUTIONS = (
    156543.033928, 78271.5169639999, 39135.7584820001, 19567.8792409999, 9783.93962049996, 4891.96981024998,
    2445.98490512499, 1222.99245256249, 611.49622628138, 305.748113140558, 152.874056570411, 76.4370282850732,
    38.2185141425366, 19.1092570712683, 9.55462853563415, 4.77731426794937, 2.38865713397468, 1.19432856685505,
    0.597164283559817, 0.298582141647617
)
ARCGIS_TILEINFO_RESOLUTIONS = TileLevels(ARCGIS_RESOLUTIONS)

# First entry is used as default for getting images, 102100 must come first as older servers don't know about 3857.
# If we know that the server we are requesting images from is 10 sp1 or later, just use 3857.
WEB_MERCATOR_WKIDs = (102100, 3857, 102113)

WEB_MERCATOR_SRS = (
    "+proj=merc +a=6378137 +b=6378137 +lat_ts=0.0 +lon_0=0.0 +x_0=0.0 +y_0=0 +units=m +k=1.0 +nadgrids=@null +no_defs"
)


class ArcGISResource(ClientResource):
    """ Enables version validation and defines common fields """

    minimum_version = 10.1

    version = NumberField(name="currentVersion")
    description = TextField()
    copyright_text = TextField(required=False)
    capabilities = TextField()
    supported_query_formats = TextField(required=False)
    max_record_count = IntegerField(required=False)

    time_enabled = False
    time_info = TimeInfoField(required=False)

    _client_descriptor = "ArcGIS"

    def get_time_info_prop(self, prop, default=None):
        val = getattr(self.time_info, prop, None)
        return default if val is None else val

    def populate_field_values(self, data):
        """ Overridden to handle 'error' key in JSON response, and validate version """

        if "error" in data:
            self.handle_error(data)

        super(ArcGISResource, self).populate_field_values(data)

    def handle_error(self, data, message="", error_class=ServiceError):

        error = data["error"]
        if "message" not in error:
            message = message or f"Unknown ArcGIS error: {error}"
            raise ContentError(message, params=self._params, url=self._url, **error)

        message = (error.pop("message") or "").lower() or message

        # Override the catch-all 500 status for specific errors

        if "token required" in message:
            status_code = 401  # Service requires authentication (not supported)
        elif "not found" in message:
            status_code = 404  # Service not found
        elif "configuration error" in message:
            status_code = 503  # Service unavailable (approximates configuration issue)
        else:
            status_code = error.get("code", 500)

        raise error_class(message, status_code=status_code, url=self._url, **error)


class ArcGISSecureResource(ClientResource):
    """
    Adds an ArcGIS token to Resource queries when provided, or when derived from username and password.
    If token is not provided, or if either username or password are missing, a public query is sent.
    """

    @staticmethod
    def generate_token(service_url, username, password, duration=None):
        """
        Returns a ServerAdmin object with a generated token. Use generate_token().token to get just the token text.
        :param service_url: The URL of the map service
        :param username: The ArcGIS server username
        :param password: The ArcGIS server password
        :param duration: The duration of the token in minutes
        """

        parsed_url = urlparse(service_url)

        server_admin = ServerAdmin(
            host=parsed_url.netloc,
            username=username,
            password=password,
            secure=(parsed_url.scheme == "https")
        )

        try:
            server_admin.generate_token(duration=duration)
        except ags.HTTPError:
            pass  # This happens when credentials are missing, invalid, or not needed
        except Exception:
            # Ignore all others: failure here for any reason should never stop an import
            # Even if token is required, the same lack of access will stop the import later
            logger.warning(f"ArcGIS secure client failed to generate token")

        return server_admin

    def _get(self, url, username=None, password=None, token=None, **kwargs):
        """ Overridden to capture URL info, and manage optional secure ArcGIS credentials """

        super(ArcGISSecureResource, self)._get(url, **kwargs)

        parsed_url = urlsplit(url)

        self.hostname = parsed_url.netloc

        # Extract the local ID of this service on the server, which includes its folder path in the services directory
        service_pattern_match = ARCGIS_SERVICE_ID_PATTERN.search(parsed_url.path)
        self.service_id = service_pattern_match.group() if service_pattern_match else None

        self.arcgis_credentials = {}
        self.arcgis_credentials["username"] = self._username = username

        # Attempt to derive token, or assume service is public

        if token:
            self._params["token"] = token
        elif username and password:
            server_admin = ArcGISSecureResource.generate_token(self._url, username, password)
            if server_admin.token:
                self._params["token"] = server_admin.token

        self.arcgis_credentials["token"] = self._token = self._params.get("token", token)


class ArcGISServerResource(ArcGISResource, ArcGISSecureResource):
    """ Defines common fields for inheriting ArcGIS service resources """

    service_description = TextField()

    document_info = ObjectField(class_name="DocumentInfo", required=False)
    full_extent = ExtentField()
    initial_extent = ExtentField()
    spatial_reference = SpatialReferenceField()

    tables = ObjectField(class_name="Table", required=False)

    @classproperty
    @classmethod
    def service_name(cls):
        service_name = super(ArcGISServerResource, cls).service_name
        return service_name.replace("server service", "service")

    def populate_field_values(self, data):

        super(ArcGISServerResource, self).populate_field_values(data)

        # At the map server level, interval and units are described in default_* fields
        self.time_enabled = (
            self.time_info is not None and
            len(self.get_time_info_prop("time_extent", [])) == 2 and
            all(self.get_time_info_prop(prop) for prop in ("default_interval", "default_units"))
        )


class ArcGISLayerResource(ArcGISResource, ArcGISSecureResource):
    """ Defines common fields for inheriting ArcGIS layer service resources """

    id = IntegerField()
    name = TextField()
    type = TextField()
    type_id_field = TextField(required=False)
    display_field = TextField()

    fields = ObjectField(class_name="Field", required=False)
    edit_fields_info = ObjectField(class_name="EditFieldsInfo", required=False)
    ownership_based_access_control_for_features = ObjectField(class_name="FeatureAccessControl", required=False)
    relationships = ObjectField(class_name="Relationship", required=False)

    default_visibility = BooleanField(default=True)
    has_attachments = BooleanField(default=False)
    has_labels = BooleanField(default=False)
    is_versioned = BooleanField(name="isDataVersioned", default=False)

    supports_advanced_queries = BooleanField(default=False)
    supports_rollback_on_failure = BooleanField(default=False)
    supports_statistics = BooleanField(default=False)
    sync_can_return_changes = BooleanField(default=False)

    extent = ExtentField()
    geometry_type = TextField()
    min_scale = NumberField()
    max_scale = NumberField()
    drawing_info = DrawingInfoField(required=False)

    def populate_field_values(self, data):

        super(ArcGISLayerResource, self).populate_field_values(data)

        self.time_enabled = (
            self.time_info is not None and
            len(self.get_time_info_prop("time_extent", [])) == 2 and
            all(self.get_time_info_prop(prop) for prop in ("interval", "units"))
        )


class ArcGISTiledImageResource(ArcGISServerResource):

    min_scale = NumberField(default=0)
    max_scale = NumberField(default=0)
    max_image_height = IntegerField(required=False)
    max_image_width = IntegerField(required=False)

    tile_info = ObjectField(class_name="TileInfo", required=False)

    def populate_field_values(self, data):
        """ Overridden to validate tile info """

        super(ArcGISTiledImageResource, self).populate_field_values(data)

        self.validate_tile_scheme()

    def generate_image_from_query(self, extent, width, height, image_path, params):

        try:
            if self.tile_info is not None:
                tiled_image = self._get_tiled_image(extent, width, height)

                # Paste image for extent left of the central meridian, if it exists
                if extent.has_negative_extent():
                    negative_extent = extent.get_negative_extent()
                    negative_image = self._get_tiled_image(negative_extent, width, height)
                    tiled_image.paste(negative_image, (0, 0), negative_image)

                return tiled_image

            # TODO: support more than just Web Mercator
            # TODO: validate bbox == bboxSR (imageSR is target)
            image_url = "/".join(u.strip("/") for u in (self._url, image_path))
            image_params = {
                "f": "image",
                "bbox": extent.as_bbox_string(),
                "bboxSR": WEB_MERCATOR_WKIDs[0],
                "imageSR": WEB_MERCATOR_WKIDs[0],
                "size": ",".join(str(i) for i in (width, height)),
                "format": "png24"
            }
            if self._token:
                image_params["token"] = self._token

            image_params.update(params or {})

            image_data = io.BytesIO(self._make_request(image_url, image_params).content)
            image_object = Image.open(image_data).convert("RGBA")

            # Paste image for extent left of the central meridian, if it exists
            if extent.has_negative_extent():
                image_params["bbox"] = extent.get_negative_extent().as_bbox_string()
                response = self._make_request(image_url, image_params)
                negative_data = io.BytesIO(response.content)
                negative_image = Image.open(negative_data).convert("RGBA")
                image_object.paste(negative_image, (0, 0), negative_image)

            return image_object

        except (BadExtent, HTTPError, ImageError):
            raise  # Caught from self._get_tiled_image

        except requests.exceptions.HTTPError as ex:
            raise HTTPError(
                "The ArcGIS service image query did not respond correctly",
                params=image_params, underlying=ex, url=image_url
            )
        except (IOError, ValueError) as ex:
            raise ImageError(
                "The ArcGIS service did not return a valid image",
                params=image_params, underlying=ex, url=image_url
            )

    def _get_tiled_image(self, extent, width, height):

        tile_levels = TileLevels([lod.resolution for lod in self.tile_info.lods])
        target_resolution = extent.get_image_resolution(width, height)
        zoom_level, resolution = tile_levels.get_nearest_tile_level_and_resolution(target_resolution)

        try:
            if math.fabs(resolution - target_resolution) > 0.0001:  # Nearest tile resolution is not close enough!
                outside_range = (
                    self.tile_info.lods[-1].resolution - target_resolution > 0.0001 or
                    target_resolution - self.tile_info.lods[0].resolution > 0.0001
                )
                if outside_range:
                    # Return blank image (just means we're zoomed too far up or down)
                    return Image.new("RGBA", (width, height), (255, 255, 255, 0))
                else:
                    # If the target resolution is inside the range, then the extent hasn't been corrected
                    error = "\n\t".join((
                        "Invalid extent: must be corrected for zoom levels",
                        "Cannot retrieve tiled map service image:",
                        "Extent resolution does not match a valid zoom level resolution.",
                        "Target resolution:{:.5f}, calculated resolution:{:.5f}".format(target_resolution, resolution)
                    ))
                    raise BadExtent(error, extent=extent, url=self._url)

            tile_origin = self.tile_info.origin
            tile_height_in_pixels = self.tile_info.rows
            tile_width_in_pixels = self.tile_info.cols
            tile_width_in_map_units = tile_width_in_pixels * resolution
            tile_height_in_map_units = tile_height_in_pixels * resolution

            # Find the starting and ending tile coordinates for this resolution (based on extent of service)
            available_first_row = int(math.floor((tile_origin.y - self.full_extent.ymax) / tile_height_in_map_units))
            available_last_row = int(math.floor((tile_origin.y - self.full_extent.ymin) / tile_height_in_map_units))
            available_first_col = int(math.floor((self.full_extent.xmin - tile_origin.x) / tile_width_in_map_units))
            available_last_col = int(math.floor((self.full_extent.xmax - tile_origin.x) / tile_width_in_map_units))

            offset_x_in_pixels = 0  # Refers to how far right and up the extent"s origin is compared to the origin tile
            shift_x = 0             # Refers to how far off it is from the boundary of the world extent

            if tile_origin.x < extent.xmin:
                offset_x_in_pixels = (extent.xmin - tile_origin.x) / resolution
            else:
                shift_x = tile_origin.x - extent.xmin

            offset_y_in_pixels = 0
            shift_y = 0
            if tile_origin.y > extent.ymax:
                offset_y_in_pixels = (tile_origin.y - extent.ymax) / resolution
            else:
                shift_y = extent.ymax - tile_origin.y

            first_tile_col = max(int(math.floor(offset_x_in_pixels / tile_width_in_pixels)), available_first_col)
            first_tile_row = max(int(math.floor(offset_y_in_pixels / tile_height_in_pixels)), available_first_row)

            offset_from_first_x = offset_x_in_pixels - (first_tile_col * tile_width_in_pixels)
            offset_from_first_y = offset_y_in_pixels - (first_tile_row * tile_height_in_pixels)

            # Overflow rows and columns by 1
            number_of_columns = int(math.ceil(((extent.xmax - extent.xmin) - shift_x) / tile_width_in_map_units)) + 1
            number_of_rows = int(math.ceil(((extent.ymax - extent.ymin) - shift_y) / tile_height_in_map_units)) + 1

            last_tile_col = min(number_of_columns + first_tile_col, available_last_col)
            last_tile_row = min(number_of_rows + first_tile_row, available_last_row)

            base_image = Image.new("RGBA", (
                number_of_columns * tile_width_in_pixels, number_of_rows * tile_height_in_pixels
            ))

            tile_threads = []
            for row_index, row in enumerate(range(first_tile_row, last_tile_row + 1)):
                for column_index, column in enumerate(range(first_tile_col, last_tile_col + 1)):
                    tile_threads.append(
                        Thread(target=self._render_single_tile, args=(
                            zoom_level, row, column, row_index, column_index,
                            tile_height_in_pixels, tile_width_in_pixels, base_image
                        ))
                    )
            for thread in tile_threads:
                thread.start()
            for thread in tile_threads:
                thread.join()

            base_image.load()

            offset_from_first_x = int(math.floor(offset_from_first_x))
            offset_from_first_y = int(math.floor(offset_from_first_y))
            cropped_image = base_image.crop((
                offset_from_first_x, offset_from_first_y,
                width + offset_from_first_x, height + offset_from_first_y
            ))

            if shift_x != 0 or shift_y != 0:
                shifted_image = Image.new("RGBA", (width, height))
                shifted_image.paste(cropped_image, (
                    int(math.ceil(shift_x / resolution)), int(math.ceil(shift_y / resolution))
                ))
                cropped_image = shifted_image

            return cropped_image

        except BadExtent:
            raise
        except (IOError, ValueError) as ex:
            raise ImageError(
                "The ArcGIS service tiled image could not be generated",
                underlying=ex, tile_info=self.tile_info, url=self._url
            )

    def _render_single_tile(self, zoom_level, url_row, url_col, row, col, tile_height, tile_width, base_image):
        tile_url = "{base_url}/tile/{zoom}/{row}/{col}".format(
            base_url=self._url.strip("/"),
            zoom=int(zoom_level),
            row=int(url_row),
            col=int(url_col)
        )
        tile_params = {"token": self._token} if self._token else {}

        try:
            response = self._make_request(tile_url, tile_params)
        except requests.exceptions.HTTPError as ex:
            status_code = getattr(getattr(ex, "response", None), "status_code", None)
            raise HTTPError(
                "The ArcGIS single tile query did not respond correctly",
                params=tile_params, status_code=status_code, underlying=ex, url=tile_url
            )

        base_image.paste(
            Image.open(io.BytesIO(response.content)).convert("RGBA"),
            (int(col * tile_width), int(row * tile_height))
        )

    def validate_tile_scheme(self):
        """
        If service is tiled, it must be in Web Mercator and tiled according to ArcGIS scheme hard-coded above.
        Service properties must already have been fetched.
        """

        if self.tile_info is None:
            return  # No tile scheme is a valid tile scheme

        message = None

        if getattr(self.tile_info.spatial_reference, "wkid", None) not in WEB_MERCATOR_WKIDs:
            message = "ArcGIS tiled service missing required wkid for mercator"
        elif self.tile_info.rows != self.tile_info.cols or self.tile_info.rows not in (256, 512):
            message = "ArcGIS tiled service missing required dimensions"
        elif not ARCGIS_TILEINFO_RESOLUTIONS.get_matching_resolutions([lod.resolution for lod in self.tile_info.lods]):
            message = "ArcGIS tiled service LODs do not match at least one of the base map LODs"

        if message is not None:
            raise BadTileScheme(message=message, tile_info=self.tile_info, url=self._url)


class MapLayerResource(ArcGISLayerResource):
    """ Compatible with ArcGIS map layer resources >= version 10.1 """

    parent = ObjectField(name="parentLayer", class_name="ParentLayer", required=False)
    sub_layers = ObjectField(class_name="ChildLayer", required=False, aliases={"name": "title"})
    legend = ObjectField(class_name="LegendElement", default=[], aliases={
        "currentVersion": "version",
        "imageData": "image_base64",
        "defaultValue": "content_type",
        "LegendValue": "values"
    })

    can_modify_layer = BooleanField(default=False)
    can_scale_symbols = BooleanField(default=False)
    definition_query = TextField(name="definitionExpression", required=False)
    popup_type = TextField(name="htmlPopupType", required=False)

    class Meta:
        case_sensitive_fields = False
        get_parameters = {"f": "json"}
        match_fuzzy_keys = True


class MapLegendResource(ArcGISSecureResource):
    """
    There is no direct end point to query individual legend elements for a layer.
    This resource is only used to convert legend element data to objects under a layer.
    """

    version = NumberField(name="currentVersion")
    layer_id = IntegerField()
    layer_name = TextField()
    layer_type = TextField()
    min_scale = NumberField()
    max_scale = NumberField()

    label = TextField()
    url = TextField()
    image_base64 = TextField(name="imageData")
    content_type = TextField()
    height = IntegerField()
    width = IntegerField()
    values = ObjectField(class_name="LegendValue", required=False)

    _client_descriptor = ArcGISResource._client_descriptor

    class Meta:
        case_sensitive_fields = False
        get_parameters = {"f": "json"}
        match_fuzzy_keys = True

    def populate_field_values(self, data):
        """ Overridden to massage legend element data before populating fields """

        if "layerId" in data and "url" in data:
            base_url = self._url[:self._url.index("/MapServer")]
            layer = data["layerId"]
            path = data["url"]

            data["url"] = f"{base_url}/MapServer/{layer}/images/{path}"

        super(MapLegendResource, self).populate_field_values(data)


class MapServerResource(ArcGISTiledImageResource):
    """ Compatible with ArcGIS map service resources >= version 10.1 """

    version = NumberField(name="currentVersion", required=False)  # Overridden not to require

    name = TextField(name="mapName")
    units = TextField(required=False)
    export_tiles_allowed = BooleanField(default=False)
    single_fused_map_cache = BooleanField(default=False)
    supports_dynamic_layers = BooleanField(default=False)
    supported_extensions = TextField(required=False)
    supported_image_format_types = TextField()

    layers = None  # Populated dynamically later

    class Meta:
        case_sensitive_fields = False
        get_parameters = {"f": "json"}
        match_fuzzy_keys = True

    def populate_field_values(self, data):
        """ Overridden to flexibly populate layers and legend """

        super(MapServerResource, self).populate_field_values(data)

        # Load all layers at once with full layer detail for each
        layer_url = "{0}/layers".format(self._url.strip("/"))
        self.layers = MapLayerResource.bulk_get(
            layer_url,
            strict=self._strict,
            session=(self._layer_session or self._session),
            bypass_version=self._bypass_version,
            bulk_key="layers", bulk_defaults={"currentVersion": self.version},
            **self.arcgis_credentials
        )
        if not self.layers:
            raise NoLayers("The ArcGIS map service does not have any layers", url=self._url)

        # Override blank or unhelpfully defaulted map service names

        if not self.name or self.name.lower() == "layers":
            root_layers = [layer for layer in self.layers if not layer.parent]

            if len(root_layers) == 1:
                self.name = root_layers[0].name

        # Load all legends from the only known legend end point, and assign them to each layer

        legend_url = "{0}/legend/".format(self._url.strip("/"))
        legend_elements = MapLegendResource.bulk_get(
            legend_url,
            strict=self._strict,
            session=(self._layer_session or self._session),
            bypass_version=self._bypass_version,
            bulk_key="layers.legend", bulk_defaults={"currentVersion": self.version},
            **self.arcgis_credentials
        )

        # Assign separately queried legend elements to respective layers

        legend_map = accumulate_items((le.layer_id, le) for le in legend_elements)
        for layer in self.layers:
            layer.legend = legend_map.get(layer.id, [])

        # Update legend element images for raster layers with more than three elements

        for layer in (l for l in self.layers if "raster" in l.type.lower() and len(l.legend) >= 3):
            max_colors = max([count_colors(base64_to_image(l.image_base64)) for l in layer.legend])

            if max_colors and max_colors > 3 and len(layer.legend) == 3:
                # If there are more than 3 colors (transparent, border, fill), then this is stretched.
                # But we only need to do something different if there are 3 patches (most common)
                images = []
                for element in layer.legend:
                    images.append(base64_to_image(element.image_base64))
                    element.image_base64 = None
                    element.url = None

                # Only middle element gets the color patch
                layer.legend[1].image_base64 = image_to_base64(stack_images_vertically(images))

    def get_image(
        self, extent, width, height, custom_renderers=None, layer_defs="", layers="", time="", **kwargs
    ):
        """
        Note: if this service is tiled, extent will be modified to allow fetching tiles at appropriate zoom level.
        :param custom_renderers:
            A JSON string or dict containing renderer JSON objects indexed by layer id (WMS ID).
            Renderers should have correspond to visible layers, with a null renderer for unstyled layers.
        :param layer_defs:
            If no custom_renderers are provided, a single ESRI definition expression
            Otherwise, a JSON string or dict with keys corresponding to layer-specific definition expressions
        :param layers:
            A string with either "show:" or "hide:" preceding a comma-separated list of layer ids
        """

        image_params = {
            "dpi": 96,
            "transparent": True,
            "layers": layers or "",
            "layerdefs": layer_defs or "",
            "time": time or ""
        }
        image_params.update(kwargs)

        if custom_renderers is not None:
            # To style and filter at the same time we need to switch to using dynamic layers
            image_params["dynamicLayers"] = self._generate_dynamic_layers(custom_renderers, layer_defs, layers)
            image_params.pop("layerdefs")  # Dynamic layers take over for layerdefs: this saves URL space

        return self.generate_image_from_query(extent, width, height, "export", params=image_params)

    def _generate_dynamic_layers(self, custom_renderers, layer_defs, layers):
        layer_list = [int(x) for x in layers.split(":")[1].split(",")]

        renderers_from_json = isinstance(custom_renderers, str)
        if renderers_from_json:
            custom_renderers = json.loads(custom_renderers)

        layer_defs_from_json = isinstance(layer_defs, str)
        if layer_defs_from_json:
            layer_defs = json.loads(layer_defs)

        if "hide" not in layers:
            layer_map = {visible_id: layer_list[visible_id] for visible_id in layer_list}
        else:
            layer_map = self._get_layer_map(self.layers)
            for hidden_id in layer_list:
                layer_map.pop(hidden_id, None)

        dynamic_layers = []

        for layer_id in layer_map:
            dynamic_layer = {
                "id": layer_id,
                "source": {"type": "mapLayer", "mapLayerId": layer_id},
            }

            layer_id = str(layer_id) if renderers_from_json else int(layer_id)
            if layer_id in custom_renderers and custom_renderers[layer_id]:

                # Convert internally aliased renderer properties back to ESRI values
                renderer = to_renderer(custom_renderers[layer_id], from_camel=False).get_data()

                if renderer['type'] == 'classBreaks':
                    # Decrement classMaxValue to mimic support for "isMaxInclusive" in ClassBreaks JSON
                    for info in renderer['classBreakInfos']:
                        # Smaller numbers than this do not affect style
                        info['classMaxValue'] -= .000001

                dynamic_layer['drawingInfo'] = {'renderer': renderer}

            layer_id = str(layer_id) if layer_defs_from_json else int(layer_id)
            if layer_id in layer_defs:
                dynamic_layer["definitionExpression"] = layer_defs[layer_id]

            dynamic_layers.append(dynamic_layer)

        return json.dumps(dynamic_layers)

    def _get_layer_map(self, layer_list, layer_map=None):
        """ Recursive method for flattening nested layer dictionary into {order1: layer1, order2: layer2, ...} """

        if layer_map is None:
            layer_map = {}

        for item in layer_list:
            layer_map[int(item.id)] = item.name
            self._get_layer_map(getattr(item, "sub_layers", None) or [], layer_map)

        return layer_map


class GeometryServiceClient(object):
    """
    Class used to handle geometry processing requests against ArcGIS server.
    Intended for internal use, so no validation of URL, etc is performed.
    """

    def __init__(self, service_url):
        self.service_url = get_base_url(service_url, True)
        if self.service_url.endswith("/project"):
            self.service_url = self.service_url[:self.service_url.index("/project")]

    def project_extent(self, extent, to_spatial_ref):
        """
        Projects the extent of a dataset or layer to the projection described by to_spatial_ref.
        :param extent: an Extent object with a spatial_reference to project
        :param to_spatial_ref: the SpatialReference object describing the target projection
        :see: http://resources.esri.com/help/9.3/arcgisserver/apis/rest/project.html
        :return: a copy of extent with the new projection applied
        """

        if not isinstance(extent, Extent):
            extent = Extent(extent)
        if not isinstance(to_spatial_ref, SpatialReference):
            to_spatial_ref = SpatialReference(to_spatial_ref)

        temp_extent = extent.clone()
        temp_extent.spatial_reference = None

        # Project features described by geometries from one projection to another

        from_spatial_ref = extent.spatial_reference
        geometries = {
            "geometryType": "esriGeometryEnvelope",
            "geometries": [temp_extent.as_dict()]
        }

        url = f"{self.service_url}/project"
        headers = {"User-agent": DEFAULT_USER_AGENT}
        params = {
            "f": "json",
            "geometries": json.dumps(geometries),
            "inSR": from_spatial_ref.wkid or from_spatial_ref.as_json_string(),
            "outSR": to_spatial_ref.wkid or to_spatial_ref.as_json_string()
        }

        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
        except requests.exceptions.HTTPError as ex:
            raise HTTPError(
                "The ArcGIS geometry service did not respond correctly",
                params=params, status_code=response.status_code, underlying=ex, url=url
            )

        try:
            extent = response.json()["geometries"]
            extent = extent if isinstance(extent, dict) else extent[0]
            extent["spatialReference"] = to_spatial_ref.as_dict()
            return Extent(extent)
        except KeyError as ex:
            raise ContentError(
                "Invalid content from ArcGIS geometry service",
                params=params, underlying=ex, url=url
            )
        except ValueError as ex:
            extent = dict(geometries["geometries"][0])
            extent["spatial_reference"] = to_spatial_ref.as_dict()
            raise BadExtent(
                "Error processing response from ArcGIS geometry service",
                extent=extent, underlying=ex, url=url
            )


TIME_SUMMARY_RENDERER = to_renderer(setdefaults({}, {
    "description": "",
    "label": "",
    "type": "simple",
    "symbol.style": "esriSMSCircle",
    "symbol.angle": 0,
    "symbol.color": [0, 0, 128, 255],
    "symbol.size": 9,
    "symbol.type": "esriSMS",
    "symbol.xoffset": 0,
    "symbol.yoffset": 0,
    "symbol.outline.color": [0, 0, 128, 255],
    "symbol.outline.style": "esriSLSSolid",
    "symbol.outline.type": "esriSLS",
    "symbol.outline.width": 1.5
}))


class FeatureLayerResource(ArcGISLayerResource):
    """ Compatible with ArcGIS feature layer resources >= version 10.1 """

    max_feature_request = MAX_FEATURE_REQUEST

    global_id_field = TextField(required=False)
    object_id_field = TextField(required=False)
    effective_min_scale = NumberField(required=False)
    effective_max_scale = NumberField(required=False)
    has_static_data = BooleanField(default=False)
    has_m = BooleanField(default=False)
    has_z = BooleanField(default=False)
    enable_z_defaults = BooleanField(default=False)
    z_default = NumberField(required=False)
    allow_geometry_updates = BooleanField(default=False)
    html_popup_type = TextField(required=False)
    time_interval = IntegerField(required=False)
    time_interval_units = TextField(required=False)
    templates = ObjectField(class_name="Template", required=False)
    types = ObjectField(class_name="Type", required=False)

    query = FEATURE_LAYER_QUERY
    time_query = FEATURE_LAYER_TIME_QUERY

    class Meta:
        case_sensitive_fields = False
        get_parameters = {"f": "json"}
        match_fuzzy_keys = True

    def get_image(self, extent, width, height, custom_renderers=None, layer_defs=None, time="", **kwargs):
        """
        :param custom_renderers:
            A JSON string or dict containing renderer JSON objects indexed by layer id (WMS ID).
        :param layer_defs:
            A JSON string or dict with indices corresponding to the feature layer definition expression:
        :param kwargs:
            May contain an ArcGIS token as "token" for secure feature layer image requests
        """

        if isinstance(custom_renderers, str):
            renderer = to_renderer(json.loads(custom_renderers)[str(self.id)])
        elif isinstance(custom_renderers, dict):
            renderer = to_renderer(custom_renderers[self.id])
        else:
            renderer = self.drawing_info.renderer

        if isinstance(layer_defs, str):
            layer_def = json.loads(layer_defs).get(str(self.id))
        elif isinstance(layer_defs, dict):
            layer_def = layer_defs.get(self.id)
        else:
            layer_def = None

        # Break up very large result sets by querying just the IDs of matching features

        query_kwargs = {k: v for k, v in kwargs.items() if k in FEATURE_LAYER_PARAMS}
        if any(k not in query_kwargs for k in kwargs):
            extras = ", ".join(k for k in kwargs if k not in query_kwargs)
            logger.warning(f"Ignoring {self.client_name} query fields: {extras}")

        id_query = self.query(
            where=layer_def or "",
            time=time or "",
            geometry=extent.as_json_string(),
            geometry_type="esriGeometryEnvelope",
            return_ids_only=True,
            **query_kwargs
        )
        if "error" in id_query:
            self.handle_error(
                id_query,
                message="The ArcGIS feature service did not return a valid image",
                error_class=ImageError
            )

        transparent_background = (0, 0, 0, 0)
        object_ids = id_query["objectIds"]
        full_image = Image.new("RGBA", (width, height), transparent_background)
        starting_record = 0

        # Override max_record_count for services with too many features to reproject
        max_features = self.max_feature_request or self.max_record_count
        max_features = min(self.max_record_count, max_features)

        while True:
            object_ids_to_get = object_ids[starting_record:starting_record + max_features]
            if not object_ids_to_get:
                break

            # Specific criteria for geometries has already been applied in the query for IDs
            id_where_clause = "{object_field} IN {formatted_id_list}".format(
                object_field=id_query["objectIdFieldName"],
                formatted_id_list=json.dumps(object_ids_to_get).replace("[", "(").replace("]", ")")
            )
            query_results = self.query(where=id_where_clause, out_sr=3857, out_fields="*", **query_kwargs)

            if "error" in query_results:
                self.handle_error(
                    query_results,
                    message="The ArcGIS feature layer did not return a valid image",
                    error_class=ImageError
                )

            # Generate the sub-images for each subset query and overlay it on the current image
            sub_image = self.generate_sub_image(extent, width, height, renderer, query_results)
            full_image = overlay_images([full_image, sub_image], background_color=transparent_background)

            starting_record += max_features

        return full_image

    def get_time_image(self, extent, width, height, **kwargs):
        query_kwargs = {k: v for k, v in kwargs.items() if k in FEATURE_LAYER_TIME_PARAMS}
        if any(k not in query_kwargs for k in kwargs):
            extras = ", ".join(k for k in kwargs if k not in query_kwargs)
            logger.warning(f"Ignoring {self.client_name} query fields: {extras}")

        return self.generate_sub_image(
            extent, width, height, TIME_SUMMARY_RENDERER, self.time_query(**query_kwargs)
        )

    def generate_sub_image(self, extent, width, height, renderer, query_results):
        """
        :param renderer:
            A renderer object as defined by clients.utils.conversion.to_renderer
        :param query_results:
            An executed query as defined by clients.query.actions.QueryAction
        """
        class_name = type(self).__name__
        raise NotImplementedError(f"{class_name}.generate_sub_image")


class FeatureServerResource(ArcGISServerResource):
    """ Compatible with ArcGIS feature service resources >= version 10.1 """

    max_record_count = IntegerField()  # Overridden to require

    units = TextField()
    has_static_data = BooleanField(default=False)
    has_versioned_data = BooleanField(default=False)
    allow_geometry_updates = BooleanField(default=False)
    editor_tracking_info = ObjectField(class_name="EditorTrackingInfo", required=False)
    enable_z_defaults = BooleanField(default=False)
    z_default = NumberField(required=False)
    supports_disconnected_editing = BooleanField(default=False)
    sync_enabled = BooleanField(default=False)
    sync_capabilities = ObjectField(class_name="SyncCapabilities", required=False)

    layers = ToManyField(FeatureLayerResource, "partial", id_field="id", relative_path="{id}")

    query = FEATURE_SERVER_QUERY

    class Meta:
        case_sensitive_fields = False
        get_parameters = {"f": "json"}
        match_fuzzy_keys = True

    def populate_field_values(self, data):
        """ Overridden to validate layers """

        super(FeatureServerResource, self).populate_field_values(data)

        if not self.layers:
            raise NoLayers("The ArcGIS feature service does not have any layers", url=self._url)

    def get_image(self, extent, width, height, custom_renderers=None, layer_defs=None, **kwargs):
        final_image = Image.new("RGBA", (width, height), (0, 0, 0, 0))

        if self._token:
            kwargs["token"] = self._token

        for layer in self.layers:
            final_image.paste(layer.get_image(extent, width, height, custom_renderers, layer_defs, **kwargs))

        return final_image


class ImageServerResource(ArcGISTiledImageResource):
    """ Compatible with ArcGIS image server resources >= version 10.1 """

    id = IntegerField(default=0)  # When treated as a single layer, this is layer order
    name = TextField()

    allowed_mosaic_methods = CommaSeparatedField(required=False)
    allow_raster_function = BooleanField(default=False)
    band_count = IntegerField()
    default_resampling_method = TextField(required=False)

    fields = ObjectField(class_name="Field", required=False)
    edit_fields_info = ObjectField(class_name="EditFieldsInfo", required=False)

    extent = ExtentField(required=False)
    spatial_reference = SpatialReferenceField(required=False)  # Overridden not to require
    has_color_map = BooleanField(default=False)
    has_histograms = BooleanField(default=False)
    has_multi_dimensions = BooleanField(default=False)
    has_raster_attribute_table = BooleanField(default=False)

    max_values = ObjectField(class_name="ValuesList")
    mean_values = ObjectField(class_name="ValuesList")
    min_values = ObjectField(class_name="ValuesList")

    object_id_field = TextField(required=False)
    ownership_based_access_control_for_rasters = ObjectField(class_name="AccessControlForRasters", required=False)

    pixel_size_x = NumberField()
    pixel_size_y = NumberField()
    pixel_type = TextField()

    service_data_type = TextField(required=False)
    standard_variation_values = ObjectField(name="stdvValues", class_name="ValuesList")
    supports_statistics = BooleanField(default=False)
    supports_advanced_queries = BooleanField(default=False)

    class Meta:
        case_sensitive_fields = False
        get_parameters = {"f": "json"}
        match_fuzzy_keys = True

    def get_image(self, extent, width, height, **kwargs):
        """ Note: if tiled, extent will be modified to allow fetching tiles at appropriate zoom level """

        image_params = {
            "pixelType": self.pixel_type,
            "time": ",".join(str(i) for i in self.get_time_info_prop("time_extent", []))
        }
        image_params.update(kwargs)

        return self.generate_image_from_query(extent, width, height, "exportImage", params=image_params)
