import logging
import requests

from PIL import Image
from collections import defaultdict
from io import BytesIO

from gis_metadata.iso_metadata_parser import IsoParser
from gis_metadata.utils import format_xpaths, ParserProperty
from parserutils.collections import reduce_value, wrap_value
from parserutils.elements import get_remote_element
from parserutils.urls import has_trailing_slash, url_to_parts, parts_to_url
from restle.fields import TextField
from restle.serializers import JSONSerializer

from .exceptions import HTTPError, ImageError, ValidationError
from .query.fields import DictField, ExtentField, ListField
from .query.serializers import XMLToJSONSerializer
from .resources import ClientResource
from .utils.geometry import Extent, SpatialReference, union_extent
from .utils.images import make_color_transparent
from .wms import NcWMSLayerResource
from .wms import WMS_DEFAULT_PARAMS, WMS_EXCEPTION_FORMAT, WMS_KNOWN_VERSIONS, WMS_SRS_DEFAULT


logger = logging.getLogger(__name__)

RELATED_ENDPOINT_FIELDS = (
    "access_constraints", "credits", "description", "keywords", "layers"
)


class ThreddsResource(ClientResource):

    default_spatial_ref = WMS_SRS_DEFAULT
    styles_color_map = None

    # Base service fields

    id = TextField()
    title = TextField(name="name")
    credits = TextField(name="authority")
    version = TextField()

    # Hard-coded base field values

    feature_info_formats = ["image/png", "text/xml"]
    layer_drawing_limit = 1

    # Derived from service fields

    data_size = TextField()
    data_format = TextField()
    data_type = TextField()
    download_url = TextField(required=False)
    modified_date = TextField(name="modified")

    _services = DictField()

    # Derived from layer and metadata fields

    access_constraints = TextField(required=False)
    description = TextField(required=False)
    full_extent = ExtentField(required=False)
    keywords = ListField(default=[])
    spatial_resolution = TextField(required=False)

    layers = ListField(default=[])
    styles = ListField(default=[])

    # Private URL fields

    _wms_url = None
    _layers_url = None
    _layers_url_format = None
    _metadata_url = None

    class Meta:
        case_sensitive_fields = False
        match_fuzzy_keys = True
        deserializer = XMLToJSONSerializer

    @classmethod
    def to_wms_url(cls, thredds_url):
        """ Helper to generate WMS service URL from a THREDDS endpoint """

        parts = url_to_parts(thredds_url)._asdict()

        parts["path"][1] = "wms"
        parts["path"][-1] = parts["query"]["dataset"][0].split("/")[-1]
        parts["query"] = WMS_DEFAULT_PARAMS

        return parts_to_url(parts, trailing_slash=has_trailing_slash(thredds_url))

    @classmethod
    def get(cls, url, **kwargs):
        """ Overridden to parse the URL in case it includes the GetCapabilities request """

        parts = url_to_parts(url)

        is_catalog_query = (
            parts.path[0] == "thredds" and
            parts.path[1] == "catalog" and
            parts.path[-1] in ("catalog.html", "catalog.xml")
        )

        if not is_catalog_query:
            raise HTTPError("Invalid THREDDS endpoint", status_code=404, url=url)
        elif not parts.query.get("dataset"):
            raise HTTPError("Missing THREDDS dataset", status_code=404, url=url)

        parts.path[-1] = "catalog.xml"  # Ensure catalog service query

        thredds_url = parts_to_url(parts, trailing_slash=has_trailing_slash(url))
        return super(ThreddsResource, cls).get(thredds_url, **kwargs)

    def _get(self, url, styles_color_map=None, spatial_ref=None, wms_version=None, **kwargs):
        """ Overridden to initialize URL's derived from a THREDDS endpoint """

        super(ThreddsResource, self)._get(url, **kwargs)

        has_trailing = has_trailing_slash(url)
        parts = url_to_parts(url)._asdict()

        parts["path"][-1] = "catalog.html"
        self._catalog_url = parts_to_url(parts, trailing_slash=has_trailing)

        parts["path"][-1] = "catalog.xml"
        self._service_url = parts_to_url(parts, trailing_slash=has_trailing)

        self.spatial_ref = SpatialReference(spatial_ref or self.default_spatial_ref)
        self.wms_version = wms_version or WMS_KNOWN_VERSIONS[-1]

        self.styles_color_map = styles_color_map or {}

    def populate_field_values(self, data):
        """ Overridden to populate from multiple end points """

        # Flatten nested dataset metadata and service info

        dataset_info = data.pop("dataset")
        dataset_detail = reduce_value(dataset_info.pop("dataset", None))

        if dataset_detail and isinstance(dataset_detail, dict):
            dataset_info.update(dataset_detail)
        else:
            raise ValidationError(
                message="THREDDS resource must specify one dataset",
                datasets=dataset_info,
                url=self._url
            )

        dataset_meta = data.pop("metadata", dataset_info.pop("metadata", None))

        data.update(dataset_info or {})
        data.update(dataset_meta or {})

        # Derive and flatten other required service information

        data["dataSize"] = " ".join(data["dataSize"][k] for k in ("value", "units"))
        data["modified"] = data["date"]["value"] if data["date"]["date_type"] == "modified" else ""
        data["services"] = services = {s["name"]: s for s in data.pop("service")["service"]}

        url_path = data["urlPath"].split("/")

        # Construct file server endpoint by prepending path in services to dataset
        file_base = (services.get("ftp") or services.get("http") or {}).get("base")
        self._file_path = file_base.strip("/").split("/") + url_path if file_base else ""

        # Construct metadata endpoint by prepending path in services to dataset

        iso_base = (services.get("iso") or {}).get("base")
        if iso_base:
            self._iso_path = iso_base.strip("/").split("/") + url_path
        else:
            raise ValidationError(
                message="ISO metadata service is required for THREDDS resource",
                services=services,
                url=self._url
            )

        # Construct WMS endpoint for image requests by prepending path in services to dataset

        wms_base = (services.get("wms") or {}).get("base")
        if wms_base:
            # Update in case its different than thredds/wms
            self._wms_path = wms_base.strip("/").split("/") + url_path
        else:
            raise ValidationError(
                message="WMS service is required for THREDDS resource",
                services=services,
                url=self._url
            )

        # Service data is ready: populate base resource fields
        super(ThreddsResource, self).populate_field_values(data)

        # Fill out all other data from related endpoints

        self._parse_related_endpoints()
        self._populate_from_endpoints()

    def _parse_related_endpoints(self):
        """ Derive related end point URLs following THREDDS service conventions """

        has_trailing = has_trailing_slash(self._url)
        parts = url_to_parts(self._url)._asdict()

        if self._file_path:
            # Derive download url: thredds/fileServer/<urlPath>
            parts["path"] = self._file_path
            parts["query"] = {}
            self.download_url = parts_to_url(parts, trailing_slash=has_trailing)

            try:
                # Ping the URL and check the response code
                response = requests.head(self.download_url)
                response.raise_for_status()

            except requests.exceptions.HTTPError:
                self.download_url = None

        # Derive base WMS url: thredds/wms/<urlPath>
        parts["path"] = self._wms_path
        self._wms_url = parts_to_url(parts, trailing_slash=has_trailing)

        # Derive layers url: thredds/wms/<urlPath>?item=menu&request=GetMetadata
        parts["query"] = {"item": "menu", "request": "GetMetadata"}
        self._layers_url = parts_to_url(parts, trailing_slash=has_trailing)

        # Derive layers url format: thredds/wms/<urlPath>?item=layerDetails&layerName={layer_name}&request=GetMetadata
        parts["query"] = {"item": "layerDetails", "layerName": "{layer_id}", "request": "GetMetadata"}
        self._layers_url_format = parts_to_url(parts, trailing_slash=has_trailing)

        # Derive metadata url: thredds/iso/<urlPath>?dataset=<ID>
        parts["path"] = self._iso_path
        parts["query"] = {"dataset": self.id}
        self._metadata_url = parts_to_url(parts, trailing_slash=has_trailing)
        self._metadata_parser = ThreddsIsoParser(get_remote_element(self._metadata_url))

    def _populate_from_endpoints(self):
        """ Populate layers from metadata and individual layer endpoints """

        if self._lazy:
            return  # Query only when a related property has been dereferenced

        layer_metadata = {d["id"]: d for d in self._metadata_parser.dimensions}
        constraints = set()
        layers = []

        for idx, desc_id in enumerate((k, l) for k, v in self._query_layer_ids().items() for l in v):
            layers_desc, layer_id = desc_id

            if not self.description:
                # Use the first layer group description
                self.description = layers_desc

            layer_obj = self._query_layer(layer_id, idx, layer_metadata)
            layers.append(layer_obj)

            if layer_obj.copyright_text:
                constraints.add(layer_obj.copyright_text)

        self.full_extent = union_extent(l.full_extent for l in layers).project_to_web_mercator()
        self.layers = layers

        self.access_constraints = max(constraints) if constraints else self._metadata_parser.use_constraints
        self.credits = self._metadata_parser.data_credits or self.credits
        self.keywords.extend(k for k in self._metadata_parser.thematic_keywords if k not in layer_metadata)

        raster_info = self._metadata_parser.raster_info
        if raster_info["x_resolution"] and raster_info["y_resolution"]:
            self.spatial_resolution = "{x} by {y}".format(
                x=raster_info["x_resolution"],
                y=raster_info["y_resolution"]
            )

    def _query_layer(self, layer_id, layer_order, layer_metadata):
        """ Allows this resource to query one layer at a time instead of all at once """

        layer_info = layer_metadata[layer_id]
        layer_data = {
            "id": layer_id,
            "title": layer_id,
            "description": layer_info["title"],
            "dimensions": layer_info,
            "credits": self._metadata_parser.data_credits,
            "layer_order": layer_order,
            "version": self.version,
            "wms_version": self.wms_version,
        }

        layer_url = self._layers_url_format.format(layer_id=layer_id)

        return NcWMSLayerResource.get(
            layer_url,
            lazy=False,
            color_map=self.styles_color_map,
            layer_data=layer_data,
            session=(self._layer_session or self._session)
        )

    def _query_layer_ids(self, data=None, layer_ids=None):
        """ Queries layer list endpoint and returns leaf layer ids by layer group description """

        if data is None:
            try:
                data = JSONSerializer.to_dict(self._make_request(self._layers_url, {}, timeout=120).text)
            except requests.exceptions.HTTPError as ex:
                raise HTTPError(
                    "The THREDDS layer id query did not respond correctly",
                    underlying=ex, url=self._layers_url
                )

        label = data["label"]
        layers = defaultdict(list)

        for layer in data["children"][::-1]:

            if "children" in layer:
                for k, v in self._query_layer_ids(layer, layer_ids).items():
                    layers[k].extend(v)
            elif "id" in layer:
                if not layer_ids or layer["id"] in layer_ids:
                    layers[label].append(layer["id"])

        return layers if layers[label] else {k: v for k, v in layers.items() if v}

    def __getattribute__(self, item):
        """ Overridden to query related endpoints when fields populated from them have been dereferenced """

        if item in RELATED_ENDPOINT_FIELDS and self._lazy:
            self._lazy = False  # Ensure this block executes only once

            if not self._populated_field_values:
                # Not yet loaded, endpoints will not be skipped
                return self._load_resource()
            else:
                # Already loaded, but the endpoints were skipped
                self._populate_from_endpoints()

        return super(ThreddsResource, self).__getattribute__(item)

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

        if not layer_ids:
            raise ImageError("No layers from which to generate an image", url=self._url)

        elif style_ids and len(layer_ids) != len(style_ids):
            raise ImageError("Provided styles do not correspond to specified Layers", url=self._url)

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
                "version": (params or {}).get("version") or self.wms_version
            }
            if image_params["version"] == WMS_KNOWN_VERSIONS[1]:
                image_params["exceptions"] = "XML"
                image_params["crs"] = extent.spatial_reference.srs
            else:
                image_params["exceptions"] = WMS_EXCEPTION_FORMAT
                image_params["srs"] = extent.spatial_reference.srs

            # Note: time and custom params may require ordering to match layer - not clear from docs
            if time_range:
                image_params["time"] = time_range

            if params:
                image_params.update(params)

            # Send the image request

            response = self._make_request(self._wms_url, image_params, timeout=120)
            response_type = response.headers["content-type"]

            if response_type != image_format:
                error = f"Unexpected image format {response_type}: {image_format}\n\t{response.text}"
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
                "The THREDDS service image query did not respond correctly",
                params=image_params, underlying=ex, url=self._wms_url
            )
        except (IOError, ValueError) as ex:
            raise ImageError(
                "The WMS service did not return a valid image",
                params=image_params, underlying=ex, url=self._wms_url
            )


class ThreddsIsoParser(IsoParser):

    def _init_data_map(self):
        super(ThreddsIsoParser, self)._init_data_map()

        # Define custom dimensions property data structure

        if self._data_map["_root"] == "MD_Metadata":
            dim_root = "contentInfo/MD_CoverageDescription/dimension"
        else:
            dim_root = "contentInfo/MI_CoverageDescription/dimension"

        dim_format = dim_root + "/MD_Band/{dim_path}"
        dim_struct = {"id": "{id}", "title": "{title}", "units": "{units}"}

        self._data_structures["dimensions"] = format_xpaths(dim_struct, **{
            "id": dim_format.format(dim_path="sequenceIdentifier/MemberName/aName/CharacterString"),
            "title": dim_format.format(dim_path="descriptor/CharacterString"),
            "units": dim_format.format(
                dim_path="sequenceIdentifier/MemberName/attributeType/TypeName/aName/CharacterString"
            )
        })

        self._data_map["_dimensions_root"] = dim_root
        self._data_map["dimensions"] = ParserProperty(self._parse_complex_list, self._update_complex_list)
