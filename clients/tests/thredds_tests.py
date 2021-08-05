import requests_mock

from unittest import mock
from parserutils.urls import get_base_url, url_to_parts

from ..exceptions import HTTPError, ImageError, ValidationError
from ..utils.geometry import Extent
from ..thredds import ThreddsResource

from .utils import ResourceTestCase, get_extent


class THREDDSTestCase(ResourceTestCase):

    def setUp(self):
        super(THREDDSTestCase, self).setUp()

        self.thredds_directory = self.data_directory / "thredds"

        self.base_url = "http://thredds.northwestknowledge.net:8080/thredds"
        self.service_path = "NWCSC_IS_ALL_SCAN/projections/macav2metdata/DATABASIN"
        self.dataset_path = f"{self.service_path}/macav2metdata.nc"
        self.base_wms_url = f"{self.base_url}/wms/{self.dataset_path}"
        self.layer_name = "macav2metdata_pr_ANN_20702099_rcp45_20CMIP5ModelMean"

        self.download_url = f"{self.base_url}/fileServer/{self.dataset_path}"

        self.catalog_url = (
            f"{self.base_url}/catalog/{self.service_path}/catalog.xml?dataset={self.dataset_path}"
        )
        self.catalog_path = self.thredds_directory / "thredds-catalog.xml"

        self.metadata_url = f"{self.base_url}/iso/{self.dataset_path}?dataset={self.dataset_path}"
        self.metadata_path = self.thredds_directory / "thredds-metadata.xml"

        self.wms_service_url = f"{self.base_wms_url}?service=WMS&version=1.3.0&request=GetCapabilities"
        self.wms_service_path = self.thredds_directory / "thredds-wms.xml"

        self.layer_menu_url = f"{self.base_wms_url}?item=menu&request=GetMetadata"
        self.layer_menu_path = self.thredds_directory / "thredds-layers.json"

        self.layer_url = f"{self.base_wms_url}?item=layerDetails&layerName={self.layer_name}&request=GetMetadata"
        self.layer_path = self.thredds_directory / "thredds-layer.json"

        self.legend_url = (
            f"{self.base_wms_url}?palette=ferret"
            f"&request=GetLegendGraphic&layer={self.layer_name}&colorbaronly=True"
        )

    def mock_thredds_client(self, mock_request, mock_metadata):
        with open(self.metadata_path) as iso_metadata:
            mock_metadata.return_value = iso_metadata.read()

        mock_request.head(self.download_url, status_code=200)

        self.mock_mapservice_request(mock_request.get, self.catalog_url, self.catalog_path)
        self.mock_mapservice_request(mock_request.get, self.metadata_url, self.metadata_path)
        self.mock_mapservice_request(mock_request.get, self.wms_service_url, self.wms_service_path)
        self.mock_mapservice_request(mock_request.get, self.layer_url, self.layer_path)
        self.mock_mapservice_request(mock_request.get, self.layer_menu_url, self.layer_menu_path)

    def test_client_name(self):

        result = ThreddsResource.client_name
        self.assertEqual(result, "THREDDS client")

    def test_service_name(self):

        result = ThreddsResource.service_name
        self.assertEqual(result, "THREDDS service")

    @requests_mock.Mocker()
    @mock.patch("clients.thredds.get_remote_element")
    def test_invalid_thredds_url(self, mock_request, mock_metadata):

        # Test with invalid url

        session = self.mock_mapservice_session(self.data_directory / "test.html")
        with self.assertRaises(HTTPError):
            ThreddsResource.get("http://www.google.com/test", session=session, lazy=False)

        # Test with invalid catalog url

        session = self.mock_mapservice_session(self.catalog_path)
        with self.assertRaises(HTTPError):
            broken_url = f"{self.base_url}/catalog/{self.service_path}/catalog.xml"
            ThreddsResource.get(broken_url, session=session, lazy=False)

        # Test with missing catalog dataset

        session = self.mock_mapservice_session(self.thredds_directory / "invalid-catalog.xml")
        with self.assertRaises(ValidationError):
            ThreddsResource.get(self.catalog_url, session=session, lazy=False)

        # Test with missing metadata endpoint

        session = self.mock_mapservice_session(self.thredds_directory / "invalid-iso-catalog.xml")
        with self.assertRaises(ValidationError):
            ThreddsResource.get(self.catalog_url, session=session, lazy=False)

        # Test with missing WMS endpoint

        session = self.mock_mapservice_session(self.thredds_directory / "invalid-wms-catalog.xml")
        with self.assertRaises(ValidationError):
            ThreddsResource.get(self.catalog_url, session=session, lazy=False)

        # Test with broken layer menu endpoint

        self.mock_thredds_client(mock_request, mock_metadata)
        self.mock_mapservice_request(mock_request.get, self.layer_menu_url, self.layer_menu_path, ok=False)

        with self.assertRaises(HTTPError):
            ThreddsResource.get(self.catalog_url, lazy=False)

    @requests_mock.Mocker()
    @mock.patch("clients.thredds.get_remote_element")
    def test_valid_thredds_request(self, mock_request, mock_metadata):
        self.mock_thredds_client(mock_request, mock_metadata)

        # Test variables initialized before query with alternate WMS version

        client = ThreddsResource.get(self.catalog_url, lazy=True, wms_version="1.1.1")

        self.assertEqual(client.wms_version, "1.1.1")
        self.assertEqual(client._catalog_url, self.catalog_url.replace(".xml", ".html"))
        self.assertEqual(client._service_url, self.catalog_url)
        self.assertEqual(set(client._required_fields), {
            "id", "name", "authority", "version",
            "dataSize", "dataFormat", "dataType", "modified", "services"
        })

        # Test population of related-endpoint-specific fields
        self.assertEqual(client.access_constraints, None)

        # Test all variables with default WMS version (1.3.0)

        styles_color_map = {
            "ferret": {
                "name": "Ferret",
                "colors": ["#CC00FF", "#00994D", "#FFFF00", "#FF0000", "#990000"]
            }
        }
        client = ThreddsResource.get(
            self.catalog_url, lazy=True,
            styles_color_map=styles_color_map
        )

        self.assertEqual(client.id, "NWCSC_IS_ALL_SCAN/projections/macav2metdata/DATABASIN/macav2metdata.nc")
        self.assertEqual(client.title, "macav2metdata.nc")
        self.assertEqual(client.credits, "NKN Northwest Knowledge Network")
        self.assertEqual(client.version, "1.0.1")

        # Hard-coded base field values

        self.assertEqual(client.feature_info_formats, ["image/png", "text/xml"])
        self.assertEqual(client.layer_drawing_limit, 1)
        self.assertEqual(client.spatial_ref.srs, "EPSG:3857")

        # Derived from service fields

        self.assertEqual(client.data_size, "231.9 Mbytes")
        self.assertEqual(client.data_format, "netCDF")
        self.assertEqual(client.data_type, "GRID")
        self.assertEqual(client.download_url, self.download_url)
        self.assertEqual(client.modified_date, "2017-04-28T17:32:01Z")
        self.assertEqual(client.wms_version, "1.3.0")

        self.assertEqual(len(client._services), 3)
        self.assertEqual(client._services["http"], {
            "name": "http", "service_type": "HTTPServer", "base": "/thredds/fileServer/"
        })
        self.assertEqual(client._services["iso"], {"name": "iso", "service_type": "ISO", "base": "/thredds/iso/"})
        self.assertEqual(client._services["wms"], {"name": "wms", "service_type": "WMS", "base": "/thredds/wms/"})

        # Derived from layer and metadata fields

        self.assertEqual(client.access_constraints, "northwestknowledge.net")
        self.assertEqual(client.description, "Downscaled daily meteorological data of Precipitation from Average.")
        self.assertEqual(
            client.full_extent.as_list(),
            [-13889573.693873862, 2883446.5788958766, -7465511.412678699, 6342327.290465648]
        )
        self.assertEqual(client.full_extent.spatial_reference.wkid, 3857)
        self.assertEqual(client.keywords, [
            "daily precipitation", "daily maximum temperature", "daily minimum temperature", "latitude", "longitude"
        ])
        self.assertEqual(client.spatial_resolution, (
            "0.041666666666666664 degrees_east by 0.041666666666666664 degrees_north"
        ))

        self.assertEqual(client.styles, [])

        # Private URL fields

        dataset_path = self.dataset_path.split("/")

        self.assertEqual(client._file_path, ["thredds", "fileServer"] + dataset_path)
        self.assertEqual(client._iso_path, ["thredds", "iso"] + dataset_path)
        self.assertEqual(client._wms_path, ["thredds", "wms"] + dataset_path)

        self.assertEqual(client._catalog_url, self.catalog_url.replace(".xml", ".html"))
        self.assertEqual(client._service_url, self.catalog_url)

        wms_url = ThreddsResource.to_wms_url(self.catalog_url)
        self.assertEqual(get_base_url(wms_url, True), self.base_wms_url)
        self.assertEqual(url_to_parts(wms_url).query, url_to_parts(self.wms_service_url).query)

        self.assertEqual(client._wms_url, self.base_wms_url)
        self.assertEqual(client._layers_url, self.layer_menu_url)
        self.assertEqual(
            client._layers_url_format,
            self.base_wms_url + "?item=layerDetails&layerName={layer_id}&request=GetMetadata"
        )
        self.assertEqual(client._metadata_url, self.metadata_url)

        # Test layer level information for first child layer

        first_layer = client.layers[0]

        self.assertEqual(first_layer.id, self.layer_name)
        self.assertEqual(first_layer.title, self.layer_name)
        self.assertEqual(first_layer.description, "Precipitation")
        self.assertEqual(first_layer.version, "1.0.1")

        self.assertEqual(
            Extent(first_layer.full_extent).as_list(),
            [-13889573.693873862, 2883446.5788958766, -7465511.412678699, 6342327.290465648]
        )
        self.assertEqual(first_layer.full_extent.spatial_reference.wkid, 3857)

        self.assertEqual(first_layer.layer_order, 0)
        self.assertEqual(first_layer.wms_version, "1.3.0")
        self.assertEqual(len(first_layer.styles), 3)
        self.assertEqual(len(first_layer.styles[0]), 5)
        self.assertEqual(first_layer.styles[0]["id"], "boxfill/ferret")
        self.assertEqual(first_layer.styles[0]["title"], "Ferret")
        self.assertEqual(first_layer.styles[0]["abstract"], None)
        self.assertEqual(first_layer.styles[0]["colors"], ["#CC00FF", "#00994D", "#FFFF00", "#FF0000", "#990000"])
        self.assertEqual(first_layer.styles[0]["legendURL"], self.legend_url)

        self.assertEqual(first_layer.dimensions, {"id": self.layer_name, "title": "Precipitation", "units": "float"})

        # Test NcWMS specific layer level information

        self.assertEqual(first_layer.credits, "NKN Northwest Knowledge Network")
        self.assertEqual(first_layer.copyright_text, "northwestknowledge.net")
        self.assertEqual(first_layer.more_info, "annual precipitation")
        self.assertEqual(first_layer.num_color_bands, 9)
        self.assertEqual(first_layer.log_scaling, False)
        self.assertEqual(first_layer.scale_range, ["26.0", "75.0"])
        self.assertEqual(len(first_layer.legend_info), 4)
        self.assertEqual(first_layer.legend_info["colorBands"], 9)
        self.assertEqual(first_layer.legend_info["legendUnits"], "inches")
        self.assertEqual(first_layer.legend_info["logScaling"], False)
        self.assertEqual(first_layer.legend_info["scaleRange"], ["26.0", "75.0"])
        self.assertEqual(first_layer.units, "inches")
        self.assertEqual(first_layer.default_style, "boxfill/ferret")
        self.assertEqual(first_layer.default_palette, "ferret")
        self.assertEqual(first_layer.palettes, ["greens", "greys", "ferret"])
        self.assertEqual(first_layer.supported_styles, ["boxfill", "contour"])

    @requests_mock.Mocker()
    @mock.patch("clients.thredds.get_remote_element")
    def test_valid_thredds_image_request(self, mock_request, mock_metadata):

        self.mock_thredds_client(mock_request, mock_metadata)
        client = ThreddsResource.get(self.catalog_url, lazy=False)

        self.assert_get_image(client, layer_ids=[self.layer_name], style_ids=["ferret"])

        self.assert_get_image(
            client, layer_ids=[self.layer_name], style_ids=["ferret"], params={"version": "1.1.1"}
        )

        extent = get_extent(web_mercator=True)
        extent.xmin -= 10
        extent.xmax += 10

        self.assert_get_image(
            client,
            extent=extent,
            layer_ids=[self.layer_name],
            style_ids=["ferret"],
            time_range="2004-01-01/2004-02-01",
            params={"version": "1.1.1"}
        )

    @requests_mock.Mocker()
    @mock.patch("clients.thredds.get_remote_element")
    def test_invalid_thredds_image_request(self, mock_request, mock_metadata):

        self.mock_thredds_client(mock_request, mock_metadata)
        client = ThreddsResource.get(self.catalog_url, lazy=False)

        valid_image_args = (32, 32, [self.layer_name], ["ferret"])

        # Test with valid params and broken endpoint

        client._session = self.mock_mapservice_session(self.data_directory / "wms" / "service-exception.xml", ok=False)
        with self.assertRaises(HTTPError):
            client.get_image(client.full_extent, *valid_image_args)

        # Test with invalid params but working endpoint

        client._session = self.mock_mapservice_session(
            self.data_directory / "test.png", mode="rb", headers={"content-type": "image/png"}
        )
        extent = get_extent(web_mercator=True)

        with self.assertRaises(ImageError):
            # No layers from which to generate an image
            client.get_image(extent.as_dict(), 100, 100)
        with self.assertRaises(ImageError):
            # Provided styles do not correspond to specified Layers
            client.get_image(extent, 100, 100, layer_ids=["layer1"], style_ids=["style1", "style2"])
        with self.assertRaises(ImageError):
            # Incompatible image format invalid_format
            client.get_image(extent, 100, 100, layer_ids=["layer1"], image_format="invalid_format")

        # Test bad image response

        client._session = self.mock_mapservice_session(
            self.data_directory / "test.html", mode="rb", headers={"content-type": "image/png"}
        )
        with self.assertRaises(ImageError):
            client.get_image(client.full_extent, *valid_image_args)
