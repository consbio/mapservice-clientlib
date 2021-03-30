import requests

from parserutils.collections import accumulate_items, setdefaults
from parserutils.urls import get_base_url, update_url_params
from restle.fields import BooleanField, NumberField, TextField
from sciencebasepy import SbSession

from .arcgis import ArcGISSecureResource
from .exceptions import ClientError, HTTPError, MissingFields, NoLayers, ValidationError
from .query.fields import DictField, ListField, ObjectField


# List of contact types that we pull out for credits field, since ScienceBase doesn't have the same concept as us.
DATA_PROVIDER_CONTACT_TYPES = (
    "Author", "Co-Investigator", "Data Owner", "Lead Organization", "Originator", "Principal Investigator"
)
SCIENCE_BASE_CONTENT_TYPES = "text/html,application/json,application/xhtml+xml,application/xml"


class ScienceBaseSession(SbSession, object):
    """
    A client for managing requests against ScienceBase using session management.
    The SbSession class is overridden here so that authentication can be based on the
    session id created when a user logs in with their USGS credentials.
    """

    _session_content_types = SCIENCE_BASE_CONTENT_TYPES

    def __init__(self, josso_session_id=None, username=None):
        super(ScienceBaseSession, self).__init__()

        self._session.headers["Accept"] = self._session_content_types
        self.has_session = bool(josso_session_id and username)

        if self.has_session:
            # These are private variables that are used in the parent: SbSession
            self._jossosessionid = josso_session_id
            self._session.params = {"josso": self._jossosessionid}
            self._username = username

    def login(self, username, password):
        super(ScienceBaseSession, self).login(username, password)

        self.has_session = True

    def get_public_url(self, response):
        return self._remove_josso_param(response.url)

    def get_json(self, url, external_id=None):
        """ Overridden to flexibly query ScienceBase items with session """

        url = update_url_params(url, format="json")
        response = (self._session if self.has_session else requests).get(url)

        try:
            response.raise_for_status()
        except ClientError:
            raise  # Prevents double wrapping intentionally raised errors in the catch-all below
        except requests.exceptions.HTTPError as ex:
            try:
                value = response.json()["errors"]
                error = value["message"] if isinstance(value, dict) else value[0]["message"]
            except (IndexError, KeyError, ValueError):
                error = f"ScienceBase denied your request for this item: {external_id}"
            raise HTTPError(error, status_code=response.status_code, underlying=ex, url=url)
        except Exception:
            # SbSession raises a generic exception for status errors (only excepts 200)
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
            error = "The ScienceBase item has not yet been published by ScienceBase: {0}"
            raise ValidationError(f"The ScienceBase item has not yet been published by ScienceBase: {external_id}")
        elif not has_valid_layers:
            error = "The ScienceBase item does not have any valid layers; shapefile or GeoTIFF are required: {}"
            raise NoLayers(error.format(external_id), url=service_url)

        item_settings["serviceType"] = service_type
        item_settings["serviceUrl"] = service_url

        return item_json


class ScienceBaseResource(ArcGISSecureResource):

    data_provider_contact_types = DATA_PROVIDER_CONTACT_TYPES

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

    settings = ObjectField(name="itemSettings", class_name="Settings", aliases={"isPrivate": "private"})

    _contacts = ObjectField(name="contacts", class_name="Contact", default=[])
    _dates = ObjectField(name="dates", class_name="Date", default=[], aliases={"dateString": "value"})
    _permissions = ObjectField(name="permissions", class_name="Permission", default=[], aliases={
        "acl": "access_list"
    })
    _tags = ObjectField(name="tags", class_name="Tag")

    class Meta:
        case_sensitive_fields = False
        get_parameters = {"format": "json"}
        match_fuzzy_keys = True

    def _get(self, url, **kwargs):
        """ Overridden to parse external_id from the URL """

        super(ScienceBaseResource, self)._get(url, **kwargs)
        self._external_id = get_base_url(url, True).strip("/").split("/")[-1]

    def _load_resource(self):
        """ Overridden to make session handling compatible with SbSession """

        if not isinstance(self._session, ScienceBaseSession):
            if isinstance(self._session, type):
                self._session = self._session(josso_session_id=self.token, username=self.username)
            elif self.token and self.username:
                self._session = ScienceBaseSession(josso_session_id=self.token, username=self.username)
            else:
                self._session = ScienceBaseSession()  # Assume a public item

        try:
            self.populate_field_values(self._session.get_json(self._url, self._external_id))
        except ValidationError:
            raise  # Prevents double wrapping validation exceptions, which are also AttributeError
        except (AttributeError, KeyError) as ex:
            # Handles nested property dependencies in both ScienceBaseSession._get_item_json and populate_field_values
            raise MissingFields(
                "The ScienceBase item is missing required fields",
                missing=ex, underlying=ex, url=self._url
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
        self.service_type = self.settings.service_type
        self.service_url = self.settings.service_url

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
                self.properties["wms_layer_name"] = facet_names.next().replace("/", "_")

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

        if hasattr(self.provenance, "annotation"):
            # Use annotations by default: may include free-form text for credits / originators
            self.originators = [self.provenance.annotation]
        else:
            # Append originators with organization or company names

            self.originators = []
            for originator in (o for o in valid_contacts if o.get("type") in self.data_provider_contact_types):
                originator_txt = originator.get("name", "unknown")
                if originator.get("organization", {}).get("display_text"):
                    originator_txt += "({})".format(originator["organization"]["display_text"])
                elif originator.get("company"):
                    originator_txt += "({})".format(originator["company"])
                self.originators.append(originator_txt)
