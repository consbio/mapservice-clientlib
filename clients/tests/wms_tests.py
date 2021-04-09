from hashlib import md5

from clients.exceptions import ClientError, ImageError
from clients.utils.geometry import Extent
from clients.wms import WMSResource

from .utils import BaseTestCase


class WMSTestCase(BaseTestCase):

    def test_invalid_url(self):
        with self.assertRaises(ClientError):
            WMSResource.get("http://www.google.com", lazy=False)  # not a WMS

    def test_invalid_projection(self):
        with self.assertRaises(ClientError):
            WMSResource.get("http://wms.jpl.nasa.gov/wms.cgi", lazy=False)  # svc does not support WMS

    def test_valid_svc_info(self):
        WMSResource.get("http://demo.mapserver.org/cgi-bin/wms", lazy=False)  # valid svc

    def test_valid_image(self):
        client = WMSResource.get("http://demo.mapserver.org/cgi-bin/wms", lazy=False)
        img = client.get_image(client.full_extent, 250, 175, ["country_bounds"], ["default"])
        assert img.size == (250, 175)
        assert img.mode == "RGBA"
        assert md5(img.tobytes()).hexdigest() == "526a075ca774aa2601fe38f191b7b798"  # Note: fails if service changes

    def test_invalid_image_request(self):
        client = WMSResource.get("http://demo.mapserver.org/cgi-bin/wms", lazy=False)

        extent_dict = {"xmin": -1000, "ymin": -1000, "xmax": 1000, "ymax": 1000, "spatial_reference": "EPSG:3857"}
        extent_list = [-1000, -1000, 1000, 1000]

        with self.assertRaises(ImageError):
            client.get_image(Extent(), 100, 100)
        with self.assertRaises(ImageError):
            client.get_image(extent_dict, 100, 100)
        with self.assertRaises(ImageError):
            client.get_image(extent_list, 100, 100, style_ids=["style1"])
        with self.assertRaises(ImageError):
            client.get_image(Extent(extent_dict), 100, 100, layer_ids=["layer1"])
        with self.assertRaises(ImageError):
            client.get_image(
                Extent(extent_list), 100, 100, layer_ids=["layer1"], image_format="invalid_format"
            )
