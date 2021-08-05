import requests

from parserutils.collections import accumulate_items, setdefaults
from parserutils.urls import get_base_url, update_url_params
from restle.fields import BooleanField, NumberField, TextField
from sciencebasepy import SbSession

from .arcgis import ArcGISSecureResource, MapServerResource
from .exceptions import HTTPError, NoLayers, ValidationError
from .resources import ClientResource
from .query.fields import DictField, ListField, ObjectField
from .wms import WMSResource


SCIENCE_BASE_CONTENT_TYPES = "text/html,application/json,application/xhtml+xml,application/xml"
SCIENCE_BASE_TOKEN_IDS = {"arcgis": "token", "wms": "josso"}


def init_sbsession(sbsession, josso_session_id=None, username=None):
    """ Set private variables used in SbSession to reuse active login session """

    sbsession._username = username
    sbsession._session.headers.update({"Accept": SCIENCE_BASE_CONTENT_TYPES})

    if josso_session_id:
        sbsession._jossosessionid = josso_session_id
        sbsession._session.params.update({"josso": josso_session_id})

    return sbsession


class ScienceBaseSession(SbSession, object):
    """
    A client for managing requests against ScienceBase using session management.
    The SbSession class is overridden here so that authentication can be based on the
    session id created when a user logs in with their USGS credentials.
    """

    def __init__(self, josso_session_id=None, username=None):
        """ Overridden to reuse active login credentials without new login """

        super(ScienceBaseSession, self).__init__()
        init_sbsession(self, josso_session_id=josso_session_id, username=username)

    def get_public_url(self, response):
        return self._remove_josso_param(response.url)

    def get_json(self, url, external_id=None):
        """ Overridden to improve error handling """

        url = update_url_params(url, format="json")
        response = self._session.get(url)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as ex:
            try:
                value = response.json()["errors"]
                error = value["message"] if isinstance(value, dict) else value[0]["message"]
            except (IndexError, KeyError, ValueError):
                error = f"ScienceBase denied your request for this item: {external_id}"
            raise HTTPError(error, status_code=response.status_code, underlying=ex, url=url)

        return self._get_json(response, external_id)

    def _get_json(self, response, external_id=None):
        """ Overridden to customize response content for ScienceBase items """

        if "/item/" in response.url:
            return self._get_item_json(response, external_id)

        return super(ScienceBaseSession, self)._get_json(response)

    def _get_item_json(self, response, external_id=None):
        """ Adds derived information to an itemSettings property """

        item_json = super(ScienceBaseSession, self)._get_json(response)
        item_settings = item_json["itemSettings"] = {}

        # Determine privacy and permissions of this ScienceBase item

        item_settings["permissions"] = {"read": {}, "write": {}}

        if "permissions" not in item_json:
            # Permissions will be excluded from response if the requesting account doesn't have WRITE access
            try:
                requests.get(self.get_public_url(response), params={"format": "json"}).raise_for_status()
            except requests.exceptions.HTTPError:
                is_private = True  # Must be private if anonymous GET fails
            else:
                is_private = False
        else:
            item_permissions = item_settings["permissions"]

            read_access_control_list = item_json["permissions"].get("read", {}).get("acl", ["PUBLIC"])
            is_private = "PUBLIC" not in read_access_control_list  # PUBLIC is stripped out by following
            read_access_control_list = (perm.split(":", 1) for perm in read_access_control_list if ":" in perm)
            item_permissions["read"] = accumulate_items((k.lower(), v) for k, v in read_access_control_list)

            write_access_control_list = item_json["permissions"].get("write", {}).get("acl", [])
            write_access_control_list = (perm.split(":", 1) for perm in write_access_control_list if ":" in perm)
            item_permissions["write"] = accumulate_items((k.lower(), v) for k, v in read_access_control_list)

        item_settings["isPrivate"] = is_private

        # Determine service type and url of this ScienceBase item

        service_type, service_url = None, None
        has_valid_layers = False

        if "distributionLinks" in item_json:
            service_types = {dl.get("title"): dl for dl in item_json["distributionLinks"]}

            if "ArcGIS REST Service" in service_types:
                service_type = "arcgis"
                service_url = service_types["ArcGIS REST Service"].get("uri")
                has_valid_layers = True

            elif "ScienceBase WMS Service" in service_types:
                # Defined even when WMS originates outside ScienceBase
                service_type = "wms"
                service_url = service_types["ScienceBase WMS Service"].get("uri")

                files_key = "Download Attached Files"
                if files_key in service_types:
                    # Prevents footprint-only map services: attached files must contain shape or GeoTIFF
                    file_extensions = (f["name"].split(".")[-1] for f in service_types[files_key]["files"])
                    has_valid_layers = any(ext for ext in file_extensions if ext in ("shp", "tif", "tiff"))

        if not service_url:
            raise ValidationError(
                f"The ScienceBase item has not yet been published by ScienceBase: {external_id}",
                url=service_url
            )
        elif not has_valid_layers:
            raise NoLayers(
                f"The ScienceBase item has no valid layers; shapefile or GeoTIFF are required: {external_id}",
                url=service_url
            )

        item_settings["serviceTokenId"] = SCIENCE_BASE_TOKEN_IDS[service_type]
        item_settings["serviceType"] = service_type
        item_settings["serviceUrl"] = service_url

        return item_json


class ScienceBaseResource(ClientResource):

    data_provider_types = (
        # Contact types used to populate the credits field
        "author", "co-investigator", "data owner",
        "lead organization", "originator", "principal investigator"
    )

    id = TextField()
    title = TextField()
    version = NumberField(default=10.1)
    summary = TextField(default="")
    description = TextField(name="body")
    citation = TextField(required=False)
    purpose = TextField(default="")
    use_constraints = TextField(name="rights", required=False)

    parent_id = TextField(required=False)
    has_children = BooleanField(default=False)

    distribution_links = ObjectField(class_name="DistributionLink", name="distributionLinks", default=[])
    facets = ObjectField(required=False, class_name="Facet", aliases={
        "boundingBox": "extent",
        "minX": "xmin",
        "minY": "ymin",
        "maxX": "xmax",
        "maxY": "ymax"
    })
    files = ObjectField(class_name="File", default=[])
    links = ObjectField(name="webLinks", class_name="Link", default=[])
    provenance = ObjectField(class_name="Provenance", aliases={"lastUpdated": "date_updated"})

    browse_categories = ListField(default=[])
    browse_types = ListField(default=[])
    properties = DictField(default={})
    system_types = ListField(default=[])

    contact_persons = ListField(default=[])
    contact_orgs = ListField(default=[])
    originators = ListField(default=[])
    settings = ObjectField(name="itemSettings", class_name="Settings", aliases={"isPrivate": "private"})

    _contacts = ObjectField(name="contacts", class_name="Contact", default=[])
    _dates = ObjectField(name="dates", class_name="Date", default=[], aliases={"dateString": "value"})
    _permissions = ObjectField(name="permissions", class_name="Permission", default=[], aliases={
        "acl": "access_list"
    })
    _tags = ObjectField(name="tags", class_name="Tag")

    _service_client = None

    class Meta:
        case_sensitive_fields = False
        get_parameters = {"format": "json"}
        match_fuzzy_keys = True

    @property
    def full_extent(self):
        """ :return: either the WMS or ArcGIS client's full extent """
        return self.get_service_client().full_extent

    @property
    def service_version(self):
        """ :return: either the WMS or ArcGIS client's version """
        return self.get_service_client().version

    def get_service_client(self):
        """ Instantiates and manages the ArcGIS or WMS client backing the ScienceBase item """

        if self._service_client:
            return self._service_client

        elif self.service_type == "arcgis":
            self._service_client = MapServerResource.get(self.service_url, lazy=True, **self.arcgis_credentials)
            self.arcgis_credentials.update(self._service_client.arcgis_credentials)

        elif self.service_type == "wms":
            self._service_client = WMSResource.get(
                self.service_url, lazy=True, token=self._token, token_id="josso"
            )
            self.josso_credentials.update(self._service_client.wms_credentials)

        if not self._lazy:
            self._service_client._load_resource()

        return self._service_client

    def _get(self, url, username=None, password=None, token=None, **kwargs):
        """
        Overridden to parse external_id from the URL, and to manage ScienceBase credentials.
        ScienceBase requires a USGS token (SbSession._jossosessionid) to access private items.
        Each ScienceBase item is backed by either an ArcGIS or WMS map service.
        A private WMS map service uses the same credentials as the base ScienceBase item,
        while a private ArcGIS map service is accessed by a separate set of credentials.

        :param username: an optional USGS username, required only for private items
        :param password: an optional USGS password, used with a username to generate a token
        :param token: an optional USGS session id, used instead of username/password if provided
        :param arcgis_credentials: an optional dict with username and password, or token for ArcGIS access

        If none of the above are provided, this resource will work only with public ScienceBase items.
        """

        super(ScienceBaseResource, self)._get(url, **kwargs)

        self._external_id = get_base_url(url, True).split("/")[-1]

        # Prepare USGS (josso) session

        session_kwargs = {"josso_session_id": token, "username": username}
        if isinstance(self._session, SbSession):
            self._session = init_sbsession(self._session, **session_kwargs)
        else:
            self._session = ScienceBaseSession(**session_kwargs)

        self._username = username
        self._token = token

        if username and password and not token:
            self._session.login(username, password)
            self._token = self._session._jossosessionid
            self._session._session.params["josso"] = self._token

        self.josso_credentials = {"username": self._username, "josso": self._token}

        # Prepare ScienceBase ArcGIS session

        arcgis_credentials = kwargs.pop("arcgis_credentials", None) or {}

        if arcgis_credentials and not arcgis_credentials.get("token"):
            arcgis_user = arcgis_credentials.get("username")
            arcgis_pass = arcgis_credentials.get("password")

            if arcgis_user and arcgis_pass:
                server_admin = ArcGISSecureResource.generate_token(self._url, arcgis_user, arcgis_pass)
                if server_admin.token:
                    arcgis_credentials["token"] = server_admin.token

        self.arcgis_credentials = {
            "username": arcgis_credentials.get("username"),
            "token": arcgis_credentials.get("token")
        }

    def _load_resource(self):
        """ Overridden to make session handling compatible with SbSession """

        self.populate_field_values(
            self._session.get_json(self._url, self._external_id)
        )

    def populate_field_values(self, data):

        # Ensure particular fields exist as defaults for any files or links before parsing

        if "files" in data:
            file_defaults = ("url", "name", "originalMetadata")
            data["files"] = [setdefaults(f, file_defaults) for f in data["files"]]
        if "webLinks" in data:
            link_defaults = ("uri", "title", "type", "typeLabel")
            data["webLinks"] = [setdefaults(l, link_defaults) for l in data["webLinks"]]

        super(ScienceBaseResource, self).populate_field_values(data)

        # Parse settings object

        self.private = self.settings.private
        self.permissions = self.settings.permissions
        self.service_token_id = self.settings.service_token_id
        self.service_type = self.settings.service_type
        self.service_url = self.settings.service_url

        if self.service_type == "arcgis":
            self.service_token = self.arcgis_credentials["token"]
        else:
            self.service_token = self._token

        # Parse dates from provenance object

        self.created_by = getattr(self.provenance, "created_by", None)
        self.date_created = self.provenance.date_created
        self.date_updated = self.provenance.date_updated

        # Parse originators, contacts and contact orgs

        self.populate_contact_related_fields()

        # Parse dates and tags from raw dates and tags

        dates = ((d.value, d.label or f"{d.type} Date") for d in self._dates if d.value)
        self.dates = [f"{val} ({label})" for val, label in dates]

        self.tags = [tag.name for tag in self._tags if getattr(tag, "name", None)]

        # Parse WMS properties from facets depending on browse types

        if self.service_type == "wms":
            any_facet_has_files = any(getattr(facet, "files", None) for facet in self.facets)
            has_valid_browse_types = {"GeoTIFF", "Shapefile"}.intersection(self.browse_types)

            if any_facet_has_files and has_valid_browse_types:
                # Note: ScienceBase escapes certain characters to underscores for WMS layer names
                facet_names = (facet.name for facet in self.facets if hasattr(facet, "name"))
                self.properties["wms_layer_name"] = next(facet_names).replace("/", "_")

    def populate_contact_related_fields(self, valid_contacts=None):
        """ Populate contact_persons, contact_orgs and originators """

        if valid_contacts is None:
            # Require a name for contacts by default
            valid_contacts = [c.get_data() for c in self._contacts if hasattr(c, "name")]

        # Append contact persons with emails if present

        self.contact_persons = []
        for person in (p for p in valid_contacts if p.get("contact_type") == "person"):
            contact_info = {"name": person.get("name", "")}
            if person.get("email"):
                contact_info["email"] = person["email"]
            self.contact_persons.append(contact_info)

        # Append contact organizations with email link if email is present

        anchor_format = '<a href="mailto:{0}">{1}</a>'

        self.contact_orgs = []
        for org in (o for o in valid_contacts if o.get("contact_type") == "organization"):
            if org.get("name") and org.get("email"):
                self.contact_orgs.append(anchor_format.format(org["email"], org["name"]))
            else:
                self.contact_orgs.append(org.get("email") or org.get("name"))

        # Append originators from provenance annotation if present, or contacts

        self.originators = []

        if hasattr(self.provenance, "annotation"):
            # Use annotations by default: may include free-form text for credits / originators
            self.originators.append(self.provenance.annotation)
        else:
            # Append originators with organization or company names

            originator_contacts = (
                o for o in valid_contacts if (o.get("type") or "").lower() in self.data_provider_types
            )
            for originator in originator_contacts:
                originator_txt = originator["name"]
                if originator.get("organization", {}).get("display_text"):
                    originator_txt += "({})".format(originator["organization"]["display_text"])
                elif originator.get("company"):
                    originator_txt += "({})".format(originator["company"])
                self.originators.append(originator_txt)

    def get_image(self, extent, width, height, **kwargs):
        return self.get_service_client().get_image(extent=extent, width=width, height=height, **kwargs)
