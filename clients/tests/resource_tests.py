import json

from requests import exceptions
from restle.fields import FloatField, TextField

from ..exceptions import ContentError, HTTPError, NetworkError
from ..exceptions import ServiceError, ServiceTimeout, UnsupportedVersion
from ..query.fields import CommaSeparatedField, DictField, ExtentField
from ..query.fields import ListField, ObjectField, SpatialReferenceField
from ..resources import DEFAULT_USER_AGENT, ClientResource

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

        # Class level constants
        self.assertEqual(client.default_spatial_ref, "EPSG:4326")
        self.assertEqual(client.incoming_casing, "camel")
        self.assertEqual(client.minimum_version, 10)
        self.assertEqual(client.supported_versions, (10.2, 30, 40.5))
        self.assertEqual(client._client_user_agent, DEFAULT_USER_AGENT)
        self.assertEqual(client._session.headers.get("User-agent"), DEFAULT_USER_AGENT)
        self.assertEqual(client._required_fields, [])

        # Instance properties
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

        # Class level constants
        self.assertEqual(client.default_spatial_ref, "EPSG:4326")
        self.assertEqual(client.incoming_casing, "camel")
        self.assertEqual(client.minimum_version, 10)
        self.assertEqual(client.supported_versions, (10.2, 30, 40.5))
        self.assertEqual(client._client_user_agent, DEFAULT_USER_AGENT)
        self.assertEqual(client._session.headers.get("User-agent"), DEFAULT_USER_AGENT)
        self.assertEqual(client._required_fields, [])

        # Instance properties
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

        # Class level constants
        self.assertEqual(client.default_spatial_ref, "EPSG:4326")
        self.assertEqual(client.incoming_casing, "camel")
        self.assertEqual(client.minimum_version, 10)
        self.assertEqual(client.supported_versions, (10.2, 30, 40.5))
        self.assertEqual(client._client_user_agent, DEFAULT_USER_AGENT)
        self.assertEqual(client._session.headers.get("User-agent"), DEFAULT_USER_AGENT)
        self.assertEqual(client._required_fields, [])

        # Instance properties
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

    def test_client_name(self):

        result = TestResource.client_name
        self.assertEqual(result, "custom test client")

        result = TestResource().client_name
        self.assertEqual(result, "custom test client")

    def test_service_name(self):

        result = TestResource.service_name
        self.assertEqual(result, "custom test service")

        result = TestResource().service_name
        self.assertEqual(result, "custom test service")

    def test_valid_bulk_get(self):

        # Test without bulk keys (flat JSON array)
        session = self.mock_bulk_session(self.bulk_path)
        self.assert_bulk_clients(TestResource.bulk_get(self.bulk_url, session=session))

        # Test with bulk keys (nested JSON array)
        session = self.mock_bulk_session(self.bulk_key_path)
        self.assert_bulk_clients(TestResource.bulk_get(self.bulk_key_url, bulk_key="objects", session=session))

    def test_invalid_bulk_get(self):

        # Test server error (500)

        session = self.mock_bulk_session(self.bulk_path, ok=False)
        with self.assertRaises(HTTPError):
            TestResource.bulk_get(self.bulk_url, session=session)

        # Test invalid JSON response

        session = self.mock_bulk_session(self.bulk_path)
        session.get.return_value.json.side_effect = ValueError

        with self.assertRaises(ContentError):
            TestResource.bulk_get(self.bulk_url, session=session)

        # Test all other explicitly handled exceptions

        session = self.mock_bulk_session(self.bulk_path)

        session.get.side_effect = exceptions.Timeout
        with self.assertRaises(ServiceTimeout):
            TestResource.bulk_get(self.bulk_url, session=session)

        session.get.side_effect = exceptions.RequestException
        with self.assertRaises(NetworkError):
            TestResource.bulk_get(self.bulk_url, session=session)

    def test_valid_load_resource(self):
        session = self.mock_mapservice_session(self.client_path)
        client = TestResource.get(self.client_url, lazy=False, session=session)

        # Class level constants
        self.assertEqual(client.default_spatial_ref, "EPSG:4326")
        self.assertEqual(client.incoming_casing, "camel")
        self.assertEqual(client.minimum_version, 10)
        self.assertEqual(client.supported_versions, (10.2, 30, 40.5))
        self.assertEqual(client._client_user_agent, DEFAULT_USER_AGENT)
        self.assertEqual(client._required_fields, [])

        # Instance properties
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
            TestResource.get(self.client_url, lazy=False, session=session)

        # Test invalid JSON response

        session = self.mock_mapservice_session(self.not_json_path)
        session.get.return_value.json.side_effect = ValueError

        with self.assertRaises(ContentError):
            TestResource.get(self.not_json_url, lazy=False, session=session)

        # Test service errors for unauthorized and permission denied

        session = self.mock_mapservice_session(self.client_path, ok=False)

        for status_code in (401, 403):
            session.get.return_value.status_code = status_code
            with self.assertRaises(ServiceError):
                TestResource.get(self.client_url, lazy=False, session=session)

        # Test all other explicitly handled exceptions

        session = self.mock_mapservice_session(self.client_path)

        session.get.side_effect = exceptions.Timeout
        with self.assertRaises(ServiceTimeout):
            TestResource.get(self.client_url, lazy=False, session=session)

        session.get.side_effect = exceptions.RequestException
        with self.assertRaises(NetworkError):
            TestResource.get(self.client_url, lazy=False, session=session)

        session.get.side_effect = UnicodeEncodeError("ascii", r"\x00\x00", 1, 2, "invalid bytes")
        with self.assertRaises(UnicodeEncodeError):
            TestResource.get(self.client_url, lazy=False, session=session)

    def test_get_image(self):
        session = self.mock_mapservice_session(self.client_path)

        client = TestResource.get(self.client_url, lazy=False, session=session)
        with self.assertRaises(NotImplementedError):
            client.get_image(get_extent(), 32, 32)

        session = self.mock_bulk_session(self.bulk_path)
        for client in TestResource.bulk_get(self.bulk_url, session=session):
            with self.assertRaises(NotImplementedError):
                client.get_image(get_extent(), 32, 32)

    def test_validate_version(self):

        # Test minimum version support

        session = self.mock_mapservice_session(self.min_path)
        client = TestResource.get(
            self.min_url, lazy=False, session=session, bypass_version=True
        )
        self.assertEqual(client.id, "invalid_min")
        self.assertEqual(client.version, 9.9)

        with self.assertRaises(UnsupportedVersion):
            TestResource.get(self.min_url, lazy=False, session=session)

        # Test maximum version support

        session = self.mock_mapservice_session(self.max_path)
        client = TestResource.get(
            self.min_url, lazy=False, session=session, bypass_version=True
        )
        self.assertEqual(client.id, "invalid_max")
        self.assertEqual(client.version, 70.8)

        with self.assertRaises(UnsupportedVersion):
            TestResource.get(self.max_url, lazy=False, session=session)


class TestResource(ClientResource):

    default_spatial_ref = "EPSG:4326"
    incoming_casing = "camel"
    minimum_version = 10
    supported_versions = (10.2, 30, 40.5)

    id = TextField(required=False)
    version = FloatField(default=30)

    comma_separated = CommaSeparatedField(required=False)
    dict_field = DictField(default={})
    extent = ExtentField(required=False)
    list_field = ListField(default=[])
    object_field = ObjectField(class_name="Field", required=False)
    spatial_reference = SpatialReferenceField(required=False)

    _client_descriptor = "custom"

    class Meta:
        case_sensitive_fields = False
        match_fuzzy_keys = True
