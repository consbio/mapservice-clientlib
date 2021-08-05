import requests_mock

from unittest import mock
from sciencebasepy import SbSession

from ..sciencebase import SCIENCE_BASE_CONTENT_TYPES
from ..sciencebase import ScienceBaseResource, ScienceBaseSession
from ..exceptions import HTTPError, MissingFields, NoLayers, ValidationError
from ..utils.geometry import Extent

from .utils import ResourceTestCase


def mock_sbsession_login():
    def sbsession_login(self, username, password):
        self._username = username
        self._jossosessionid = f"{username}:{password}"
        return self._jossosessionid
    return sbsession_login


class ScienceBaseTestCase(ResourceTestCase):

    def setUp(self):
        super(ScienceBaseTestCase, self).setUp()

        self.sciencebase_directory = self.data_directory / "sciencebase"

        # ArcGIS-backed endpoints

        arcgis_service_url = "https://www.sciencebase.gov/arcgis/rest/services/Catalog/service/MapServer"

        self.arcgis_item_url = "https://www.sciencebase.gov/catalog/item/arcgis/?format=json"
        self.arcgis_item_path = self.sciencebase_directory / "arcgis-item.json"
        self.arcgis_service_url = f"{arcgis_service_url}?f=json"
        self.arcgis_service_path = self.sciencebase_directory / "arcgis-service.json"
        self.arcgis_service_layer_url = f"{arcgis_service_url}/0/?f=json"
        self.arcgis_service_layer_path = self.sciencebase_directory / "arcgis-service-layer.json"
        self.arcgis_service_layers_url = f"{arcgis_service_url}/layers?f=json"
        self.arcgis_service_layers_path = self.sciencebase_directory / "arcgis-service-layers.json"
        self.arcgis_service_legend_url = f"{arcgis_service_url}/legend/?f=json"
        self.arcgis_service_legend_path = self.sciencebase_directory / "arcgis-service-legend.json"

        self.arcgis_service_data = (
            (self.arcgis_service_url, self.arcgis_service_path),
            (self.arcgis_service_layer_url, self.arcgis_service_layer_path),
            (self.arcgis_service_layers_url, self.arcgis_service_layers_path),
            (self.arcgis_service_legend_url, self.arcgis_service_legend_path)
        )

        # Deprecated endpoints

        self.deprecated_url = "https://www.sciencebase.gov/directory/deprecatedLegacyObj/getObj?objId=val"
        self.deprecated_path = self.sciencebase_directory / "deprecated.json"

        self.josso_url = "https://my.usgs.gov/josso/signon/usernamePasswordLogin.do"

        # WMS-backed endpoints

        wms_service_url = "https://www.sciencebase.gov/catalogMaps/mapping/ows/wms"

        self.wms_item_url = "https://www.sciencebase.gov/catalog/item/wms/?format=json"
        self.wms_item_path = self.sciencebase_directory / "wms-item.json"
        self.wms_service_url = f"{wms_service_url}?version=1.3.0&service=wms&request=getcapabilities"
        self.wms_service_path = self.sciencebase_directory / "wms-service.xml"
        self.wms_service_image_url = f"{wms_service_url}?version=1.3.0&service=wms&request=getcapabilities"
        self.wms_service_image_path = self.sciencebase_directory / "wms-service.xml"

        self.wms_service_data = (
            (self.wms_item_url, self.wms_item_path),
            (self.wms_service_url, self.wms_service_path),
            (self.wms_service_image_url, self.wms_service_image_path),
        )

        # Invalid ScienceBase endpoints

        self.empty_error_url = "https://www.sciencebase.gov/catalog/item/empty/?format=json"
        self.empty_error_path = self.sciencebase_directory / "empty-error.json"

        self.footprint_url = "https://www.sciencebase.gov/catalog/item/footprint/?format=json"
        self.footprint_path = self.sciencebase_directory / "footprint.json"

        self.json_error_url = "https://www.google.com/?format=json"
        self.json_error_path = self.data_directory / "test.html"

        self.message_error_url = "https://www.sciencebase.gov/catalog/item/message/?format=json"
        self.message_error_path = self.sciencebase_directory / "message-error.json"

        self.messages_error_url = "https://www.sciencebase.gov/catalog/item/messages/?format=json"
        self.messages_error_path = self.sciencebase_directory / "messages-error.json"

        self.missing_fields_url = "https://www.sciencebase.gov/catalog/item/missing-fields/?format=json"
        self.missing_fields_path = self.sciencebase_directory / "missing-fields.json"

        self.unpublished_url = "https://www.sciencebase.gov/catalog/item/error/?format=json"
        self.unpublished_path = self.sciencebase_directory / "unpublished.json"

    def mock_service_client(self, mock_request, service_type, token=None):

        if service_type == "error":
            self.mock_mapservice_request(mock_request.get, self.arcgis_item_url, self.arcgis_item_path, ok=False)
            self.mock_mapservice_request(mock_request.get, self.wms_item_url, self.wms_item_path, ok=False)
            self.mock_mapservice_request(mock_request.get, self.empty_error_url, self.empty_error_path, ok=False)
            self.mock_mapservice_request(mock_request.get, self.json_error_url, self.json_error_path, ok=False)
            self.mock_mapservice_request(mock_request.get, self.message_error_url, self.message_error_path, ok=False)
            self.mock_mapservice_request(mock_request.get, self.messages_error_url, self.messages_error_path, ok=False)
            self.mock_mapservice_request(mock_request.get, self.missing_fields_url, self.missing_fields_path)
            self.mock_mapservice_request(mock_request.get, self.footprint_url, self.footprint_path)
            self.mock_mapservice_request(mock_request.get, self.unpublished_url, self.unpublished_path)

        elif service_type == "session":
            self.mock_mapservice_request(mock_request.get, self.arcgis_item_url, self.arcgis_item_path)
            self.mock_mapservice_request(mock_request.get, self.deprecated_url, self.deprecated_path)
            self.mock_mapservice_request(mock_request.get, self.wms_item_url, self.wms_item_path)

        elif service_type == "arcgis":

            # Tests public ScienceBase item with unnecessary ArcGIS credentials
            self.mock_mapservice_request(mock_request.get, self.arcgis_item_url, self.arcgis_item_path)

            url_format = "{url}&token={token}" if token else "{url}"
            for url, path in self.arcgis_service_data:
                self.mock_mapservice_request(mock_request.get, url_format.format(url=url, token=token), path)

        elif service_type == "wms":

            # Tests private ScienceBase item with required WMS credentials
            self.mock_mapservice_request(mock_request.get, self.wms_item_url, self.wms_item_path, ok=False)

            url_format = "{url}&josso={token}" if token else "{url}"
            for url, path in self.wms_service_data:
                self.mock_mapservice_request(mock_request.get, url_format.format(url=url, token=token), path)

        else:
            raise AssertionError(f"Invalid service type: {service_type}")

    def assert_sciencebase_session(self, client, username=None, token=None):
        session = client._session

        self.assertTrue(isinstance(session, SbSession))
        self.assertEqual(session._username, username)
        self.assertEqual(session._jossosessionid, token)
        self.assertTrue(session._session.headers.get("Accept"), SCIENCE_BASE_CONTENT_TYPES)
        self.assertEqual(session._session.params, {"josso": token})

    def test_client_name(self):

        result = ScienceBaseResource.client_name
        self.assertEqual(result, "ScienceBase client")

    def test_service_name(self):

        result = ScienceBaseResource.service_name
        self.assertEqual(result, "ScienceBase service")

    @requests_mock.Mocker()
    def test_invalid_sciencebase_urls(self, mock_request):

        with self.assertRaises(AssertionError):
            self.mock_service_client(mock_request, "nope")

        self.mock_service_client(mock_request, "error")

        # ArcGIS server error
        with self.assertRaises(HTTPError):
            ScienceBaseResource.get(self.arcgis_item_url, lazy=False)

        # WMS server error
        with self.assertRaises(HTTPError):
            ScienceBaseResource.get(self.wms_item_url, lazy=False)

        # Error without a message
        with self.assertRaises(HTTPError):
            ScienceBaseResource.get(self.empty_error_url, lazy=False)

        # JSON content error
        with self.assertRaises(HTTPError):
            ScienceBaseResource.get(self.json_error_url, lazy=False)

        # Specific ScienceBase errors
        with self.assertRaises(MissingFields):
            ScienceBaseResource.get(self.missing_fields_url, lazy=False)
        with self.assertRaises(NoLayers):
            ScienceBaseResource.get(self.footprint_url, lazy=False)
        with self.assertRaises(ValidationError):
            ScienceBaseResource.get(self.unpublished_url, lazy=False)

    @requests_mock.Mocker()
    @mock.patch("clients.sciencebase.SbSession.login", new_callable=mock_sbsession_login)
    def test_valid_sciencebase_sessions(self, mock_request, mock_login):
        self.mock_service_client(mock_request, "session")

        # Test direct session instantiation

        session_json = ScienceBaseSession().get_json(self.deprecated_url)
        self.assertEqual(set(session_json.keys()), {"id", "name", "description"})

        session_json = ScienceBaseSession().get_json(self.arcgis_item_url)
        self.assertEqual(set(session_json.keys()), ARCGIS_ITEM_KEYS)

        session_json = ScienceBaseSession().get_json(self.wms_item_url)
        self.assertEqual(set(session_json.keys()), WMS_ITEM_KEYS)

        # Test session instantiation through ScienceBaseResource

        session_kwargs = {
            "token": "usgs_session.id",
            "username": "usgs_session.uid"
        }

        session = None
        client = ScienceBaseResource.get(self.arcgis_item_url, session=session, **session_kwargs)
        self.assert_sciencebase_session(client, **session_kwargs)

        session = SbSession
        client = ScienceBaseResource.get(self.arcgis_item_url, session=session, **session_kwargs)
        self.assert_sciencebase_session(client, **session_kwargs)

        session = SbSession()
        client = ScienceBaseResource.get(self.arcgis_item_url, session=session, **session_kwargs)
        self.assert_sciencebase_session(client, **session_kwargs)

        session = ScienceBaseSession
        client = ScienceBaseResource.get(self.arcgis_item_url, session=session, **session_kwargs)
        self.assert_sciencebase_session(client, **session_kwargs)

        session = ScienceBaseSession()
        client = ScienceBaseResource.get(self.arcgis_item_url, session=session, **session_kwargs)
        self.assert_sciencebase_session(client, **session_kwargs)

        session = ScienceBaseSession(josso_session_id="usgs_session.id", username="usgs_session.uid")
        client = ScienceBaseResource.get(self.arcgis_item_url, session=session, **session_kwargs)
        self.assert_sciencebase_session(client, **session_kwargs)

    @requests_mock.Mocker()
    def test_invalid_sciencebase_sessions(self, mock_request):
        self.mock_service_client(mock_request, "error")

        with self.assertRaises(HTTPError):
            ScienceBaseSession().get_json(self.empty_error_url)

        with self.assertRaises(HTTPError):
            ScienceBaseSession().get_json(self.message_error_url)

        with self.assertRaises(HTTPError):
            ScienceBaseSession().get_json(self.messages_error_url)

    @requests_mock.Mocker()
    @mock.patch("clients.arcgis.ServerAdmin")
    def test_valid_arcgis_sciencebase_request(self, mock_request, mock_server_admin):
        self.mock_service_client(mock_request, "arcgis", token="arcgis_token")

        mock_server_admin.return_value = mock.Mock(
            token="arcgis_token",
            generate_token=mock.Mock()
        )
        token, username = "usgs_session.id", "usgs_session.uid"
        arcgis_credentials = {
            "username": "arcgis_user",
            "password": "arcgis_pass"
        }

        client = ScienceBaseResource.get(
            self.arcgis_item_url, lazy=False,
            token=token, username=username,
            arcgis_credentials=arcgis_credentials
        )
        self.assertEqual(set(client._required_fields), {
            "id", "title", "body", "provenance", "itemsettings", "tags"
        })

        self.assertEqual(client._token, token)
        self.assertEqual(client._username, username)
        self.assertEqual(client.josso_credentials, {"josso": token, "username": username})
        self.assertEqual(client.arcgis_credentials, {"token": "arcgis_token", "username": "arcgis_user"})

        service_client = client.get_service_client()

        self.assertIs(client.get_service_client(), service_client)
        self.assertEqual(service_client._token, "arcgis_token")
        self.assertEqual(service_client._username, "arcgis_user")
        self.assertEqual(service_client._params.get("token"), "arcgis_token")
        self.assertEqual(service_client.arcgis_credentials, {"token": "arcgis_token", "username": "arcgis_user"})

        self.assertEqual(client.service_version, 10.5)
        self.assertEqual(client.service_version, service_client.version)
        self.assertEqual(client.arcgis_credentials, {"token": "arcgis_token", "username": "arcgis_user"})

        self.assertEqual(client.id, "arcgis_service")
        self.assertEqual(client.title, "Testing ArcGIS Service")
        self.assertEqual(client.version, 10.1)
        self.assertEqual(client.summary, "With reference to white tailed jack rabbit")
        self.assertEqual(client.description, "With reference to white tailed jack rabbit found in Alaska")
        self.assertEqual(client.citation, None)
        self.assertEqual(client.purpose, "")
        self.assertEqual(client.use_constraints, None)

        self.assertEqual(client.parent_id, "parent-folder")
        self.assertEqual(client.has_children, False)

        self.assert_object_field(client.distribution_links, ARCGIS_DIST_LINKS)

        facet_data = client.facets[0].get_data()

        self.assertEqual(len(client.facets), 1)
        self.assertEqual(len(facet_data), 12)
        self.assertEqual(len(facet_data["files"]), 2)
        self.assertEqual(
            Extent(facet_data.get("extent"), spatial_reference="102100").as_list(),
            [-121.861000575342, 44.4967792744768, -115.403665323615, 49.0040515878564]
        )
        self.assert_object_field(client.facets, [{
            "name": "ArcGIS.sd",
            "facet_name": "ArcGIS Service Definition",
            "service_id": "arcgis_service",
            "service_path": "arcgis_service",
            "enabled_services": ["KmlServer", "WMSServer"]
        }])

        self.assertEqual(client.files, [])
        self.assert_object_field(client.links, [{
            "type": "webLink",
            "uri": "https://www.sciencebase.gov/catalog/item/arcgis_service",
            "title": "Product Web-page with Downloadable Files",
            "hidden": False,
            "type_label": None
        }])

        self.assert_object_field(client.provenance, {
            "annotation": "generated using mdTranslator",
            "date_created": "2015-04-15T22:48:33Z",
            "date_updated": "2016-04-08T23:42:46Z"
        })

        self.assertEqual(client.browse_categories, ["Data"])
        self.assertEqual(
            client.browse_types,
            ["ArcGIS Service Definition", "Downloadable", "Map Service", "ArcGIS REST Map Service"]
        )
        self.assertEqual(client.properties, {})
        self.assertEqual(client.system_types, ["Downloadable", "Mappable"])

        self.assertEqual(client.contact_persons, [{"name": "Some Employee"}])
        self.assertEqual(client.contact_orgs, [
            '<a href="mailto:srlcc.info@gmail.com">Southern Rockies Landscape Conservation Cooperative</a>',
            "Southern Rockies Landscape Conservation Cooperative"
        ])
        self.assertEqual(client.originators, ["generated using mdTranslator"])

        self.assertEqual(client.settings.get_data(), ARCGIS_SETTINGS)
        self.assertEqual(client.permissions.get_data(), ARCGIS_SETTINGS["permissions"])
        self.assertEqual(client.private, ARCGIS_SETTINGS["private"])
        self.assertEqual(client.service_token_id, ARCGIS_SETTINGS["service_token_id"])
        self.assertEqual(client.service_type, ARCGIS_SETTINGS["service_type"])
        self.assertEqual(client.service_url, ARCGIS_SETTINGS["service_url"])

        # Private resource properties
        self.assert_object_field(client._contacts, [
            {
                "name": "Southern Rockies Landscape Conservation Cooperative",
                "type": "Publisher",
                "contact_type": "organization",
                "email": "srlcc.info@gmail.com"
            },
            {
                "name": "Southern Rockies Landscape Conservation Cooperative",
                "type": "Lead Organization",
                "contact_type": "organization"
            },
            {
                "name": "Some Employee",
                "type": "Data Owner",
                "contact_type": "person",
                "organization": {"display_text": "Southern Rockies Landscape Conservation Cooperative"}
            },
            {
                "type": "Point of Contact",
                "contact_type": "organization",
                "email": "srlcc.info@gmail.com"
            }
        ])
        self.assert_object_field(client._dates, [{
            "type": "Reported",
            "value": "2016",
            "label": "Date Reported",
        }])

        permissions = client._permissions.get_data()

        self.assertIn("read", permissions)
        self.assertEqual(permissions["read"].get("inherited"), False)
        self.assertEqual(
            permissions["read"].get("access_list"),
            ["USER:bcward@consbio.org", "USER:dani.harvey@consbio.org"]
        )
        self.assertIn("write", permissions)
        self.assertEqual(permissions["write"].get("inherited"), False)
        self.assertEqual(
            permissions["write"].get("access_list"),
            ["USER:bcward@consbio.org", "USER:dani.harvey@consbio.org", "USER:databasinadmin@consbio.org"]
        )

        self.assert_object_field(client._tags, [{"name": "test"}])

    @requests_mock.Mocker()
    def test_valid_arcgis_sciencebase_image_request(self, mock_request):
        self.mock_service_client(mock_request, "arcgis")

        client = ScienceBaseResource.get(self.arcgis_item_url, lazy=False)
        client.get_service_client()._session = self.mock_mapservice_session(
            self.data_directory / "test.png",
            mode="rb",
            headers={"content-type": "image/png"}
        )
        self.assert_get_image(client)

    @requests_mock.Mocker()
    @mock.patch("clients.sciencebase.SbSession.login", new_callable=mock_sbsession_login)
    def test_valid_wms_sciencebase_request(self, mock_request, mock_login):
        username, password = "usgs_user", "usgs_pass"
        token = f"{username}:{password}"

        self.mock_service_client(mock_request, "wms", token=token)

        client = ScienceBaseResource.get(
            self.wms_item_url, lazy=False,
            username=username, password="usgs_pass"
        )

        self.assertEqual(client._token, token)
        self.assertEqual(client._username, username)
        self.assertEqual(client.josso_credentials, {"josso": token, "username": username})

        service_client = client.get_service_client()
        self.assertIs(client.get_service_client(), service_client)
        self.assertEqual(service_client._token, token)
        self.assertEqual(service_client._params.get("josso"), token)
        self.assertEqual(service_client.wms_credentials, {"josso": token, "token_id": "josso"})

        self.assertEqual(client.service_version, "1.3.0")
        self.assertEqual(client.service_version, service_client.version)
        self.assertEqual(client.josso_credentials, {"josso": token, "username": username, "token_id": "josso"})

        title = "Southwestern Willow Flycatcher Focal Area"

        self.assertEqual(client.id, "wms_service")
        self.assertEqual(client.title, title)
        self.assertEqual(client.version, 10.1)
        self.assertEqual(client.summary, f"The {title} represents an area of interest")
        self.assertEqual(
            client.description,
            f"The {title} represents an area of interest pertaining to the southwestern willow flycatcher."
        )
        self.assertEqual(client.citation, f"{title} (WLFW)")
        self.assertEqual(client.purpose, "This dataset is being used as part of the Conservation Blueprint 1.0.")
        self.assertEqual(client.use_constraints, None)

        self.assertEqual(client.parent_id, "parent-folder")
        self.assertEqual(client.has_children, False)

        self.assert_object_field(client.distribution_links, WMS_DIST_LINKS)

        facet_data = client.facets[0].get_data()

        self.assertEqual(len(client.facets), 2)
        self.assertEqual(len(facet_data), 7)
        self.assertEqual(len(facet_data["files"]), 8)
        self.assertEqual(
            Extent(facet_data.get("extent"), spatial_reference="EPSG:5070").as_list(),
            [-121.38976229221491, 29.80333794238641, -104.72940289874478, 39.32228869647462]
        )
        self.assert_object_field(client.facets, [
            {
                "name": "SouthwesternWillowFlycatcher_FocalArea",
                "facet_name": "Shapefile",
                "class_name": "gov.sciencebase.catalog.item.facet.ShapefileFacet",
                "geometry_type": "MultiLineString",
                "native_crs": "EPSG:5070"
            },
            {
                "facet_name": "Citation",
                "class_name": "gov.sciencebase.catalog.item.facet.CitationFacet",
                "citation_type": "vector digital data"
            }
        ])

        self.assert_object_field(client.files, [{
            "name": "SouthwesternWillowFlycatcher_FocalArea_metadata.xml",
            "title": "",
            "content_type": "application/fgdc+xml",
            "size": 10293,
            "date_uploaded": "2015-08-29T17:46:16Z",
            "url": "https://www.sciencebase.gov/catalog/file/get/wms?f=__disk__id",
            "download_uri": "https://www.sciencebase.gov/catalog/file/get/wms?f=__disk__id"
        }])
        self.assertEqual(client.links, [])

        self.assert_object_field(client.provenance, {
            "data_source": "Input directly",
            "date_created": "2015-08-29T17:46:44Z",
            "date_updated": "2015-08-29T17:46:44Z"
        })

        self.assertEqual(client.browse_categories, ["Data", "Publication"])
        self.assertEqual(
            client.browse_types,
            ["Shapefile", "Downloadable", "Map Service", "OGC WMS Layer", "OGC WFS Layer", "Citation"]
        )
        self.assertEqual(client.properties, {"wms_layer_name": "SouthwesternWillowFlycatcher_FocalArea"})
        self.assertEqual(client.system_types, ["Downloadable", "Mappable"])

        self.assertEqual(client.contact_persons, [
            {"name": "Some Person", "email": "person@freshwaterinstitute.org"},
            {"name": "Another Person", "email": "srlcc.info@gmail.com"}
        ])
        self.assertEqual(client.contact_orgs, ["Freshwater Institute"])
        self.assertEqual(client.originators, [
            "Some Person(Freshwater Institute)",
            "Another Person(Freshwater Institute)",
            "Freshwater Institute"
        ])

        self.assertEqual(client.settings.get_data(), WMS_SETTINGS)
        self.assertEqual(client.permissions.get_data(), WMS_SETTINGS["permissions"])
        self.assertEqual(client.private, WMS_SETTINGS["private"])
        self.assertEqual(client.service_token_id, WMS_SETTINGS["service_token_id"])
        self.assertEqual(client.service_type, WMS_SETTINGS["service_type"])
        self.assertEqual(client.service_url, WMS_SETTINGS["service_url"])

        # Private resource properties

        self.assert_object_field(client._contacts, [
            {
                "name": "Some Person",
                "type": "Originator",
                "contact_type": "person",
                "email": "person@freshwaterinstitute.org",
                "job_title": "Senior Environmental Associate",
                "first_name": "Some",
                "middle_name": "Other",
                "last_name": "Person",
                "company": "Freshwater Institute",
                "organization": {"name": "Something Else"}
            },
            {
                "name": "Another Person",
                "type": "Data Owner",
                "contact_type": "person",
                "email": "srlcc.info@gmail.com",
                "organization": {"display_text": "Freshwater Institute"}
            },
            {
                "name": "Freshwater Institute",
                "type": "Lead Organization",
                "contact_type": "organization"
            }
        ])

        self.assertEqual(client._dates, [])
        self.assertEqual(client._permissions, [])

        self.assert_object_field(client._tags, [
            {"type": "Theme", "scheme": "None", "name": "conservation"},
            {"type": "Theme", "scheme": "None", "name": "Southwestern Willow Flycatcher"},
            {"type": "Theme", "scheme": "None", "name": "Focal Area"},
            {"type": "Theme", "scheme": "None", "name": "WLFW"}
        ])

    @requests_mock.Mocker()
    def test_valid_wms_sciencebase_image_request(self, mock_request):
        self.mock_service_client(mock_request, "wms")

        client = ScienceBaseResource.get(self.wms_item_url, lazy=False)
        client.get_service_client()._session = self.mock_mapservice_session(
            self.data_directory / "test.png",
            mode="rb",
            headers={"content-type": "image/png"}
        )

        # Ensure WMS is public without token
        self.assertEqual(client.private, False)
        self.assertEqual(client.settings.get_data()["private"], False)

        self.assert_get_image(client, layer_ids=["AKCAN_mastersample_50km"], style_ids=["highlight"])


ARCGIS_ITEM_KEYS = {
    "id",
    "body",
    "browseCategories",
    "browseTypes",
    "contacts",
    "dates",
    "distributionLinks",
    "facets",
    "hasChildren",
    "itemSettings",
    "link",
    "locked",
    "parentId",
    "permissions",
    "previewImage",
    "provenance",
    "relatedItems",
    "summary",
    "systemTypes",
    "tags",
    "title",
    "webLinks"
}
ARCGIS_DIST_LINKS = [
    {
        "uri": "https://www.sciencebase.gov/arcgis/rest/services/Catalog/service/MapServer",
        "title": "ArcGIS REST Service",
        "type": "serviceLink",
        "type_label": "Service Link",
        "rel": "alternate",
        "name": "",
        "files": ""
    },
    {
        "uri": "https://www.sciencebase.gov/arcgis/rest/services/Catalog/service/MapServer/kml/mapImage.kmz",
        "title": "KML Service",
        "type": "kml",
        "type_label": "KML Download",
        "rel": "alternate",
        "name": "",
        "files": ""
    },
    {
        "uri": (
            "https://www.sciencebase.gov/arcgis/services/Catalog/service/MapServer/WMSServer"
            "?request=GetCapabilities&service=WMS"
        ),
        "title": "ArcGIS WMS Service",
        "type": "serviceLink",
        "type_label": "Service Link",
        "rel": "alternate",
        "name": "",
        "files": ""
    },
    {
        "uri": "https://www.sciencebase.gov/catalog/file/get/arcgis_service",
        "title": "Download Attached Files",
        "type": "downloadLink",
        "type_label": "Download Link",
        "rel": "alternate",
        "name": "TestingBeaverAr.zip",
        "files": [
            {
                "name": "ArcGIS.sd/ArcGIS.sd",
                "title": "Testing ArcGIS Service",
                "content_type": "x-gis/x-arcgis_service-def",
                "size": 12537004,
            },
            {
                "name": "ArcGIS.sd/thumbnail.png",
                "title": None,
                "content_type": "image/png",
                "size": 11287,
            }
        ]
    }
]
ARCGIS_SETTINGS = {
    "permissions": {
        "read": {
            "user": [
                "bcward@consbio.org",
                "dani.harvey@consbio.org"
            ]
        },
        "write": None,
    },
    "private": True,
    "service_token_id": "token",
    "service_type": "arcgis",
    "service_url": "https://www.sciencebase.gov/arcgis/rest/services/Catalog/service/MapServer"
}

WMS_ITEM_KEYS = {
    "id",
    "body",
    "browseCategories",
    "browseTypes",
    "citation",
    "contacts",
    "distributionLinks",
    "facets",
    "files",
    "hasChildren",
    "itemSettings",
    "link",
    "parentId",
    "previewImage",
    "provenance",
    "purpose",
    "relatedItems",
    "spatial",
    "summary",
    "systemTypes",
    "tags",
    "title"
}
WMS_DIST_LINKS = [
    {
        "uri": (
            "https://www.sciencebase.gov/catalogMaps/mapping/ows/wms"
            "?mode=download&request=kml&service=wms&layers=SouthwesternWillowFlycatcher_FocalArea"
        ),
        "title": "KML Service",
        "type": "kml",
        "type_label": "KML Download",
        "rel": "alternate",
        "name": "",
        "files": ""
    },
    {
        "uri": (
            "https://www.sciencebase.gov/catalogMaps/mapping/ows/wms"
            "?service=wms&request=getcapabilities&version=1.3.0"
        ),
        "title": "ScienceBase WMS Service",
        "type": "serviceCapabilitiesUrl",
        "type_label": "OGC Service Capabilities URL",
        "rel": "alternate",
        "name": "",
        "files": ""
    },
    {
        "uri": (
            "https://www.sciencebase.gov/catalogMaps/mapping/ows/wms"
            "?service=wfs&request=getcapabilities&version=1.0.0"
        ),
        "title": "ScienceBase WFS Service",
        "type": "serviceCapabilitiesUrl",
        "type_label": "OGC Service Capabilities URL",
        "rel": "alternate",
        "name": "",
        "files": ""
    },
    {
        "uri": "https://www.sciencebase.gov/catalog/file/get/wms",
        "title": "Download Attached Files",
        "type": "downloadLink",
        "type_label": "Download Link",
        "rel": "alternate",
        "name": "SouthwesternWil.zip",
        "files": [
            {
                "name": "SouthwesternWillowFlycatcher_FocalArea/SouthwesternWillowFlycatcher_FocalArea.shp",
                "title": "",
                "content_type": "x-gis/x-shapefile",
                "size": 2545048
            },
            {
                "name": "SouthwesternWillowFlycatcher_FocalArea/SouthwesternWillowFlycatcher_FocalArea.dbf",
                "title": "",
                "content_type": "text/plain",
                "size": 1417767
            },
            {
                "name": "SouthwesternWillowFlycatcher_FocalArea/SouthwesternWillowFlycatcher_FocalArea.shx",
                "title": "",
                "content_type": "x-gis/x-shapefile",
                "size": 8332
            },
            {
                "name": "SouthwesternWillowFlycatcher_FocalArea/SouthwesternWillowFlycatcher_FocalArea.prj",
                "title": "",
                "content_type": "text/plain",
                "size": 480
            },
            {
                "name": "SouthwesternWillowFlycatcher_FocalArea/SouthwesternWillowFlycatcher_FocalArea.shp.xml",
                "title": "",
                "content_type": "application/xml",
                "size": 389190
            },
            {
                "name": "SouthwesternWillowFlycatcher_FocalArea/SouthwesternWillowFlycatcher_FocalArea.sbn",
                "title": "",
                "content_type": "x-gis/x-shapefile",
                "size": 10868
            },
            {
                "name": "SouthwesternWillowFlycatcher_FocalArea/SouthwesternWillowFlycatcher_FocalArea.sbx",
                "title": "",
                "content_type": "x-gis/x-shapefile",
                "size": 692
            },
            {
                "name": "SouthwesternWillowFlycatcher_FocalArea/SouthwesternWillowFlycatcher_FocalArea.cpg",
                "title": "",
                "content_type": "text/plain",
                "size": 5
            },
            {
                "name": "SouthwesternWillowFlycatcher_FocalArea_metadata.xml",
                "title": "",
                "content_type": "application/fgdc+xml",
                "size": 10293
            }
        ]
    }
]
WMS_SETTINGS = {
    "permissions": {"read": None, "write": None},
    "private": True,
    "service_token_id": "josso",
    "service_type": "wms",
    "service_url": (
        "https://www.sciencebase.gov/catalogMaps/mapping/ows/wms?service=wms&request=getcapabilities&version=1.3.0"
    )
}
