"""
WMS Client (only supports 1.1.1 and 1.3.0 now)

WMS Notes: layer may have BoundingBox, LatLonBoundingBox, or both (or worst case, neither).
    Only has LatLonBoundingBox for some layers:
    http://nowcoast.noaa.gov/wms/com.esri.wms.Esrimap/obs?service=wms&version=1.1.1&request=GetCapabilities

    Has bboxes only for one parent layer, and that's it (default to global extent??):
    http://neowms.sci.gsfc.nasa.gov/wms/wms?version=1.1.1&service=WMS&request=GetCapabilities

layer may have sublayers (extent may be defined at parent layer level).
"""

import requests

from PIL import Image
from io import BytesIO

from parserutils.collections import setdefaults, wrap_value
from parserutils.urls import has_trailing_slash, update_url_params, url_to_parts, parts_to_url
from restle.fields import TextField, BooleanField, IntegerField

from .exceptions import BadExtent, ClientError, HTTPError, ImageError
from .exceptions import MissingFields, NoLayers, ServiceError, ValidationError
from .query.fields import DictField, ExtentField, ListField, SpatialReferenceField
from .query.serializers import XMLToJSONSerializer
from .resources import ClientResource
from .utils.geometry import Extent, union_extent
from .utils.images import make_color_transparent


WMS_KNOWN_VERSIONS = ("1.1.1", "1.3.0")
WMS_DEFAULT_PARAMS = {
    "version": WMS_KNOWN_VERSIONS[1],  # Default to maximum
    "service": "WMS",
    "request": "GetCapabilities"
}
WMS_EXCEPTION_FORMAT = "application/vnd.ogc.se_xml"
WMS_SRS_DEFAULT = "EPSG:3857"


class NcWMSLayerResource(ClientResource):

    default_spatial_ref = "EPSG:4326"

    # Pulled from layer list or metadata query

    id = TextField()
    title = TextField(required=False)
    description = TextField(required=False)
    credits = TextField(required=False)
    layer_order = IntegerField(default=0)
    units = TextField(required=False)
    version = TextField()
    wms_version = TextField()

    # Pulled from layer details query

    copyright_text = TextField(name="copyright")
    more_info = TextField()
    full_extent = ExtentField(name="bbox")

    num_color_bands = IntegerField()
    log_scaling = BooleanField()
    scale_range = ListField()

    default_palette = TextField()
    palettes = ListField()
    supported_styles = ListField(default=["boxfill"])

    # Derived properties

    default_style = TextField(required=False)
    dimensions = DictField(required=False)
    legend_info = DictField(required=False)
    styles = ListField(default=[])

    is_ncwms = True

    class Meta:
        case_sensitive_fields = False
        match_fuzzy_keys = True

    def _get(self, url, color_map=None, layer_data=None, **kwargs):
        """ Overridden to capture data known only to the parent NcWMSLayerResource """

        super(NcWMSLayerResource, self)._get(url, **kwargs)

        self._color_map = color_map or {}
        self._layer_data = layer_data or {}

    def populate_field_values(self, data):
        """ Overridden to include data from parent NcWMSLayerResource """

        data.update({k: v for k, v in self._layer_data.items() if v or k not in data})

        super(NcWMSLayerResource, self).populate_field_values(data)

        if "boxfill" not in self.supported_styles:
            raise ValidationError(
                message=f"Layer {self.title} does not support boxfill style",
                styles=self.supported_styles,
                url=self._url
            )

        self.full_extent = self.full_extent.project_to_web_mercator()
        self.default_style = "boxfill/{}".format(self.default_palette.lower())

        self.legend_info = {
            "colorBands": self.num_color_bands,
            "scaleRange": self.scale_range,
            "logScaling": self.log_scaling,
            "legendUnits": self.units or ""
        }

        legend_params = {
            # May add WIDTH and HEIGHT on the front-end
            "request": "GetLegendGraphic",
            "layer": self.id,
            "colorbaronly": bool(self.num_color_bands)
        }

        for palette in (p.lower() for p in self.palettes):
            style = f"boxfill/{palette}"
            color = self._color_map.get(palette, {})

            self.styles.append({
                "id": style,
                "title": color.get("name", palette),
                "abstract": None,
                "colors": color.get("colors"),
                "legendURL": update_url_params(self._url, palette=palette, **legend_params)
            })

        self.styles = sorted(self.styles, key=lambda s: s["title"].lower())


class WMSLayerResource(ClientResource):

    default_spatial_ref = "EPSG:4326"

    id = TextField(name="name", required=False)  # Empty for parent layers
    title = TextField(name="title")
    version = TextField()
    description = TextField(name="abstract", required=False)
    supports_query = BooleanField(name="queryable", default=False)

    _attribution = DictField(default={})
    _dimension = DictField(default=[], aliases={"value": "values"})
    _extent = DictField(required=False, aliases={"value": "values"})
    _metadata_url = DictField(name="MetadataURL", default=[])
    _style = DictField(default={}, aliases={"Name": "id"})

    _geographic_extent = ExtentField(name="EX_GeographicBoundingBox", required=False, aliases={
        "southBoundLatitude": "ymin",
        "eastBoundLongitude": "xmax",
        "northBoundLatitude": "ymax",
        "westBoundLongitude": "xmin"
    })
    _old_bbox_extent = ExtentField(name="BoundingBox", required=False, aliases={
        "minx": "xmin",
        "miny": "ymin",
        "maxx": "xmax",
        "maxy": "ymax",
        "CRS": "spatial_reference",
        "SRS": "spatial_reference"
    })
    _old_latlon_extent = ExtentField(name="LatLonBoundingBox", required=False, aliases={
        "minx": "xmin",
        "miny": "ymin",
        "maxx": "xmax",
        "maxy": "ymax"
    })

    _spatial_refs = ListField(name="SRS", default=[])
    _coordinate_refs = ListField(name="CRS", default=[])

    # Derived properties

    has_time = BooleanField(default=False)
    has_dimensions = BooleanField(default=False)
    is_ncwms = BooleanField(default=False)
    is_old_version = BooleanField(name="old_version", default=False)
    layer_order = IntegerField(name="order", required=False)
    parent_order = IntegerField(name="group", required=False)

    attribution = DictField(default={})
    dimensions = DictField(default={})
    full_extent = ExtentField(required=False)
    metadata_urls = DictField(required=False)
    styles = ListField(required=False)
    supported_spatial_refs = ListField(required=False)

    # Optional NcWMS properties

    credits = TextField(required=False)
    copyright_text = TextField(required=False)
    more_info = TextField(required=False)

    num_color_bands = IntegerField(default=0)
    log_scaling = BooleanField(default=False)
    scale_range = ListField(default=[])
    legend_info = DictField(default={})
    units = TextField(required=False)

    default_style = TextField(required=False)
    default_palette = TextField(required=False)
    palettes = ListField(default=[])
    supported_styles = ListField(default=["boxfill"])

    class Meta:
        case_sensitive_fields = False
        match_fuzzy_keys = True

    def __init__(self, color_map=None, **kwargs):
        """ Overridden to pass a styles color map to NcWMSLayerResource"""

        super(WMSLayerResource, self).__init__(**kwargs)
        self._color_map = color_map or {}

    @classmethod
    def get(cls, url, **kwargs):
        raise NotImplementedError("WMSLayerResource cannot be fetched, only populated")

    def populate_field_values(self, data):
        """ Overridden to recursively populate layers """

        self.wms = data.pop("wms")
        self.parent = data.pop("parent", None)

        self._url = self.wms.wms_url
        self._behind_proxy = self.wms._behind_proxy

        self._ncwms_layer_url = update_url_params(self._url, **{
            "request": "GetMetadata",
            "item": "layerDetails",
            "layerName": "{layer_id}"
        })

        self.child_layers = []
        self.leaf_layers = {}

        data["old_version"] = (data["version"] == self.wms.supported_versions[0])
        data["queryable"] = (data.get("queryable", "").lower() in {"1", "true"})
        data["is_ncwms"] = self.wms._is_ncwms

        super(WMSLayerResource, self).populate_field_values(data)

        # No parent/child layer dependencies
        self._populate_dimensions()
        self._populate_metadata_urls()

        self.has_dimensions = bool(self.dimensions)
        self.has_time = "time" in self.dimensions

        # Must populate before child layers (depend on self.parent)
        self._populate_attribution()
        self._populate_extent()
        self._populate_styles()
        self._populate_spatial_refs()

        self._populate_child_layers(data)

        # Must populate after child layers (depends on self.child_layers)
        if self.is_ncwms:
            self._populate_ncwms_names()

    def _populate_child_layers(self, data):
        """ Recurse and instantiate children with nested Layer data """

        for layer in wrap_value(data.get("Layer", [])):
            layer["wms"] = self.wms
            layer["parent"] = self
            layer["version"] = data["version"]

            wms_layer = WMSLayerResource(
                session=(self._layer_session or self._session),
                color_map=self._color_map
            )
            wms_layer.populate_field_values(layer)
            self.child_layers.append(wms_layer)
            self.full_extent = union_extent((self.full_extent, wms_layer.full_extent))

            if wms_layer.id and not wms_layer.child_layers:
                self.leaf_layers[wms_layer.id] = wms_layer

        if self.parent:
            self.parent.leaf_layers.update(self.leaf_layers)

    def _populate_attribution(self):

        if not self._attribution:
            self.attribution.update(getattr(self.parent, "attribution", {}))

        elif self._attribution.get("title"):
            self.attribution = {
                "title": self._attribution["title"],
                "href": (self._attribution.get("online_resource") or {}).get("href")
            }

    def _populate_dimensions(self):
        if not self._dimension:
            return

        for dim in wrap_value(self._dimension):
            obj = dict(self._extent or dim)

            if dim.get("name") and dim.get("units") and obj.get("values"):
                obj["units"] = dim["units"]
                obj["default"] = obj.get("default")
                obj["values"] = obj["values"].strip().split(",") or None

                self.dimensions[dim["name"]] = obj

    def _populate_extent(self):
        """ Extract original extent - caller must limit to globe and project """

        if self._geographic_extent:
            extent = self._geographic_extent
        elif self._old_latlon_extent:
            extent = self._old_latlon_extent
        elif self._old_bbox_extent:
            extent = self._old_bbox_extent
            extent = extent if isinstance(extent, Extent) else extent[0]
        else:
            extent = getattr(self.parent, "full_extent", None)

        if self.id and not extent:
            # Leaf layer missing extent as EX_GeographicBoundingBox, LatLonBoundingBox, or BoundingBox
            raise MissingFields(f'Extent required for WMS layer "{self.id}"', missing="extent", url=self._url)
        elif extent:
            try:
                # Standardize across layers; they may be in different projections
                self.full_extent = extent.project_to_web_mercator()
            except ValueError as ex:
                raise BadExtent(
                    f'Error reprojecting extent for WMS layer "{self.id}"',
                    extent=self.full_extent, underlying=ex, url=self._url
                )

    def _populate_metadata_urls(self):

        parsed = wrap_value(self._metadata_url)

        self.metadata_urls = {
            md["metadata_url_type"]: md["online_resource"]["href"]
            for md in parsed if md.get("metadata_url_type") and (md.get("online_resource") or {}).get("href")
        }

    def _populate_ncwms_names(self):
        """ For NcWMS layers, group names are sometimes non-informative: use IDs to fill out the title """

        def append_fragment(title, fragment):
            if fragment.lower().startswith(title.lower()):
                fragment = fragment[len(title):].strip("_")
            if fragment not in title:
                title += f" ({fragment})"
            return title.replace("_", " ")

        if self.id and self.id.count("/") and not self.child_layers:
            self.title = append_fragment(self.title, self.id.split("/")[1])
        elif self.child_layers:
            first_child_layer = self.child_layers[0]
            if "/" in (first_child_layer.id or "") and not first_child_layer.child_layers:
                self.title = append_fragment(self.title, first_child_layer.id.split("/")[0])

    def _populate_styles(self):

        self.styles = list(self.parent.styles) if self.parent else []

        for style in wrap_value(self._style):
            if not style.get("id"):
                continue

            style = setdefaults(style, "legend_url.online_resource.href")
            legend_url = style["legend_url"]["online_resource"]["href"]

            if self._behind_proxy:
                # Legend URL may be internal, which won't work if service is behind a proxy: apply proxy to legend URL
                legend_url = update_url_params(self._url, **url_to_parts(legend_url).query)

            self.styles.append({
                "id": style["id"],
                "title": style.get("title", style["id"]),
                "abstract": style.get("abstract"),
                "legendURL": legend_url
            })

    def _populate_spatial_refs(self):

        supported_spatial_refs = set(getattr(self.parent, "supported_spatial_refs", ""))  # SRS is inherited
        supported_spatial_refs.update(sr.strip() for sr in self._spatial_refs)
        supported_spatial_refs.update(cr.strip() for cr in self._coordinate_refs)

        self.supported_spatial_refs = sorted(supported_spatial_refs)

    def _populate_ordered_layers(self, ordered_layers):
        """ Sets a unique layer order for all layers and a common parent order for nested sibling layers """

        self.layer_order = len(ordered_layers)
        self.parent_order = self.parent.layer_order
        ordered_layers.append(self)

        if self.child_layers:
            # Recurse until we reach a leaf layer

            child_layers = list(self.child_layers)
            child_layers.reverse()

            for child in child_layers:
                child._populate_ordered_layers(ordered_layers)

        elif self.is_ncwms:
            # Attempt to query the NcWMS layer endpoint for more data

            layer_url = self._ncwms_layer_url.format(layer_id=self.id)
            layer_data = {
                "id": self.id,
                "title": self.id,
                "description": self.title,
                "layer_order": self.layer_order,
                "version": self.version,
                "wms_version": self.version
            }

            try:
                ncwms_layer = NcWMSLayerResource.get(
                    layer_url,
                    lazy=False,
                    color_map=self._color_map,
                    layer_data=layer_data,
                    session=(self._layer_session or self._session)
                )
            except ClientError:
                pass  # No NcWMS data to query
            else:
                self.credits = ncwms_layer.credits
                self.copyright_text = ncwms_layer.copyright_text
                self.more_info = ncwms_layer.more_info

                self.num_color_bands = ncwms_layer.num_color_bands
                self.log_scaling = ncwms_layer.log_scaling
                self.scale_range = ncwms_layer.scale_range
                self.legend_info = ncwms_layer.legend_info
                self.units = ncwms_layer.units

                self.default_style = ncwms_layer.default_style
                self.default_palette = ncwms_layer.default_palette
                self.palettes = ncwms_layer.palettes
                self.supported_styles = ncwms_layer.supported_styles
                self.styles = ncwms_layer.styles


class WMSResource(ClientResource):

    default_spatial_ref = WMS_SRS_DEFAULT
    incoming_casing = "pascal"
    styles_color_map = None

    title = TextField()
    description = TextField(name="abstract")
    access_constraints = TextField(required=False)
    version = TextField()

    feature_info_formats = ListField(default=[])
    map_formats = ListField(default=[])
    keywords = ListField(required=False)
    layer_drawing_limit = IntegerField(required=False)

    full_extent = ExtentField()
    has_dimensions = BooleanField(default=False)
    has_time = BooleanField(default=False)
    is_ncwms = BooleanField(default=False)
    supported_spatial_refs = ListField(required=False)
    spatial_ref = SpatialReferenceField(required=False)

    supported_versions = WMS_KNOWN_VERSIONS

    _wms_url = None

    class Meta:
        case_sensitive_fields = False
        match_fuzzy_keys = True

        deserializer = XMLToJSONSerializer
        get_parameters = WMS_DEFAULT_PARAMS

    @property
    def wms_url(self):
        """ Preserves required or custom WMS parameters through resource load cycle """

        if not self._wms_url:
            default_params = self._meta.get_parameters.copy()
            service_params = {k: v for k, v in self._params.items() if k not in default_params}
            self._wms_url = update_url_params(self._url, replace_all=True, **service_params)

        return self._wms_url

    @classmethod
    def get(cls, url, **kwargs):
        """ Overridden to parse the URL in case it includes the GetCapabilities request """

        parts = url_to_parts(url)

        # Must be list, not generator, or will be updating dict during iteration
        for param in [p for p in parts.query if p.lower() in WMS_DEFAULT_PARAMS]:
            parts.query.pop(param)

        return super(WMSResource, cls).get(
            parts_to_url(parts, trailing_slash=has_trailing_slash(url)), **kwargs
        )

    def _get(self, url, spatial_ref=None, styles_color_map=None, token=None, token_id="token", version=None, **kwargs):
        """ Overridden to do some initialization and capture version and target coordinate reference """

        super(WMSResource, self)._get(url, **kwargs)

        self._behind_proxy = self._url.rfind("http://") > 0 or self._url.rfind("https://") > 0

        # Note: if NcWMS, initial request may take a VERY long time
        # URL is trimmed of any query parameters at this point, so endswith is valid
        self._is_ncwms = ("ncwms" in self._url.lower() or self._url.endswith(".nc"))
        self._ordered_layers = []  # Populated before resource is loaded, or anytime afterwards if self._lazy

        self._spatial_ref = spatial_ref or self.default_spatial_ref
        self.styles_color_map = styles_color_map or {}

        self._token = token
        self._token_id = token_id
        if token is not None:
            self._params[token_id] = token

        self.wms_credentials = {"token_id": self._token_id, self._token_id: self._token}

        self._params["version"] = version or WMS_KNOWN_VERSIONS[-1]

        # Populated before resource is loaded: must not be implemented as field definitions
        self.leaf_layers = {}
        self.root_layers = []

    def _load_resource(self, as_unicode=False):
        """ Overridden to query XML as ASCII the first time: prevents unicode errors and duplicate requests """

        super(WMSResource, self)._load_resource(as_unicode)  # Default to False to ensure one attempt

    def populate_field_values(self, data):
        """ Overridden to validate root fields and flatten converted WMS data """

        if "ServiceException" in data:
            raise ServiceError(data["ServiceException"], url=self.wms_url)
        else:
            self.validate_version(data["version"])

        service = data["Service"]
        title = service["Title"] or ""

        wms_data = {
            "version": data["version"],
            "title": title,
            "abstract": service["Abstract"],
            "keywords": (service.get("KeywordList") or {}).get("Keyword"),
            "access_constraints": service.get("AccessConstraints") or "",
            # The max number of layers that can be rendered at once
            "layer_drawing_limit": int(service.get("LayerLimit") or 0) or None,
            "is_ncwms": self._is_ncwms
        }

        access_constraints = wms_data["access_constraints"]
        if not access_constraints or access_constraints.strip().lower() == "none":
            wms_data["access_constraints"] = None

        # Process capability request fields

        capabilities = data["Capability"]
        request = capabilities["Request"]

        wms_data["map_formats"] = (request.get("GetMap") or {}).get("Format")
        wms_data["feature_info_formats"] = (request.get("GetFeatureInfo") or {}).get("Format")

        # Process nested layers: will not be processed as JSON by Resource

        for layer in wrap_value(capabilities.get("Layer", [])):
            layer["wms"] = self
            layer["version"] = wms_data["version"]

            wms_layer = WMSLayerResource(
                color_map=self.styles_color_map,
                session=(self._layer_session or self._session)
            )
            wms_layer.populate_field_values(layer)

            self.root_layers.append(wms_layer)
            self.leaf_layers.update(wms_layer.leaf_layers)

        if len(self.root_layers) == 1 and self.root_layers[0].child_layers:
            # If only a single root, parent layer it is equivalent to the dataset itself
            self.root_layers = self.root_layers[0].child_layers

        if not self.leaf_layers:
            raise NoLayers("The WMS service does not have any layers", url=self.wms_url)
        elif not self._lazy:
            self._populate_ordered_layers()  # Process ordered layers after nested structure is loaded

        # Prepare layer dependent data

        # Union of all leaf layer extents in Web Mercator (root layers recursively union leafs)
        wms_data["full_extent"] = union_extent(l.full_extent for l in self.root_layers).as_dict()

        time_for_dimensions = [l.has_time for l in self.leaf_layers.values() if l.has_dimensions]
        wms_data["has_dimensions"] = bool(time_for_dimensions)
        wms_data["has_time"] = any(time_for_dimensions)

        # Validate spatial references: must support a variant of Web Mercator to call get_image

        supported_spatial_refs = {srs for l in self.leaf_layers.values() for srs in l.supported_spatial_refs}
        wms_data["supported_spatial_refs"] = sorted(supported_spatial_refs)

        # Ensure EPSG:3857 is at front of list of supported projections
        web_mercator_srs = {"EPSG:3857", "EPSG:3785", "EPSG:900913", "EPSG:102113"}
        web_mercator_srs = sorted(web_mercator_srs.intersection(supported_spatial_refs))

        if self._spatial_ref in web_mercator_srs:
            wms_data["spatial_ref"] = self._spatial_ref
        elif web_mercator_srs:
            wms_data["spatial_ref"] = web_mercator_srs[0]

        # Populate fields with coerced, non-layer data (layers are nested to represent parent/child relationships)

        super(WMSResource, self).populate_field_values(wms_data)

    def _populate_ordered_layers(self):
        """ Must be called after root layers and complete nested layer structure have been loaded """

        reversed_layers = list(self.root_layers)
        reversed_layers.reverse()

        for root_layer in reversed_layers:
            root_layer._populate_ordered_layers(self._ordered_layers)

    def get_image(
        self, extent, width, height,
        layer_ids=None, style_ids=None, time_range=None, params=None, image_format="png"
    ):
        """
        Note: extent aspect ratio must align correctly with image aspect ratio, or this will be warped incorrectly.
        Extent must be in Web Mercator. The caller of this function is expected to pass in valid values.
        Also note: the first layer is the lowest layer in stack, all others render on top
        """

        if not isinstance(extent, Extent):
            spatial_ref = getattr(extent, "spatial_reference", None) or self.spatial_ref
            extent = Extent(extent, spatial_reference=spatial_ref)

        if self.spatial_ref is None:
            supported_srs = ",".join(self.supported_spatial_refs)
            image_error = f"Invalid coordinate system identifier (Web Mercator required): {supported_srs}"
            raise ImageError(image_error, url=self.wms_url)

        elif not layer_ids:
            raise ImageError("No layers from which to generate an image", url=self.wms_url)

        elif style_ids and len(layer_ids) != len(style_ids):
            raise ImageError("Provided styles do not correspond to specified Layers", url=self.wms_url)

        elif not any(f.startswith(f"image/{image_format}") for f in self.map_formats):
            image_error = "Incompatible image format {0}: {1}".format(image_format, ",".join(self.map_formats))
            raise ImageError(image_error, url=self.wms_url)

        elif not extent.crosses_anti_meridian():
            return self.generate_image_from_query(
                extent, width, height, layer_ids, style_ids, time_range, params, image_format
            )

        # Edge case: mapserver renders badly any global extent raster data that straddles the -180/180 line
        # Note: this needs to be done carefully or layer will not overlay properly with base layers
        # (meaning all we should be adjusting here is the width, NOT height)

        new_extent = extent.limit_to_global_width()
        resolution = extent.get_image_resolution(width, height)
        left_side_adjust = int(round((new_extent.xmin - extent.xmin) / resolution, 0))
        img_width, img_height = new_extent.fit_image_dimensions_to_extent(width, height, resolution)

        img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        wms_img = self.generate_image_from_query(
            new_extent, img_width, img_height, layer_ids, style_ids, time_range, params, image_format
        )
        img.paste(wms_img, (left_side_adjust, 0, left_side_adjust + img_width, img_height), wms_img)

        # Request other side of meridian, if part of the extent
        if extent.has_negative_extent():
            neg_extent = extent.get_negative_extent()
            img_width, img_height = neg_extent.fit_image_dimensions_to_extent(width, height, resolution)
            negative_image = self.generate_image_from_query(
                neg_extent, img_width, img_height, layer_ids, style_ids, time_range, params, image_format
            )
            img.paste(negative_image, (0, 0), negative_image)

        return img

    def generate_image_from_query(self, extent, width, height, layer_ids, style_ids, time_range, params, image_format):

        if not image_format.startswith("image/"):
            image_format = f"image/{image_format}"

        try:
            image_params = {
                # Constants
                "service": "WMS",
                "request": "GetMap",
                "transparent": "TRUE",
                # Variables
                "format": image_format,
                "width": width,
                "height": height,
                "bbox": extent.as_bbox_string(),
                "layers": ",".join(wrap_value(layer_ids)),
                "styles": ",".join(wrap_value(style_ids)),
                "version": (params or {}).get("version") or self.version
            }
            if self._token:
                image_params[self._token_id] = self._token

            if image_params["version"] == WMS_KNOWN_VERSIONS[1]:
                image_params["exceptions"] = "XML"
                image_params["crs"] = extent.spatial_reference.srs
            else:
                image_params["exceptions"] = WMS_EXCEPTION_FORMAT
                image_params["srs"] = extent.spatial_reference.srs

            if time_range:
                # Unclear in docs if time and custom params require ordering to match layer
                image_params["time"] = time_range

            if params:
                # Update from params last in order to override any of the above
                image_params.update(params)

            response = self._make_request(self.wms_url, image_params, timeout=120)
            response_type = response.headers["content-type"]

            if response_type != image_format:
                if WMS_EXCEPTION_FORMAT not in response_type:
                    error = f"Unexpected image format {response_type}: {image_format}\n\t{response.text}"
                else:
                    error = XMLToJSONSerializer.to_dict(response.content).get(
                        "ServiceException", "No service exception"
                    )
                raise ImageError(error, params=image_params, underlying=response.text, url=response.url)

            img = Image.open(BytesIO(response.content))
            fix_transparency = False
            if img.mode == "RGB" and img.info["transparency"]:  # PIL does not always correctly detect PNG transparency
                fix_transparency = True

            img = img.convert("RGBA")
            if fix_transparency:
                r, g, b = img.info["transparency"]
                replace_color = (r, g, b, 255)
                make_color_transparent(img, replace_color)

            return img

        except requests.exceptions.HTTPError as ex:
            raise HTTPError(
                "The WMS service image query did not respond correctly",
                params=image_params, underlying=ex, url=self.wms_url
            )
        except (IOError, ValueError) as ex:
            raise ImageError(
                "The WMS service did not return a valid image",
                params=image_params, underlying=ex, url=self.wms_url
            )

    @property
    def ordered_layers(self):
        """ :return: flattened ordered list of nested layers, but lazily if self._lazy """

        if self._ordered_layers:
            return self._ordered_layers

        elif not self._populated_field_values:
            self._load_resource()

        elif self._lazy:
            self._populate_ordered_layers()

        return self.ordered_layers  # Now that they are populated
