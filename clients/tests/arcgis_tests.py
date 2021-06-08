import requests_mock

from unittest import mock

from parserutils.collections import setdefaults

from clients.arcgis import MapServerResource, FeatureServerResource, ImageServerResource
from clients.arcgis import MapLayerResource, FeatureLayerResource, GeometryServiceClient
from clients.exceptions import BadExtent, ContentError, HTTPError, ImageError, ServiceError
from clients.query.fields import RENDERER_DEFAULTS

from .utils import ResourceTestCase, get_extent_dict, get_spatial_reference_dict
from .utils import get_default_image, get_extent, get_object, get_spatial_reference


class ArcGISTestCase(ResourceTestCase):

    def setUp(self):
        super(ArcGISTestCase, self).setUp()

        self.arcgis_directory = self.data_directory / "arcgis"

        self.map_url = "https://www.fws.gov/wetlands/arcgis/rest/services/Wetlands/MapServer/?f=json"
        self.map_path = self.arcgis_directory / "map.json"
        self.map_layer_url = "https://www.fws.gov/wetlands/arcgis/rest/services/Wetlands/MapServer/0/?f=json"
        self.map_layer_path = self.arcgis_directory / "map-layer.json"
        self.map_layers_url = "https://www.fws.gov/wetlands/arcgis/rest/services/Wetlands/MapServer/layers?f=json"
        self.map_layers_path = self.arcgis_directory / "map-layers.json"
        self.map_legend_url = "https://www.fws.gov/wetlands/arcgis/rest/services/Wetlands/MapServer/legend/?f=json"
        self.map_legend_path = self.arcgis_directory / "map-legend.json"

        self.feature_url = "https://services1.arcgis.com/gbas/arcgis/rest/services/prcp/FeatureServer/?f=json"
        self.feature_path = self.arcgis_directory / "feature.json"
        self.feature_layer_url = "https://services1.arcgis.com/gbas/arcgis/rest/services/prcp/FeatureServer/0?f=json"
        self.feature_layer_path = self.arcgis_directory / "feature-layer.json"
        self.feature_layer_id_url = "https://services1.arcgis.com/gbas/arcgis/rest/services/prcp/FeatureServer/0/query"
        self.feature_layer_id_path = self.arcgis_directory / "feature-layer-ids.json"

        self.image_url = "https://map.dfg.ca.gov/arcgis/rest/services/BaseRemoteSensing/NAIP_2010/ImageServer/?f=json"
        self.image_path = self.arcgis_directory / "image.json"

        self.geometry_url = "http://tasks.arcgisonline.com/arcgis/rest/services/Geometry/GeometryServer/project"
        self.geometry_args = (
            "?f=json"
            "&geometries=%7B"
            "%22geometryType%22%3A+%22esriGeometryEnvelope%22%2C+"
            "%22geometries%22%3A+%5B%7B"
            "%22xmin%22%3A+-180.0%2C+%22ymin%22%3A+"
            "-90.0%2C+%22xmax%22%3A+180.0%2C+%22ymax%22%3A+90.0"
            "%7D%5D%7D"
            "&inSR=4326"
            "&outSR=3857"
        )
        self.geometry_path = self.arcgis_directory / "geometry.json"

        self.config_url = "https://services1.arcgis.com/errors/arcgis/rest/services/BadConfig/MapServer/?f=json"
        self.config_path = self.arcgis_directory / "config-error.json"
        self.empty_url = "https://services1.arcgis.com/errors/arcgis/rest/services/Empty/MapServer/?f=json"
        self.empty_path = self.arcgis_directory / "empty-error.json"
        self.generic_url = "https://services1.arcgis.com/errors/arcgis/rest/services/599/MapServer/?f=json"
        self.generic_path = self.arcgis_directory / "generic-error.json"
        self.not_found_url = "https://services1.arcgis.com/errors/arcgis/rest/services/NotFound/MapServer/?f=json"
        self.not_found_path = self.arcgis_directory / "not-found.json"
        self.token_required_url = "https://services1.arcgis.com/errors/arcgis/rest/services/Token/MapServer/?f=json"
        self.token_required_path = self.arcgis_directory / "token-required.json"

        self.error_path = self.arcgis_directory / "error.html"

    def mock_arcgis_client(self, mock_request, service_type):

        if service_type == "error":
            self.mock_mapservice_request(mock_request.get, self.config_url, self.config_path)
            self.mock_mapservice_request(mock_request.get, self.empty_url, self.empty_path)
            self.mock_mapservice_request(mock_request.get, self.generic_url, self.generic_path)
            self.mock_mapservice_request(mock_request.get, self.not_found_url, self.not_found_path)
            self.mock_mapservice_request(mock_request.get, self.token_required_url, self.token_required_path)
        elif service_type == "feature":
            self.mock_mapservice_request(mock_request.get, self.feature_url, self.feature_path)
            self.mock_mapservice_request(mock_request.get, self.feature_layer_url, self.feature_layer_path)
            self.mock_mapservice_request(mock_request.post, self.feature_layer_id_url, self.feature_layer_id_path)
        elif service_type == "geometry":
            self.mock_mapservice_request(mock_request.get, self.geometry_url + self.geometry_args, self.geometry_path)
        elif service_type == "image":
            self.mock_mapservice_request(mock_request.get, self.image_url, self.image_path)
        elif service_type == "map":
            self.mock_mapservice_request(mock_request.get, self.map_url, self.map_path)
            self.mock_mapservice_request(mock_request.get, self.map_layer_url, self.map_layer_path)
            self.mock_mapservice_request(mock_request.get, self.map_layers_url, self.map_layers_path)
            self.mock_mapservice_request(mock_request.get, self.map_legend_url, self.map_legend_path)
        else:
            raise AssertionError(f"Invalid service type: {service_type}")

    @requests_mock.Mocker()
    def test_invalid_arcgis_urls(self, mock_request):

        # Map all service and layer urls to data
        self.mock_arcgis_client(mock_request, "error")
        self.mock_arcgis_client(mock_request, "map")
        self.mock_arcgis_client(mock_request, "feature")
        self.mock_arcgis_client(mock_request, "image")

        # Test service level errors

        error_url = self.empty_url

        with self.assertRaises(ContentError, msg=f"ServiceError not raised for map service: {error_url}"):
            MapServerResource.get(error_url, lazy=False)
        with self.assertRaises(ContentError, msg=f"ServiceError not raised for feature service: {error_url}"):
            FeatureServerResource.get(error_url, lazy=False)
        with self.assertRaises(ContentError, msg=f"ServiceError not raised for image service: {error_url}"):
            ImageServerResource.get(error_url, lazy=False)

        for error_url in (self.config_url, self.generic_url, self.not_found_url, self.token_required_url):

            with self.assertRaises(ServiceError, msg=f"ServiceError not raised for map service: {error_url}"):
                MapServerResource.get(error_url, lazy=False)
            with self.assertRaises(ServiceError, msg=f"ServiceError not raised for feature service: {error_url}"):
                FeatureServerResource.get(error_url, lazy=False)
            with self.assertRaises(ServiceError, msg=f"ServiceError not raised for image service: {error_url}"):
                ImageServerResource.get(error_url, lazy=False)

        # Test layer level errors

        session = self.mock_mapservice_session(self.empty_path)

        with self.assertRaises(ContentError, msg=f"ServiceError not raised for map layer: {error_url}"):
            MapLayerResource.get(self.map_layer_url, lazy=False, session=session)
        with self.assertRaises(ContentError, msg=f"ServiceError not raised for feature layer: {error_url}"):
            FeatureLayerResource.get(self.feature_layer_url, lazy=False, session=session)

        for error_path in (self.config_path, self.generic_path, self.not_found_path, self.token_required_path):
            session = self.mock_mapservice_session(error_path)

            with self.assertRaises(ServiceError, msg=f"ServiceError not raised for map layer: {error_url}"):
                MapLayerResource.get(self.map_layer_url, lazy=False, session=session)
            with self.assertRaises(ServiceError, msg=f"ServiceError not raised for feature layer: {error_url}"):
                FeatureLayerResource.get(self.feature_layer_url, lazy=False, session=session)

    @requests_mock.Mocker()
    def test_valid_arcgis_geometry_request(self, mock_request):
        self.mock_arcgis_client(mock_request, "geometry")

        extent_dict = get_extent_dict(web_mercator=False)
        spatial_ref = get_spatial_reference_dict(web_mercator=True)

        client = GeometryServiceClient(self.geometry_url)
        projected = client.project_extent(extent_dict, spatial_ref)

        self.assertEqual(
            projected.as_list(),
            [-20037507.842788247, -30240971.45838615, 20037507.842788247, 30240971.45838615]
        )
        self.assertEqual(projected.spatial_reference.wkid, 3857)

    @requests_mock.Mocker()
    def test_invalid_arcgis_geometry_request(self, mock_request):

        client = GeometryServiceClient(self.geometry_url)
        extent = get_extent(web_mercator=False)

        self.mock_mapservice_request(mock_request.get, self.geometry_url, self.error_path)
        with self.assertRaises(BadExtent):
            client.project_extent(extent, get_spatial_reference(web_mercator=True))

        self.mock_mapservice_request(mock_request.get, self.geometry_url, self.empty_path)
        with self.assertRaises(ContentError):
            client.project_extent(extent, get_spatial_reference(web_mercator=True))

        self.mock_mapservice_request(mock_request.get, self.geometry_url, self.geometry_path, ok=False)
        with self.assertRaises(HTTPError):
            client.project_extent(extent, get_spatial_reference(web_mercator=True))

    @requests_mock.Mocker()
    def test_valid_arcgis_mapservice_request(self, mock_request):
        self.mock_arcgis_client(mock_request, "map")

        client = MapServerResource.get(self.map_url, lazy=False)

        # ArcGISResource
        self.assertEqual(client.version, 10.5)
        self.assertEqual(client.description, "This data set represents the extent of wetlands and deepwater habitats.")
        self.assertEqual(client.copyright_text, "U.S. Fish and Wildlife Service, National Standards and Support Team")
        self.assertEqual(client.capabilities, "Map,Query,Data")
        self.assertEqual(client.supported_query_formats, "JSON,AMF,geoJSON")
        self.assertEqual(client.max_record_count, 1000)
        self.assertEqual(client.time_enabled, False)
        self.assertEqual(client.time_info, None)

        # ArcGISServerResource
        self.assertEqual(client.service_description, "")

        self.assert_object_values(client.document_info, {
            "title": "National Wetlands Inventory",
            "author": "U.S. Fish and Wildlife Service, National Standards and Support Team",
            "comments": "For wetland information visit www.fws.gov/wetlands/",
            "subject": "This data set represents the extent of wetlands and deepwater habitats",
            "category": "",
            "keywords": "Wetlands,Hydrography,Surface water,Swamps,Marshes,Bogs,Fens"
        })
        self.assertEqual(
            client.full_extent.as_list(),
            [-19951753.9839, -1622986.231899999, 20021553.447300002, 11554273.714599997]
        )
        self.assertEqual(client.full_extent.spatial_reference.wkid, 102100)
        self.assertEqual(
            client.initial_extent.as_list(),
            [513260.3879679106, 7886090.999233324, 18518909.628708653, 13864251.221455548]
        )
        self.assertEqual(client.initial_extent.spatial_reference.wkid, 102100)
        self.assertEqual(client.spatial_reference.wkid, 102100)

        self.assertEqual(len(client.tables), 1)
        self.assert_object_values(client.tables[0], {
            "id": 2,
            "name": "NWI_Wetland_Codes"
        })

        # ArcGISTiledImageResource
        self.assertEqual(client.min_scale, 112076270.45185184)
        self.assertEqual(client.max_scale, 0)
        self.assertEqual(client.max_image_height, 4096)
        self.assertEqual(client.max_image_width, 4096)
        self.assertEqual(client.tile_info, None)

        # MapServerResource + ArcGISTiledImageResource + ArcGISServerResource + ArcGISResource
        self.assertEqual(client.name, "Wetlands")
        self.assertEqual(client.units, "esriMeters")
        self.assertEqual(client.export_tiles_allowed, False)
        self.assertEqual(client.single_fused_map_cache, False)
        self.assertEqual(client.supports_dynamic_layers, True)
        self.assertEqual(client.supported_extensions, "KmlServer,WMSServer")
        self.assertEqual(client.supported_image_format_types, "PNG,JPG,DIB,TIFF,EMF,PS,PDF,GIF,SVG,SVGZ,BMP")
        self.assertEqual(len(client.layers), 1)

        # Test layer level information for first layer

        first_layer = client.layers[0]

        # ArcGISResource
        self.assertEqual(first_layer.version, 10.5)
        self.assertEqual(
            first_layer.description,
            "This data set represents the extent of wetlands and deepwater habitats."
        )
        self.assertEqual(
            first_layer.copyright_text,
            "U.S. Fish and Wildlife Service, National Standards and Support Team"
        )
        self.assertEqual(first_layer.capabilities, "Map,Query,Data")
        self.assertEqual(first_layer.supported_query_formats, "JSON,AMF,geoJSON")
        self.assertEqual(first_layer.max_record_count, 1000)
        self.assertEqual(first_layer.time_enabled, False)
        self.assertEqual(first_layer.time_info, None)

        # ArcGISLayerResource
        self.assertEqual(first_layer.id, 0)
        self.assertEqual(first_layer.name, "Wetlands")
        self.assertEqual(first_layer.type_id_field, None)
        self.assertEqual(first_layer.display_field, "Wetlands.ATTRIBUTE")
        self.assertEqual(first_layer.edit_fields_info, None)

        self.assertEqual(len(first_layer.fields), len(MAP_LAYER_FIELDS))
        for idx, field in enumerate(MAP_LAYER_FIELDS):
            self.assert_object_values(first_layer.fields[idx], field)

        self.assert_object_values(
            first_layer.ownership_based_access_control_for_features,
            {"allow_others_to_query": True}
        )

        self.assertEqual(first_layer.relationships, [])
        self.assertEqual(first_layer.default_visibility, True)
        self.assertEqual(first_layer.has_attachments, False)
        self.assertEqual(first_layer.has_labels, True)
        self.assertEqual(first_layer.is_versioned, False)
        self.assertEqual(first_layer.supports_advanced_queries, True)
        self.assertEqual(first_layer.supports_rollback_on_failure, False)
        self.assertEqual(first_layer.supports_statistics, True)
        self.assertEqual(first_layer.sync_can_return_changes, False)
        self.assertEqual(
            first_layer.extent.as_list(),
            [-19024325.925, -1622985.366700001, 16239651.735799998, 11554273.612999998]
        )
        self.assertEqual(first_layer.extent.spatial_reference.wkid, 102100)
        self.assertEqual(first_layer.geometry_type, "esriGeometryPolygon")
        self.assertEqual(first_layer.min_scale, 250000)
        self.assertEqual(first_layer.max_scale, 0)

        self.assert_object_values(first_layer.drawing_info, MAP_LAYER_DRAWING_INFO)

        # MapLayerResource
        self.assertEqual(first_layer.parent, None)
        self.assertEqual(first_layer.sub_layers, [])
        self.assertEqual(first_layer.can_modify_layer, True)
        self.assertEqual(first_layer.can_scale_symbols, False)
        self.assertEqual(first_layer.definition_query, None)
        self.assertEqual(first_layer.popup_type, "esriServerHTMLPopupTypeNone")
        self.assertEqual(len(first_layer.legend), 8)

        # Test layer level information for first layer

        first_legend_element = first_layer.legend[0]

        # MapLegendResource
        self.assertEqual(first_legend_element.version, 10.5)
        self.assertEqual(first_legend_element.layer_id, 0)
        self.assertEqual(first_legend_element.layer_name, "Wetlands")
        self.assertEqual(first_legend_element.layer_type, "Feature Layer")
        self.assertEqual(first_legend_element.min_scale, 250000)
        self.assertEqual(first_legend_element.max_scale, 0)
        self.assertEqual(first_legend_element.label, "Estuarine and Marine Deepwater")
        self.assertEqual(
            first_legend_element.url,
            (
                "https://www.fws.gov/wetlands/arcgis/rest/services/Wetlands/MapServer/0/"
                "images/bc7988a8ada44f94ae79a56c02b45bb7"
            )
        )
        self.assertEqual(
            first_legend_element.image_base64,
            (
                "iVBORw0KGgoAAAANSUhEUgAAABQAAAAUCAYAAACNiR0NAAAAAXNSR0IB2"
                "cksfwAAAAlwSFlzAAAOxAAADsQBlSsOGwAAADtJREFUOI1jYaAyYKGlgf="
            )
        )
        self.assertEqual(first_legend_element.content_type, "image/png")
        self.assertEqual(first_legend_element.height, 20)
        self.assertEqual(first_legend_element.width, 20)
        self.assertEqual(first_legend_element.values, ["Estuarine and Marine Deepwater"])

    @requests_mock.Mocker()
    def test_valid_arcgis_mapservice_image_request(self, mock_request):
        self.mock_arcgis_client(mock_request, "map")
        self.assert_get_image(MapServerResource.get(self.map_url, lazy=False))

    @requests_mock.Mocker()
    def test_invalid_arcgis_mapservice_image_request(self, mock_request):
        self.mock_arcgis_client(mock_request, "map")

        client = MapServerResource.get(self.map_url, lazy=False)
        client._session = self.mock_mapservice_session(self.error_path)

        with self.assertRaises(ImageError):
            client.get_image(get_extent(web_mercator=True).as_dict(), 100, 100)

        client._session = self.mock_mapservice_session(self.error_path, ok=False)
        with self.assertRaises(HTTPError):
            client.get_image(get_extent(web_mercator=True).as_dict(), 100, 100)

    @requests_mock.Mocker()
    def test_valid_arcgis_featureservice_request(self, mock_request):
        self.mock_arcgis_client(mock_request, "feature")

        client = FeatureServerResource.get(self.feature_url, lazy=False)

        # ArcGISResource
        self.assertEqual(client.version, 10.81)
        self.assertEqual(client.description, "")
        self.assertEqual(client.copyright_text, "")
        self.assertEqual(client.capabilities, "Query")
        self.assertEqual(client.supported_query_formats, "JSON")
        self.assertEqual(client.max_record_count, 2000)
        self.assertEqual(client.time_enabled, False)
        self.assertEqual(client.time_info, None)

        # ArcGISServerResource
        self.assertEqual(client.service_description, "")
        self.assertEqual(client.document_info, None)
        self.assertEqual(
            client.full_extent.as_list(),
            [-13407041.172414886, 4623683.436859363, -13267891.808923297, 4838750.263348374]
        )
        self.assertEqual(client.full_extent.spatial_reference.wkid, 102100)
        self.assertEqual(
            client.initial_extent.as_list(),
            [-13407041.172414886, 4623683.436859363, -13267891.808923297, 4838750.263348374]
        )
        self.assertEqual(client.initial_extent.spatial_reference.wkid, 102100)
        self.assertEqual(client.spatial_reference.wkid, 102100)
        self.assertEqual(client.tables, [])

        # FeatureServerResource
        self.assertEqual(client.units, "esriMeters")
        self.assertEqual(client.has_static_data, True)
        self.assertEqual(client.has_versioned_data, False)
        self.assertEqual(client.allow_geometry_updates, True)

        self.assert_object_values(client.editor_tracking_info, {
            "enable_editor_tracking": False,
            "enable_ownership_access_control": False,
            "allow_others_to_query": True,
            "allow_others_to_update": True,
            "allow_others_to_delete": True
        })

        self.assertEqual(client.enable_z_defaults, False)
        self.assertEqual(client.z_default, None)
        self.assertEqual(client.supports_disconnected_editing, False)
        self.assertEqual(client.sync_enabled, False)
        self.assertEqual(client.sync_capabilities, None)
        self.assertEqual(len(client.layers), 1)

        # Test layer level information for first layer

        first_layer = client.layers[0]

        # ArcGISResource
        self.assertEqual(first_layer.version, 10.81)
        self.assertEqual(first_layer.description, "")
        self.assertEqual(first_layer.copyright_text, "")
        self.assertEqual(first_layer.capabilities, "Query")
        self.assertEqual(first_layer.supported_query_formats, "JSON,geoJSON,PBF")
        self.assertEqual(first_layer.max_record_count, 2000)
        self.assertEqual(first_layer.time_enabled, False)
        self.assertEqual(first_layer.time_info, None)

        # ArcGISLayerResource
        self.assertEqual(first_layer.id, 0)
        self.assertEqual(first_layer.name, "gbas_3839_prcp_2070_50")
        self.assertEqual(first_layer.type_id_field, "")
        self.assertEqual(first_layer.display_field, "")

        self.assertEqual(len(first_layer.fields), len(FEATURE_LAYER_FIELDS))
        for idx, field in enumerate(FEATURE_LAYER_FIELDS):
            self.assert_object_values(first_layer.fields[idx], field)

        self.assertEqual(first_layer.edit_fields_info, None)
        self.assertEqual(first_layer.ownership_based_access_control_for_features, None)
        self.assertEqual(first_layer.relationships, [])
        self.assertEqual(first_layer.default_visibility, True)
        self.assertEqual(first_layer.has_attachments, False)
        self.assertEqual(first_layer.has_labels, False)
        self.assertEqual(first_layer.is_versioned, False)
        self.assertEqual(first_layer.supports_advanced_queries, True)
        self.assertEqual(first_layer.supports_rollback_on_failure, False)
        self.assertEqual(first_layer.supports_statistics, True)
        self.assertEqual(first_layer.sync_can_return_changes, False)
        self.assertEqual(
            first_layer.extent.as_list(),
            [-13407041.172414886, 4623683.436859363, -13267891.808923297, 4838750.263348374]
        )
        self.assertEqual(first_layer.extent.spatial_reference.wkid, 102100)
        self.assertEqual(first_layer.geometry_type, "esriGeometryPoint")
        self.assertEqual(first_layer.min_scale, 18489298)
        self.assertEqual(first_layer.max_scale, 0)

        self.assert_object_values(first_layer.drawing_info, FEATURE_LAYER_DRAWING_INFO)

        # FeatureLayerResource
        self.assertEqual(first_layer.global_id_field, "")
        self.assertEqual(first_layer.object_id_field, "FID")
        self.assertEqual(first_layer.effective_min_scale, None)
        self.assertEqual(first_layer.effective_max_scale, None)
        self.assertEqual(first_layer.has_static_data, True)
        self.assertEqual(first_layer.has_m, False)
        self.assertEqual(first_layer.has_z, False)
        self.assertEqual(first_layer.enable_z_defaults, False)
        self.assertEqual(first_layer.z_default, None)
        self.assertEqual(first_layer.allow_geometry_updates, True)
        self.assertEqual(first_layer.html_popup_type, "esriServerHTMLPopupTypeNone")
        self.assertEqual(first_layer.time_interval, None)
        self.assertEqual(first_layer.time_interval_units, None)

        self.assertEqual(len(first_layer.templates), len(FEATURE_LAYER_TEMPLATES))
        for idx, template in enumerate(FEATURE_LAYER_TEMPLATES):
            self.assert_object_values(first_layer.templates[idx], template)

        self.assertEqual(first_layer.types, [])

    @requests_mock.Mocker()
    @mock.patch('clients.arcgis.FeatureLayerResource.generate_sub_image')
    def test_valid_arcgis_featureservice_image_request(self, mock_request, mock_sub_image):
        mock_sub_image.return_value = get_default_image()

        self.mock_arcgis_client(mock_request, "feature")
        self.assert_get_image(FeatureServerResource.get(self.feature_url, lazy=False))

    @requests_mock.Mocker()
    def test_invalid_arcgis_featureservice_image_request(self, mock_request):

        self.mock_arcgis_client(mock_request, "feature")

        client = FeatureServerResource.get(self.feature_url, lazy=False)
        client._session = self.mock_mapservice_session(self.error_path)

        # Test with valid feature service data (fails at generate_sub_image)

        with self.assertRaises(NotImplementedError):
            client.get_image(get_extent(web_mercator=True).as_dict(), 100, 100)

        # Test with invalid feature data

        self.mock_mapservice_request(
            mock_request.post,
            self.feature_layer_id_url,
            self.arcgis_directory / "not-found.json"
        )
        with self.assertRaises(ImageError):
            client.get_image(get_extent(web_mercator=True).as_dict(), 100, 100)

    @requests_mock.Mocker()
    def test_valid_arcgis_imageservice_request(self, mock_request):
        self.mock_arcgis_client(mock_request, "image")

        client = ImageServerResource.get(self.image_url, lazy=False)

        # ArcGISResource
        self.assertEqual(client.version, 10.5)
        self.assertEqual(client.description, "Natural color representation of NAIP 2010 aerial imagery.")
        self.assertEqual(client.copyright_text, "")
        self.assertEqual(client.capabilities, "Image,Metadata,Catalog")
        self.assertEqual(client.supported_query_formats, None)
        self.assertEqual(client.max_record_count, 1000)
        self.assertEqual(client.time_enabled, False)
        self.assertEqual(client.time_info, None)

        # ArcGISServerResource
        self.assertEqual(client.service_description, "Natural color representation of NAIP 2010 aerial imagery.")
        self.assertEqual(client.document_info, None)
        self.assertEqual(
            client.full_extent.as_list(),
            [-13852876.8488, 3828749.521800003, -12703715.8488, 5170873.521800003]
        )
        self.assertEqual(client.full_extent.spatial_reference.wkid, 102100)
        self.assertEqual(
            client.initial_extent.as_list(),
            [-13852876.8488, 3828749.521800003, -12703715.8488, 5170873.521800003]
        )
        self.assertEqual(client.initial_extent.spatial_reference.wkid, 102100)
        self.assertEqual(client.spatial_reference.wkid, 102100)
        self.assertEqual(client.tables, None)

        # ArcGISTiledImageResource
        self.assertEqual(client.min_scale, 0)
        self.assertEqual(client.max_scale, 0)
        self.assertEqual(client.max_image_height, 4100)
        self.assertEqual(client.max_image_width, 15000)
        self.assertEqual(client.tile_info, None)

        # ImageServerResource
        self.assertEqual(client.id, 0)
        self.assertEqual(client.name, "Base_Remote_Sensing/NAIP_2010")
        self.assertEqual(client.allowed_mosaic_methods, ["Center", "NorthWest", "Nadir", "Viewpoint", "Seamline"])
        self.assertEqual(client.allow_raster_function, True)
        self.assertEqual(client.band_count, 3)
        self.assertEqual(client.default_resampling_method, "Bilinear")

        self.assertEqual(len(client.fields), len(IMAGE_SERVICE_FIELDS))
        for idx, field in enumerate(IMAGE_SERVICE_FIELDS):
            self.assert_object_values(client.fields[idx], field)

        self.assertEqual(client.edit_fields_info, None)
        self.assertEqual(
            client.extent.as_list(),
            [-13852876.8488, 3828749.521800003, -12703715.8488, 5170873.521800003]
        )
        self.assertEqual(client.extent.spatial_reference.wkid, 102100)
        self.assertEqual(client.spatial_reference.wkid, 102100)
        self.assertEqual(client.has_color_map, False)
        self.assertEqual(client.has_histograms, False)
        self.assertEqual(client.has_multi_dimensions, False)
        self.assertEqual(client.has_raster_attribute_table, False)
        self.assertEqual(client.max_values, [])
        self.assertEqual(client.mean_values, [])
        self.assertEqual(client.min_values, [])
        self.assertEqual(client.object_id_field, "OBJECTID")
        self.assertEqual(client.ownership_based_access_control_for_rasters, None)
        self.assertEqual(client.pixel_size_x, 1)
        self.assertEqual(client.pixel_size_y, 1)
        self.assertEqual(client.pixel_type, "U8")
        self.assertEqual(client.service_data_type, "esriImageServiceDataTypeRGB")
        self.assertEqual(client.standard_variation_values, [])
        self.assertEqual(client.supports_statistics, True)
        self.assertEqual(client.supports_advanced_queries, True)

    @requests_mock.Mocker()
    def test_valid_arcgis_imageservice_image_request(self, mock_request):
        self.mock_arcgis_client(mock_request, "image")
        self.assert_get_image(ImageServerResource.get(self.image_url, lazy=False))

    @requests_mock.Mocker()
    def test_invalid_arcgis_imageservice_image_request(self, mock_request):
        self.mock_arcgis_client(mock_request, "image")

        client = ImageServerResource.get(self.image_url, lazy=False)
        client._session = self.mock_mapservice_session(self.error_path)

        with self.assertRaises(ImageError):
            client.get_image(get_extent(web_mercator=True).as_dict(), 100, 100)

        client._session = self.mock_mapservice_session(self.error_path, ok=False)
        with self.assertRaises(HTTPError):
            client.get_image(get_extent(web_mercator=True).as_dict(), 100, 100)


IMAGE_SERVICE_FIELDS = [
    {
        "name": "OBJECTID",
        "type": "esriFieldTypeOID",
        "alias": "OBJECTID",
        "domain": None
    },
    {
        "name": "Shape",
        "type": "esriFieldTypeGeometry",
        "alias": "Shape",
        "domain": None
    },
    {
        "name": "Name",
        "type": "esriFieldTypeString",
        "alias": "Name",
        "domain": None,
        "length": 50
    },
    {
        "name": "Category",
        "type": "esriFieldTypeInteger",
        "alias": "Category",
        "domain": get_object({
            "type": "codedValue",
            "name": "MosaicCatalogItemCategoryDomain",
            "coded_values": [
                get_object({"name": "Unknown", "code": 0}),
                get_object({"name": "Primary", "code": 1}),
                get_object({"name": "Incomplete", "code": 254}),
                get_object({"name": "Custom", "code": 255})
            ],
            "merge_policy": "esriMPTDefaultValue",
            "split_policy": "esriSPTDefaultValue"
        }),
    },
    {
        "name": "CenterX",
        "type": "esriFieldTypeDouble",
        "alias": "CenterX",
        "domain": None
    },
    {
        "name": "CenterY",
        "type": "esriFieldTypeDouble",
        "alias": "CenterY",
        "domain": None
    }
]

FEATURE_LAYER_FIELDS = [
    {
        "name": "FID",
        "type": "esriFieldTypeOID",
        "actual_type": "int",
        "alias": "FID",
        "sql_type": "sqlTypeInteger",
        "nullable": False,
        "editable": False,
        "domain": None,
        "default_value": None
    },
    {
        "name": "POINTID",
        "type": "esriFieldTypeInteger",
        "actual_type": "int",
        "alias": "POINTID",
        "sql_type": "sqlTypeInteger",
        "nullable": True,
        "editable": True,
        "domain": None,
        "default_value": None
    },
    {
        "name": "POINT_X",
        "type": "esriFieldTypeDouble",
        "actual_type": "float",
        "alias": "POINT_X",
        "sql_type": "sqlTypeFloat",
        "nullable": True,
        "editable": True,
        "domain": None,
        "default_value": None
    },
    {
        "name": "POINT_Y",
        "type": "esriFieldTypeDouble",
        "actual_type": "float",
        "alias": "POINT_Y",
        "sql_type": "sqlTypeFloat",
        "nullable": True,
        "editable": True,
        "domain": None,
        "default_value": None
    }
]
FEATURE_LAYER_DRAWING_INFO = {
    "renderer": get_object(setdefaults({
        "type": "simple",
        "symbol": get_object({
            "type": "esriPMS",
            "url": "RedSphere.png",
            "image": "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAABGdBTUEAALGPC/6ZiGvGAAAAAASUVORK5CYII=",
            "content_type": "image/png",
            "width": 15,
            "height": 15
        })
    }, RENDERER_DEFAULTS))
}
FEATURE_LAYER_TEMPLATES = [
    {
        "name": "New Feature",
        "description": "",
        "drawing_tool": "esriFeatureEditToolPoint",
        "prototype": get_object({
            "attributes": get_object({"point_x": None, "point_y": None})
        })
    }
]

MAP_LAYER_FIELDS = [
    {
        "name": "Wetlands.OBJECTID",
        "type": "esriFieldTypeOID",
        "alias": "OBJECTID",
        "domain": None
    },
    {
        "name": "Wetlands.ATTRIBUTE",
        "type": "esriFieldTypeString",
        "alias": "ATTRIBUTE",
        "length": 20,
        "domain": None
    },
    {
        "name": "Wetlands.ACRES",
        "type": "esriFieldTypeDouble",
        "alias": "ACRES",
        "domain": None
    },
    {
        "name": "Wetlands.SHAPE",
        "type": "esriFieldTypeGeometry",
        "alias": "Shape",
        "domain": None
    },
    {
        "name": "Wetlands.GLOBALID",
        "type": "esriFieldTypeGlobalID",
        "alias": "GLOBALID",
        "length": 38,
        "domain": None
    },
    {
        "name": "Wetlands.WETLAND_TYPE",
        "type": "esriFieldTypeString",
        "alias": "WETLAND_TYPE",
        "length": 50,
        "domain": None
    },
]
MAP_LAYER_DRAWING_INFO = {
    "renderer": get_object(setdefaults({
        "type": "uniqueValue",
        "field1": "Wetlands.WETLAND_TYPE",
        "field2": None,
        "field3": None,
        "default_symbol": None,
        "default_label": None,
        "unique_values": [
            get_object({
                "symbol": get_object({
                    "type": "esriSFS",
                    "style": "esriSFSSolid",
                    "color": [0, 124, 136, 255],
                    "outline": get_object({
                        "type": "esriSLS",
                        "style": "esriSLSSolid",
                        "color": [0, 0, 0, 255],
                        "width": 0.4
                    })
                }),
                "value": "Estuarine and Marine Deepwater",
                "label": "Estuarine and Marine Deepwater",
                "description": ""
            }),
            get_object({
                "symbol": get_object({
                    "type": "esriSFS",
                    "style": "esriSFSSolid",
                    "color": [102, 194, 165, 255],
                    "outline": get_object({
                        "type": "esriSLS",
                        "style": "esriSLSSolid",
                        "color": [0, 0, 0, 255],
                        "width": 0.4
                    })
                }),
                "value": "Estuarine and Marine Wetland",
                "label": "Estuarine and Marine Wetland",
                "description": ""
            })
        ],
        "field_delimiter": ","
    }, RENDERER_DEFAULTS)),
    "transparency": 0,
    "labeling": [
        get_object({
            "placement": "esriServerPolygonPlacementAlwaysHorizontal",
            "where": None,
            "expression": "[Wetlands.ATTRIBUTE]",
            "use_coded_values": True,
            "symbol": get_object({
                "type": "esriTS",
                "color": [255, 255, 255, 255],
                "background_color": None,
                "border_line_color": None,
                "border_line_width": None,
                "vertical_alignment": "bottom",
                "horizontal_alignment": "center",
                "is_rtl": False,
                "angle": 0,
                "offset_x": 0,
                "offset_y": 0,
                "kerning": True,
                "halo_color": None,
                "halo_size": None,
                "font": get_object({
                    "family": "Arial",
                    "size": 10,
                    "style": "normal",
                    "weight": "normal",
                    "decoration": "none"
                })
            }),
            "min_scale": 50000,
            "max_scale": 0
        })
    ]
}
