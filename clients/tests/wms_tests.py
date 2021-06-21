from clients.exceptions import ContentError, HTTPError, ImageError
from clients.wms import WMSResource
from clients.utils.geometry import Extent

from .utils import ResourceTestCase, get_extent


class WMSTestCase(ResourceTestCase):

    def setUp(self):
        super(WMSTestCase, self).setUp()

        self.wms_directory = self.data_directory / "wms"

        self.wms_url = "http://demo.mapserver.org/cgi-bin/wms"
        self.wms_path = self.wms_directory / "ncwms-layer.json"

        self.ncwms_url = "http://tools.pacificclimate.org/ncWMS-PCIC/wms?dataset=pr-tasmax-tasmin_day"
        self.ncwms_path = self.wms_directory / "ncwms-layer.json"

    def assert_ncwms_request(self, data_path, version, token=None):

        is_max_version = (version == "1.3.0")

        headers = {"content-type": "application/json"}
        session = self.mock_mapservice_session(data_path)
        layer_session = self.mock_mapservice_session(self.ncwms_path, headers=headers)

        client = WMSResource.get(
            self.ncwms_url,
            lazy=False, session=session, layer_session=layer_session,
            token=token, version=version
        )

        # Test service level information

        if not token:
            self.assertEqual(client.wms_url, self.ncwms_url)
        else:
            self.assertEqual(client.wms_url, f"{self.ncwms_url}&token={token}")

        self.assertEqual(client.title, "My ncWMS server")
        self.assertEqual(client.description, "")
        self.assertEqual(client.access_constraints, None)

        self.assertEqual(client.version, version)
        self.assertEqual(client.version, client._version)
        self.assertEqual(client._token, token)
        self.assertEqual(client._params.get("token"), token)

        self.assertEqual(client.feature_info_formats, ["image/png", "text/xml"])
        self.assertEqual(client.map_formats, ["image/png", "image/gif", "image/jpeg"])
        self.assertEqual(client.keywords, ["ncwms", "server"])
        self.assertEqual(client.layer_drawing_limit, 1 if is_max_version else None)
        self.assertEqual(
            client.full_extent.as_list(),
            [-15696047.830489751, 5012341.860907214, -5788613.783964222, 18295676.048854332]
        )
        self.assertEqual(client.full_extent.spatial_reference.wkid, 3857)
        self.assertEqual(
            client.supported_spatial_refs,
            ["EPSG:27700", "EPSG:32661", "EPSG:32761", "EPSG:3408", "EPSG:3409", "EPSG:3857", "EPSG:41001"]
        )
        self.assertEqual(client.has_dimensions, True)
        self.assertEqual(client.has_time, True)
        self.assertEqual(client.is_ncwms, True)
        self.assertEqual(client.spatial_ref, "EPSG:3857")

        layer_ids = {"pr-tasmax-tasmin_day"}

        self.assertEqual(len(client.leaf_layers), len(layer_ids))
        self.assertTrue(all(l in layer_ids for l in client.leaf_layers))

        self.assertEqual(len(client.root_layers), 1)
        child_layers = {l for l in client.root_layers[0].child_layers}
        self.assertTrue(all(l.id in layer_ids for l in child_layers))

        ordered_layers = {l for l in client.ordered_layers if l.id}
        self.assertEqual(len(ordered_layers), len(layer_ids))
        self.assertTrue(all(l.id in layer_ids for l in ordered_layers))

        # Test layer level information for first child layer

        first_layer = client.root_layers[0].child_layers[0]

        self.assertEqual(first_layer.id, "pr-tasmax-tasmin_day")
        self.assertEqual(first_layer.title, "precipitation_flux")
        self.assertEqual(first_layer.description, "Precipitation")
        self.assertEqual(first_layer.version, version)
        self.assertEqual(first_layer.supports_query, True)

        if is_max_version:
            self.assertEqual(first_layer._extent, None)
        else:
            self.assertEqual(first_layer._extent["current"], "1")
            self.assertEqual(first_layer._extent["default"], "2021-06-14T00:00:00.000Z")
            self.assertEqual(first_layer._extent["multiple_values"], "1")
            self.assertEqual(first_layer._extent["name"], "time")
            self.assertEqual(
                first_layer._extent["values"],
                "1950-01-01T00:00:00.000Z/2100-12-31T00:00:00.000Z/P1D"
            )

        extent_coords = [-140.99999666399998, 41.000001336, -52.00000235999998, 83.49999861600001]
        spatial_ref = "CRS:84" if is_max_version else "EPSG:4326"

        self.assertEqual(first_layer._spatial_ref, [])
        self.assertEqual(first_layer._coordinate_ref, [])

        if not is_max_version:
            self.assertEqual(first_layer._new_extent, None)
        else:
            self.assertEqual(Extent(first_layer._new_extent).as_list(), extent_coords)
            self.assertEqual(first_layer._new_extent["spatial_reference"], "EPSG:4326")

        self.assertEqual(Extent(first_layer._old_bbox_extent).as_list(), extent_coords)
        self.assertEqual(first_layer._old_bbox_extent["spatial_reference"], spatial_ref)
        self.assertEqual(
            Extent(first_layer.full_extent).as_list(),
            [-15696047.830489751, 5012341.860907214, -5788613.783964222, 18295676.048854332]
        )
        self.assertEqual(first_layer.full_extent.spatial_reference.wkid, 3857)
        self.assertEqual(
            first_layer.supported_spatial_refs,
            ["EPSG:27700", "EPSG:32661", "EPSG:32761", "EPSG:3408", "EPSG:3409", "EPSG:3857", "EPSG:41001"]
        )

        self.assertEqual(first_layer.has_time, True)
        self.assertEqual(first_layer.has_dimensions, True)
        self.assertEqual(first_layer.is_ncwms, True)
        self.assertEqual(first_layer.is_old_version, not is_max_version)
        self.assertEqual(first_layer.layer_order, 1)
        self.assertEqual(first_layer.parent_order, 0)
        self.assertEqual(first_layer._metadata_url, [])
        self.assertEqual(first_layer.metadata_urls, {})

        self.assertEqual(len(first_layer._style), 24)
        self.assertEqual(first_layer._style[0]["id"], "boxfill/alg")
        self.assertEqual(first_layer._style[0]["title"], "boxfill/alg")
        self.assertEqual(first_layer._style[0]["abstract"], "boxfill style, using the alg palette")
        self.assertEqual(first_layer._style[0]["legend_url"]["format"], "image/png")
        self.assertEqual(first_layer._style[0]["legend_url"]["width"], "110")
        self.assertEqual(first_layer._style[0]["legend_url"]["height"], "264")
        self.assertEqual(first_layer._style[0]["legend_url"]["online_resource"]["href"], (
            "http://pizza.pcic.uvic.ca:8080/ncWMS-PCIC/wms?"
            "REQUEST=GetLegendGraphic&LAYER=pr-tasmax-tasmin_day&PALETTE=alg"
        ))
        self.assertEqual(first_layer._style[0]["legend_url"]["online_resource"]["online_resource_type"], "simple")

        self.assertEqual(len(first_layer.styles), 17)
        self.assertEqual(len(first_layer.styles[0]), 5)
        self.assertEqual(first_layer.styles[0]["id"], "boxfill/alg")
        self.assertEqual(first_layer.styles[0]["title"], "Algorithmic")
        self.assertEqual(first_layer.styles[0]["abstract"], None)
        self.assertEqual(first_layer.styles[0]["legendURL"], (
            "http://tools.pacificclimate.org/ncWMS-PCIC/wms"
            "?palette=alg&request=GetLegendGraphic&layer=pr-tasmax-tasmin_day&colorbaronly=True"
        ))

        self.assertEqual(first_layer._attribution, {})
        self.assertEqual(first_layer.attribution, {})

        if not is_max_version:
            self.assertEqual(len(first_layer._dimension), 2)
            self.assertEqual(first_layer._dimension["name"], "time")
            self.assertEqual(first_layer._dimension["units"], "ISO8601")
        else:
            self.assertEqual(len(first_layer._dimension), 6)
            self.assertEqual(first_layer._dimension["current"], "true")
            self.assertEqual(first_layer._dimension["default"], "2021-05-05T00:00:00.000Z")
            self.assertEqual(first_layer._dimension["multiple_values"], "true")
            self.assertEqual(first_layer._dimension["name"], "time")
            self.assertEqual(first_layer._dimension["units"], "ISO8601")
            self.assertEqual(
                first_layer._dimension["values"],
                "1950-01-01T00:00:00.000Z/2100-12-31T00:00:00.000Z/P1D"
            )

        self.assertEqual(len(first_layer.dimensions), 1)
        self.assertEqual(len(first_layer.dimensions["time"]), 6)
        self.assertEqual(first_layer.dimensions["time"]["name"], "time")
        self.assertEqual(first_layer.dimensions["time"]["units"], "ISO8601")
        self.assertEqual(
            first_layer.dimensions["time"]["values"],
            ["1950-01-01T00:00:00.000Z/2100-12-31T00:00:00.000Z/P1D"]
        )
        if is_max_version:
            self.assertEqual(first_layer.dimensions["time"]["current"], "true")
            self.assertEqual(first_layer.dimensions["time"]["default"], "2021-05-05T00:00:00.000Z")
            self.assertEqual(first_layer.dimensions["time"]["multiple_values"], "true")
        else:
            self.assertEqual(first_layer.dimensions["time"]["current"], "1")
            self.assertEqual(first_layer.dimensions["time"]["default"], "2021-06-14T00:00:00.000Z")
            self.assertEqual(first_layer.dimensions["time"]["multiple_values"], "1")

        self.assertEqual(first_layer.child_layers, [])
        self.assertEqual(first_layer.leaf_layers, {})

        # Test NcWMS specific layer level information

        self.assertEqual(first_layer.credits, None)
        self.assertEqual(first_layer.copyright_text, "")
        self.assertEqual(first_layer.more_info, "")
        self.assertEqual(first_layer.num_color_bands, 254)
        self.assertEqual(first_layer.log_scaling, False)
        self.assertEqual(first_layer.scale_range, ["0.0", "797.8125"])
        self.assertEqual(len(first_layer.legend_info), 4)
        self.assertEqual(first_layer.legend_info["colorBands"], 254)
        self.assertEqual(first_layer.legend_info["legendUnits"], "mm day-1")
        self.assertEqual(first_layer.legend_info["logScaling"], False)
        self.assertEqual(first_layer.legend_info["scaleRange"], ["0.0", "797.8125"])
        self.assertEqual(first_layer.units, "mm day-1")
        self.assertEqual(first_layer.default_style, "boxfill/rainbow")
        self.assertEqual(first_layer.default_palette, "rainbow")
        self.assertEqual(first_layer.palettes, [
            "alg", "greyscale", "ncview", "occam", "yellow_red", "red_yellow", "lightblue_darkblue_log", "occam_inv",
            "ferret", "redblue", "brown_green", "blueheat", "brown_blue", "blue_brown", "blue_darkred",
            "lightblue_darkblue", "rainbow"
        ])
        self.assertEqual(first_layer.supported_styles, ["boxfill"])

    def assert_wms_request(self, data_path, version, token=None):

        is_max_version = (version == "1.3.0")

        client = WMSResource.get(
            self.wms_url, lazy=False, session=self.mock_mapservice_session(data_path),
            token=token, version=version
        )

        # Test service level information

        if not token:
            self.assertEqual(client.wms_url, self.wms_url)
        else:
            self.assertEqual(client.wms_url, f"{self.wms_url}?token={token}")

        self.assertEqual(client.title, "WMS Demo Server for MapServer")
        self.assertEqual(client.description, "This demonstration server showcases MapServer")
        self.assertEqual(client.access_constraints, None)

        self.assertEqual(client.version, version)
        self.assertEqual(client.version, client._version)
        self.assertEqual(client._token, token)
        self.assertEqual(client._params.get("token"), token)

        self.assertEqual(client.feature_info_formats, ["text/html", "application/vnd.ogc.gml", "text/plain"])
        self.assertEqual(client.map_formats, ["image/png", "image/jpeg", "application/json"])
        self.assertEqual(client.keywords, ["DEMO", "WMS"])
        self.assertEqual(client.layer_drawing_limit, None)
        self.assertEqual(
            client.full_extent.as_list(),
            [-20037508.342789244, -20037471.205137067, 20037508.342789244, 20037471.20513706]
        )
        self.assertEqual(client.full_extent.spatial_reference.wkid, 3857)
        self.assertEqual(
            client.supported_spatial_refs,
            ["EPSG:3857", "EPSG:3978", "EPSG:4269", "EPSG:4326"]
        )
        self.assertEqual(client.has_dimensions, False)
        self.assertEqual(client.has_time, False)
        self.assertEqual(client.is_ncwms, False)
        self.assertEqual(client.spatial_ref, "EPSG:3857")

        layer_ids = {"continents", "country_bounds", "cities", "bluemarble"}

        self.assertEqual(len(client.leaf_layers), len(layer_ids))
        self.assertTrue(all(l in layer_ids for l in client.leaf_layers))

        self.assertEqual(len(client.root_layers), len(layer_ids))
        self.assertTrue(all(l.id in layer_ids for l in client.root_layers))

        self.assertEqual(len(client.ordered_layers), len(layer_ids))
        self.assertTrue(all(l.id in layer_ids for l in client.ordered_layers))

        # Test layer level information for first layer

        first_layer = client.ordered_layers[0]
        first_layer.styles
        self.assertEqual(first_layer.id, "cities")
        self.assertEqual(first_layer.title, "World cities")
        self.assertEqual(first_layer.description, None)
        self.assertEqual(first_layer.version, version)
        self.assertEqual(first_layer.supports_query, True)

        self.assertEqual(first_layer._extent, None)

        if not is_max_version:
            self.assertEqual(first_layer._spatial_ref, ["EPSG:4326"])
            self.assertEqual(first_layer._coordinate_ref, [])
            self.assertEqual(first_layer._new_extent, None)
        else:
            self.assertEqual(first_layer._spatial_ref, [])
            self.assertEqual(first_layer._coordinate_ref, ["EPSG:4326"])
            self.assertEqual(
                Extent(first_layer._new_extent).as_list(),
                [-178.167, -54.8, 179.383, 78.9333]
            )
            self.assertEqual(first_layer._new_extent["spatial_reference"], "EPSG:4326")

        self.assertEqual(
            Extent(first_layer._old_bbox_extent).as_list(),
            [-178.167, -54.8, 179.383, 78.9333]
        )
        self.assertEqual(first_layer._old_bbox_extent["spatial_reference"], "EPSG:4326")
        self.assertEqual(
            Extent(first_layer.full_extent).as_list(),
            [-19833459.716165174, -7323146.544576741, 19968824.216969796, 14888598.992608657]
        )
        self.assertEqual(first_layer.full_extent.spatial_reference.wkid, 3857)
        self.assertEqual(
            first_layer.supported_spatial_refs,
            ["EPSG:3857", "EPSG:3978", "EPSG:4269", "EPSG:4326"]
        )

        self.assertEqual(first_layer.has_time, False)
        self.assertEqual(first_layer.has_dimensions, False)
        self.assertEqual(first_layer.is_ncwms, False)
        self.assertEqual(first_layer.is_old_version, not is_max_version)
        self.assertEqual(first_layer.layer_order, 0)
        self.assertEqual(first_layer.parent_order, None)

        self.assertEqual(first_layer._metadata_url["format"], "text/xml")
        self.assertEqual(first_layer._metadata_url["metadata_url_type"], "TC211")
        self.assertEqual(
            first_layer._metadata_url["online_resource"]["href"],
            "https://demo.mapserver.org/cgi-bin/wms?request=GetMetadata&layer=cities"
        )
        self.assertEqual(first_layer._metadata_url["online_resource"]["online_resource_type"], "simple")
        self.assertEqual(first_layer.metadata_urls, {
            "TC211": "https://demo.mapserver.org/cgi-bin/wms?request=GetMetadata&layer=cities"
        })

        sld_version = "&sld_version=1.1.0" if is_max_version else ""

        self.assertEqual(first_layer._style["id"], "default")
        self.assertEqual(first_layer._style["title"], "default")
        self.assertEqual(first_layer._style["legend_url"]["format"], "image/png")
        self.assertEqual(first_layer._style["legend_url"]["width"], "192")
        self.assertEqual(first_layer._style["legend_url"]["height"], "41")
        self.assertEqual(first_layer._style["legend_url"]["online_resource"]["href"], (
            f"https://demo.mapserver.org/cgi-bin/wms?version={version}&service=WMS&request=GetLegendGraphic"
            f"{sld_version}&layer=cities&format=image/png&STYLE=default"
        ))
        self.assertEqual(
            first_layer._style["legend_url"]["online_resource"]["online_resource_type"], "simple"
        )

        self.assertEqual(len(first_layer.styles), 1)
        self.assertEqual(len(first_layer.styles[0]), 4)
        self.assertEqual(first_layer.styles[0]["id"], "default")
        self.assertEqual(first_layer.styles[0]["title"], "default")
        self.assertEqual(first_layer.styles[0]["abstract"], None)
        self.assertEqual(first_layer.styles[0]["legendURL"], (
            f"https://demo.mapserver.org/cgi-bin/wms?version={version}&service=WMS&request=GetLegendGraphic"
            f"{sld_version}&layer=cities&format=image/png&STYLE=default"
        ))

        self.assertEqual(first_layer._attribution, {})
        self.assertEqual(first_layer.attribution, {})
        self.assertEqual(first_layer._dimension, [])
        self.assertEqual(first_layer.dimensions, {})

        self.assertEqual(first_layer.child_layers, [])
        self.assertEqual(first_layer.leaf_layers, {})

    def test_invalid_wms_url(self):

        session = self.mock_mapservice_session(self.data_directory / "test.html")

        with self.assertRaises(ContentError):
            WMSResource.get("http://www.google.com", session=session, lazy=False)

    def test_valid_new_ncwms_request(self):
        self.assert_ncwms_request(self.wms_directory / "ncwms-max.xml", version="1.3.0")

    def test_valid_old_ncwms_request(self):
        self.assert_ncwms_request(self.wms_directory / "ncwms-min.xml", version="1.1.1", token="secure")

    def test_valid_new_wms_request(self):
        self.assert_wms_request(self.wms_directory / "demo-wms-max.xml", version="1.3.0", token="secure")

    def test_valid_old_wms_request(self):
        self.assert_wms_request(self.wms_directory / "demo-wms-min.xml", version="1.1.1")

    def test_valid_wms_image_request(self):

        session = self.mock_mapservice_session(self.wms_directory / "demo-wms-max.xml")
        client = WMSResource.get(self.wms_url, session=session, lazy=False)

        self.assert_get_image(client, layer_ids=["country_bounds"], style_ids=["default"])

    def test_invalid_wms_image_request(self):

        session = self.mock_mapservice_session(self.wms_directory / "demo-wms-max.xml")
        client = WMSResource.get(self.wms_url, session=session, lazy=False)

        # Test with valid params and broken endpoint

        client._session = self.mock_mapservice_session(self.wms_directory / "service-exception.xml", ok=False)
        with self.assertRaises(HTTPError):
            client.get_image(client.full_extent, 32, 32, ["country_bounds"], ["default"])

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
