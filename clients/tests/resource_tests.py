import json

from requests import exceptions
from restle.fields import FloatField, TextField

from clients.exceptions import ContentError, HTTPError, NetworkError
from clients.exceptions import ServiceError, ServiceTimeout, UnsupportedVersion
from clients.query.fields import CommaSeparatedField, DictField, ExtentField
from clients.query.fields import ListField, ObjectField, SpatialReferenceField
from clients.resources import ClientResource

from .utils import ResourceTestCase, get_extent


class ClientResourceTestCase(ResourceTestCase):

    def setUp(self):
        super(ClientResourceTestCase, self).setUp()

        self.clients_directory = self.data_directory / "resources"

        self.client_url = "https://test.client.org/single/"
        self.client_path = self.clients_directory / "test-client.json"
        self.bulk_url = "https://test.client.org/bulk/"
        self.bulk_path = self.clients_directory / "test-client-bulk.json"
        self.bulk_key_url = "https://test.client.org/bulk_keys/"
        self.bulk_key_path = self.clients_directory / "test-client-bulk-keys.json"
        self.min_url = "https://test.client.org/invalid_min/"
        self.min_path = self.clients_directory / "test-invalid-min.json"
        self.max_url = "https://test.client.org/invalid_max/"
        self.max_path = self.clients_directory / "test-invalid-max.json"
        self.not_json_url = "https://test.client.org/invalid_json/"
        self.not_json_path = self.clients_directory / "test-invalid-json.html"

    def assert_bulk_clients(self, clients):

        self.assertEqual(len(clients), 3)

        client = clients[0]

        self.assertEqual(client._minimum_version, 10)
        self.assertEqual(client._supported_versions, (10.2, 30, 40.5))
        self.assertEqual(client.id, "first")
        self.assertEqual(client.version, 10.2)
        self.assertEqual(client.comma_separated, ["one", "two", "three"])
        self.assertEqual(client.dict_field, {"a": "aaa", "b": "bbb", "c": "ccc"})
        self.assertEqual(
            client.extent.as_list(),
            [-180.0, -90.0, 180.0, 90.0]
        )
        self.assertEqual(client.extent.spatial_reference.srs, "EPSG:4326")
        self.assertEqual(client.list_field, ["ddd", "eee", "fff"])

        self.assert_object_field(client.object_field, {
            "type": "object",
            "prop": "val",
            "method": "callable",
            "parent": {
                "type": "object",
                "prop": "inherited"
            },
            "children": [
                {"type": "specialized"},
                {"type": "aggregated"}
            ]
        })

        self.assertEqual(client.spatial_reference.srs, "EPSG:4326")
        self.assertEqual(client.spatial_reference.wkid, 4326)
        self.assertEqual(client.spatial_reference.latest_wkid, "4326")

        client = clients[1]

        self.assertEqual(client._minimum_version, 10)
        self.assertEqual(client._supported_versions, (10.2, 30, 40.5))
        self.assertEqual(client.id, "second")
        self.assertEqual(client.version, 40.5)
        self.assertEqual(client.comma_separated, ["four", "five", "six"])
        self.assertEqual(client.dict_field, {"x": "xxx", "y": "yyy", "z": "zzz"})
        self.assertEqual(
            client.extent.as_list(),
            [-20037508.342789244, -20037471.205137067, 20037508.342789244, 20037471.20513706]
        )
        self.assertEqual(client.extent.spatial_reference.srs, "EPSG:3857")
        self.assertEqual(client.list_field, ["ttt", "uuu", "vvv"])

        self.assert_object_field(client.object_field, {
            "type": "parent",
            "prop": "inhertiable",
            "parent": None,
            "children": [{
                "type": "object",
                "prop": "val",
                "method": "callable",
                "children": [
                    {"type": "specialized"},
                    {"type": "aggregated"}
                ]
            }]
        })

        self.assertEqual(client.spatial_reference.srs, "EPSG:3857")
        self.assertEqual(client.spatial_reference.wkid, 3857)
        self.assertEqual(client.spatial_reference.latest_wkid, "3857")

        client = clients[2]

        self.assertEqual(client._minimum_version, 10)
        self.assertEqual(client._supported_versions, (10.2, 30, 40.5))
        self.assertEqual(client.id, None)
        self.assertEqual(client.version, 30)
        self.assertEqual(client.comma_separated, None)
        self.assertEqual(client.dict_field, {})
        self.assertEqual(client.extent, None)
        self.assertEqual(client.list_field, [])
        self.assertEqual(client.object_field, None)
        self.assertEqual(client.spatial_reference, None)

    def mock_bulk_session(self, data_path, mode="r", ok=True, headers=None):
        session = self.mock_mapservice_session(data_path, mode, ok, headers)

        response = session.get.return_value
        response.json.return_value = json.loads(response.text)

        return session

    def test_valid_bulk_get(self):

        # Test without bulk keys (flat JSON array)
        session = self.mock_bulk_session(self.bulk_path)
        self.assert_bulk_clients(TestClientResource.bulk_get(self.bulk_url, session=session))

        # Test with bulk keys (nested JSON array)
        session = self.mock_bulk_session(self.bulk_key_path)
        self.assert_bulk_clients(TestClientResource.bulk_get(self.bulk_key_url, bulk_key="objects", session=session))

    def test_invalid_bulk_get(self):

        # Test server error (500)

        session = self.mock_bulk_session(self.bulk_path, ok=False)
        with self.assertRaises(HTTPError):
            TestClientResource.bulk_get(self.bulk_url, session=session)

        # Test invalid JSON response

        session = self.mock_bulk_session(self.bulk_path)
        session.get.return_value.json.side_effect = ValueError

        with self.assertRaises(ContentError):
            TestClientResource.bulk_get(self.bulk_url, session=session)

        # Test all other explicitly handled exceptions

        session = self.mock_bulk_session(self.bulk_path)

        session.get.side_effect = exceptions.Timeout
        with self.assertRaises(ServiceTimeout):
            TestClientResource.bulk_get(self.bulk_url, session=session)

        session.get.side_effect = exceptions.RequestException
        with self.assertRaises(NetworkError):
            TestClientResource.bulk_get(self.bulk_url, session=session)

    def test_valid_load_resource(self):
        session = self.mock_mapservice_session(self.client_path)
        client = TestClientResource.get(self.client_url, lazy=False, session=session)

        self.assertEqual(client._minimum_version, 10)
        self.assertEqual(client._supported_versions, (10.2, 30, 40.5))
        self.assertEqual(client.id, "single")
        self.assertEqual(client.version, 10.2)
        self.assertEqual(client.comma_separated, ["one", "two", "three"])
        self.assertEqual(client.dict_field, {"a": "aaa", "b": "bbb", "c": "ccc"})
        self.assertEqual(
            client.extent.as_list(),
            [-180.0, -90.0, 180.0, 90.0]
        )
        self.assertEqual(client.extent.spatial_reference.srs, "EPSG:4326")
        self.assertEqual(client.list_field, ["xxx", "yyy", "zzz"])

        self.assert_object_field(client.object_field, {
            "type": "object",
            "prop": "val",
            "method": "callable",
            "parent": {
                "type": "object",
                "prop": "inherited"
            },
            "children": [
                {"type": "specialized"},
                {"type": "aggregated"}
            ]
        })

        self.assertEqual(client.spatial_reference.srs, "EPSG:4326")
        self.assertEqual(client.spatial_reference.wkid, 4326)
        self.assertEqual(client.spatial_reference.latest_wkid, "4326")

    def test_invalid_load_resource(self):

        # Test server error (500)

        session = self.mock_mapservice_session(self.client_path, ok=False)
        with self.assertRaises(HTTPError):
            TestClientResource.get(self.client_url, lazy=False, session=session)

        # Test invalid JSON response

        session = self.mock_mapservice_session(self.not_json_path)
        session.get.return_value.json.side_effect = ValueError

        with self.assertRaises(ContentError):
            TestClientResource.get(self.not_json_url, lazy=False, session=session)

        # Test service errors for unauthorized and permission denied

        session = self.mock_mapservice_session(self.client_path, ok=False)

        for status_code in (401, 403):
            session.get.return_value.status_code = status_code
            with self.assertRaises(ServiceError):
                TestClientResource.get(self.client_url, lazy=False, session=session)

        # Test all other explicitly handled exceptions

        session = self.mock_mapservice_session(self.client_path)

        session.get.side_effect = exceptions.Timeout
        with self.assertRaises(ServiceTimeout):
            TestClientResource.get(self.client_url, lazy=False, session=session)

        session.get.side_effect = exceptions.RequestException
        with self.assertRaises(NetworkError):
            TestClientResource.get(self.client_url, lazy=False, session=session)

        session.get.side_effect = UnicodeEncodeError("ascii", r"\x00\x00", 1, 2, "invalid bytes")
        with self.assertRaises(UnicodeEncodeError):
            TestClientResource.get(self.client_url, lazy=False, session=session)

    def test_get_image(self):
        session = self.mock_mapservice_session(self.client_path)

        client = TestClientResource.get(self.client_url, lazy=False, session=session)
        with self.assertRaises(NotImplementedError):
            client.get_image(get_extent(), 32, 32)

        session = self.mock_bulk_session(self.bulk_path)
        for client in TestClientResource.bulk_get(self.bulk_url, session=session):
            with self.assertRaises(NotImplementedError):
                client.get_image(get_extent(), 32, 32)

    def test_validate_version(self):

        session = self.mock_mapservice_session(self.min_path)
        with self.assertRaises(UnsupportedVersion):
            TestClientResource.get(self.min_url, lazy=False, session=session)

        session = self.mock_mapservice_session(self.max_path)
        with self.assertRaises(UnsupportedVersion):
            TestClientResource.get(self.max_url, lazy=False, session=session)


class TestClientResource(ClientResource):

    # TODO: add the following to Meta
    _incoming_casing = "camel"
    _minimum_version = 10
    _supported_versions = (10.2, 30, 40.5)

    id = TextField(required=False)
    version = FloatField(default=30)

    comma_separated = CommaSeparatedField(required=False)
    dict_field = DictField(default={})
    extent = ExtentField(required=False)
    list_field = ListField(default=[])
    object_field = ObjectField(class_name="Field", required=False)
    spatial_reference = SpatialReferenceField(required=False)

    class Meta:
        case_sensitive_fields = False
        match_fuzzy_keys = True