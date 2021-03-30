import unittest

from clients.sciencebase import ScienceBaseResource
from clients.exceptions import ClientError


class ScienceBaseTestCase(unittest.TestCase):

    def test_missing_fields(self):
        with self.assertRaises(ClientError):
            client = ScienceBaseResource.get(
                "https://www.sciencebase.gov/catalog/item/51350807e4b0e1603e4fecfc", lazy=False
            )
            assert client.id == "51350807e4b0e1603e4fecfc"

    def test_invalid_type(self):
        with self.assertRaises(ClientError):
            client = ScienceBaseResource.get(
                "https://www.sciencebase.gov/catalog/item/51cc89ede4b052f2a4539a82", lazy=False
            )
            assert client.id == "51cc89ede4b052f2a4539a82"

    def test_valid_item(self):
        client = ScienceBaseResource.get(
            "https://www.sciencebase.gov/catalog/item/4fc51d73e4b00e9c12d8c389", lazy=False
        )
        assert client.id == "4fc51d73e4b00e9c12d8c389"
