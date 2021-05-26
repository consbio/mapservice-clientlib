import requests_mock

from hashlib import md5
from unittest import mock

from clients.exceptions import ClientError, ImageError
from clients.utils.geometry import Extent
from clients.thredds import ThreddsResource

from .utils import ResourceTestCase, get_extent


class THREDDSTestCase(ResourceTestCase):

    def setUp(self):
        super(THREDDSTestCase, self).setUp()

        base_url = "http://thredds.northwestknowledge.net:8080/thredds"
        service_path = "NWCSC_INTEGRATED_SCENARIOS_ALL_CLIMATE/projections/macav2metdata/DATABASIN"
        dataset_path = f"{service_path}/macav2metdata.nc"
        layer_name = "macav2metdata_pr_ANN_20702099_rcp45_20CMIP5ModelMean"

        self.download_url = f"{base_url}/fileServer/{dataset_path}"

        self.catalog_url = f"{base_url}/catalog/{service_path}/catalog.xml?dataset={dataset_path}"
        self.catalog_path = self.data_directory / "thredds" / "thredds-catalog.xml"

        self.metadata_url = f"{base_url}/iso/{dataset_path}?dataset={dataset_path}"
        self.metadata_path = self.data_directory / "thredds" / "thredds-metadata.xml"

        self.service_url = f"{base_url}/wms/{dataset_path}?service=WMS&version=1.3.0&request=GetCapabilities"
        self.service_path = self.data_directory / "thredds" / "thredds-wms.xml"

        self.layer_menu_url = f"{base_url}/wms/{dataset_path}?item=menu&request=GetMetadata"
        self.layer_menu_path = self.data_directory / "thredds" / "thredds-layers.json"

        self.layer_url = (
            f"{base_url}/wms/{dataset_path}?item=layerDetails&layerName={layer_name}&request=GetMetadata"
        )
        self.layer_path = self.data_directory / "thredds" / "thredds-layer.json"
        self.layer_name = layer_name

        self.legend_url = (
            f"{base_url}/wms/{dataset_path}?palette=ferret"
            f"&request=GetLegendGraphic&layer={layer_name}&colorbaronly=True"
        )

    def mock_thredds_client(self, mock_request, mock_metadata):
        with open(self.metadata_path) as iso_metadata:
            mock_metadata.return_value = iso_metadata.read()

        mock_request.head(self.download_url, status_code=200)

        self.mock_mapservice_get(self.catalog_path, mock_request, self.catalog_url)
        self.mock_mapservice_get(self.metadata_path, mock_request, self.metadata_url)
        self.mock_mapservice_get(self.service_path, mock_request, self.service_url)
        self.mock_mapservice_get(self.layer_path, mock_request, self.layer_url)
        self.mock_mapservice_get(self.layer_menu_path, mock_request, self.layer_menu_url)

    def test_invalid_thredds_url(self):
        session = self.mock_mapservice_session(self.data_directory / "test.html")

        with self.assertRaises(ClientError):
            ThreddsResource.get("http://www.google.com/test", session=session, lazy=False)

    @requests_mock.Mocker()
    @mock.patch('clients.thredds.get_remote_element')
    def test_valid_thredds_request(self, mock_request, mock_metadata):
        self.mock_thredds_client(mock_request, mock_metadata)

        client = ThreddsResource.get(self.catalog_url, lazy=False)

        self.assertEqual(client.id, "NWCSC_IS_ALL_SCAN/projections/macav2metdata/DATABASIN/macav2metdata.nc")
        self.assertEqual(client.title, "macav2metdata.nc")
        self.assertEqual(client.credits, "northwestknowledge.net")
        self.assertEqual(client.version, "1.0.1")
        self.assertEqual(client.is_ncwms, True)

        # Hard-coded base field values

        self.assertEqual(client.feature_info_formats, ["image/png", "text/xml"])
        self.assertEqual(client.layer_drawing_limit, 1)
        self.assertEqual(client.spatial_ref, "EPSG:3857")

        # Derived from service fields

        self.assertEqual(client.data_size, "231.9 Mbytes")
        self.assertEqual(client.data_format, "netCDF")
        self.assertEqual(client.data_type, "GRID")
        self.assertEqual(client.download_url, self.download_url)
        self.assertEqual(client.modified_date, "2017-04-28T17:32:01Z")
        self.assertEqual(client.wms_version, "1.1.1")

        self.assertEqual(len(client._services), 3)
        self.assertEqual(client._services["http"], {
            "name": "http", "service_type": "HTTPServer", "base": "/thredds/fileServer/"
        })
        self.assertEqual(client._services["iso"], {"name": "iso", "service_type": "ISO", "base": "/thredds/iso/"})
        self.assertEqual(client._services["wms"], {"name": "wms", "service_type": "WMS", "base": "/thredds/wms/"})

        # Derived from layer and metadata fields

        self.assertEqual(client.access_constraints, "")
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

        self.assertEqual(first_layer.is_ncwms, True)
        self.assertEqual(first_layer.layer_order, 0)
        self.assertEqual(first_layer.wms_version, "1.1.1")
        self.assertEqual(len(first_layer.styles), 3)
        self.assertEqual(len(first_layer.styles[0]), 5)
        self.assertEqual(first_layer.styles[0]["id"], "boxfill/ferret")
        self.assertEqual(first_layer.styles[0]["title"], "Ferret")
        self.assertEqual(first_layer.styles[0]["abstract"], None)
        self.assertEqual(first_layer.styles[0]["colors"], ["#CC00FF", "#00994D", "#FFFF00", "#FF0000", "#990000"])
        self.assertEqual(first_layer.styles[0]["legendURL"], self.legend_url)

        self.assertEqual(first_layer.dimensions, {"id": self.layer_name, "title": "Precipitation", "units": "float"})

        # Test NcWMS specific layer level information

        self.assertEqual(first_layer.credits, "")
        self.assertEqual(first_layer.copyright_text, "")
        self.assertEqual(first_layer.more_info, "")
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
    @mock.patch('clients.thredds.get_remote_element')
    def test_valid_thredds_image_request(self, mock_request, mock_metadata):
        self.mock_thredds_client(mock_request, mock_metadata)

        client = ThreddsResource.get(self.catalog_url, lazy=False)
        client._session = self.mock_mapservice_session(
            self.data_directory / "test.png", mode="rb", headers={"content-type": "image/png"}
        )
        img = client.get_image(client.full_extent, 32, 32, [self.layer_name], ["ferret"])

        self.assertEqual(img.size, (32, 32))
        self.assertEqual(img.mode, "RGBA")
        self.assertEqual(md5(img.tobytes()).hexdigest(), "93d44c4c38607ac0834c68fc2b3dc92b")

    @requests_mock.Mocker()
    @mock.patch('clients.thredds.get_remote_element')
    def test_invalid_thredds_image_request(self, mock_request, mock_metadata):
        self.mock_thredds_client(mock_request, mock_metadata)

        client = ThreddsResource.get(self.catalog_url, lazy=False)
        client._session = self.mock_mapservice_session(
            self.data_directory / "wms" / "service-exception.xml"
        )

        extent = get_extent(web_mercator=True)

        with self.assertRaises(ImageError):
            # No layers from which to generate an image
            client.get_image(extent.as_dict(), 100, 100)
        with self.assertRaises(ImageError):
            # Failed image request (service exception)
            client.get_image(extent, 100, 100, layer_ids=["layer1"])
        with self.assertRaises(ImageError):
            # Provided styles do not correspond to specified Layers
            client.get_image(extent, 100, 100, layer_ids=["layer1"], style_ids=["style1", "style2"])
        with self.assertRaises(ImageError):
            # Incompatible image format invalid_format
            client.get_image(extent, 100, 100, layer_ids=["layer1"], image_format="invalid_format")
