import copy
import requests

from parserutils.collections import setdefaults
from parserutils.numbers import is_number
from parserutils.strings import ALPHANUMERIC, snake_to_camel
from restle.resources import Resource
from restle.exceptions import HTTPException, MissingFieldException, NotFoundException

from .exceptions import BadExtent, ClientError, ContentError, HTTPError, MissingFields
from .exceptions import NetworkError, ServiceError, ServiceTimeout, UnsupportedVersion
from .utils.geometry import EXTENT_KEYS


DEFAULT_USER_AGENT = "Mozilla/5.0 (compatible; +https://databasin.org)"


class ClientResource(Resource):
    """ Overridden to provide bulk get functionality and to validate version and extents """

    _client_user_agent = DEFAULT_USER_AGENT

    _incoming_casing = "camel"
    _minimum_version = None
    _maximum_version = None

    _session = None
    _layer_session = None

    def __init__(self, **kwargs):

        session = kwargs.pop("session", None)
        if not session:
            session = requests.Session()
            session.headers["User-agent"] = self._client_user_agent

        super(ClientResource, self).__init__(session=session, **kwargs)

        to_camel = self._incoming_casing in {"camel", "pascal"}
        required = [
            snake_to_camel(f.name) if to_camel else f.name
            for f in self._meta.fields if f.required and f.default is None
        ]

        if self._incoming_casing != "pascal":
            self._required_fields = required
        else:
            self._required_fields = [
                # Capitalize only the first letter if Pascal: leave the rest camel-cased
                f[0].upper() + f[1:] if self._incoming_casing == "pascal" else f for f in required
            ]

    @property
    def service_url(self):
        return getattr(self, "_service_url", self._url)

    @service_url.setter
    def service_url(self, value):
        self._service_url = value

    @classmethod
    def bulk_get(cls, url, strict=True, lazy=True, session=None, bulk_key=None, bulk_defaults=None, **kwargs):
        """ Populates a list of resources with only one external map service request """

        self = cls.get(url, strict=strict, lazy=True, session=session, **kwargs)

        try:
            response = self._make_request(url, self._params)
        except requests.exceptions.HTTPError as ex:
            raise HTTPError(
                "The map service did not respond correctly",
                params=self._params, underlying=ex, url=self._url
            )
        except requests.exceptions.Timeout as ex:
            timeout_error = type(ex).__name__  # This may be a Connect or Read timeout
            raise ServiceTimeout(
                f"{timeout_error}: the map service did not respond in time",
                status_code=response.status_code, underlying=ex, url=self._url
            )
        except requests.exceptions.RequestException as ex:
            network_error = type(ex).__name__  # HTTPError is handled above: this represents everything else
            raise NetworkError(
                f"{network_error}: the map service is unavailable",
                underlying=ex, url=self._url
            )

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as ex:
            raise HTTPError(
                f"The map service returned {response.status_code} ({response.reason})",
                params=self._params, status_code=response.status_code, underlying=ex, url=url
            )

        try:
            bulk_data = response.json()
        except ValueError as ex:
            raise ContentError(
                "The map service returned unparsable content",
                params=self._params, underlying=ex, url=self._url
            )

        return cls._bulk_get(self._url, bulk_data, bulk_key.split("."), bulk_defaults=bulk_defaults)

    @classmethod
    def _bulk_get(cls, url, bulk_data, bulk_keys, objects=None, obj=None, fields=None, bulk_defaults=None):
        """
        Recursively iterates over bulk_keys nested in bulk_data, applying accumulated field data to each.
        Values found at the innermost nested levels overwrite values at the same key above, and only values
        matching field names defined in `cls` will be accumulated.

        :param bulk_data: a dict containing potentially nested data (missing values are ignored)
        :param bulk_keys: a list of keys that can be found in bulk_data (missing keys are ignored)
        :param objects: used only in the recursion; accumulates updated resources
        :param obj: used only in the recursion; accumulates any field data at each recursion level
        :param fields: used in recursion to introspect valid cls fields once, but may also be used as a filter
        :param bulk_defaults:
                a field name or list of field names to default to None in the bulk query OR
                a dict of field values or list of them to apply default values to corresponding fields.
                Keys or field names may be dot notated to indicate nested values
                :see: clients.utils.setdefaults

        :return: a list of `cls` instances, updated with accumulated data found at each key level
        """

        def simplify(string_or_strings):
            """ Helper to strip non-alphanumeric characters from field names """

            if not isinstance(string_or_strings, str):
                return [simplify(s) for s in string_or_strings]
            return "".join(x for x in string_or_strings if x in ALPHANUMERIC).lower()

        if objects is None:
            objects = []
        if obj is None:
            obj = {}
        if fields is None:
            fields = {simplify(f.name) for f in cls._meta.fields}

        if not bulk_keys:
            return objects

        bulk_key = bulk_keys.pop(0)
        bulk_data = bulk_data.get(bulk_key, bulk_data)
        bulk_data = bulk_data if isinstance(bulk_data, list) else [bulk_data]

        for data in copy.deepcopy(bulk_data):
            if not data:
                continue
            elif bulk_keys:
                obj.update({k: v for k, v in data.items() if simplify(k) in fields})
                cls._bulk_get(url, data, list(bulk_keys), objects, obj, fields, bulk_defaults)
            else:
                if isinstance(data, dict):
                    data.update(obj)
                else:
                    data = {bulk_key: data}

                if bulk_defaults is not None:
                    setdefaults(data, bulk_defaults)

                resource = cls()
                resource._url = url
                resource.populate_field_values(data)
                objects.append(resource)

        return objects

    @classmethod
    def get(cls, url, strict=True, lazy=True, session=None, **kwargs):
        """ Overridden to capture strict and lazy settings in the instance """

        # Call lazily first for initialization only
        self = super(ClientResource, cls).get(url, strict=strict, lazy=True, session=session)
        self._lazy = lazy
        self._strict = strict
        self._layer_session = kwargs.pop("layer_session", None)

        self.service_url = self._url

        self._get(url, strict=strict, lazy=lazy, session=session, **kwargs)

        if not self._lazy:
            self._load_resource()  # Load now that initialization is complete

        return self

    def _get(self, url, **kwargs):
        """ Override in children to implement pre-load functionality after instance creation in get """

    def _load_resource(self, as_unicode=True):
        """ Overridden to customize clients exception handling """

        try:
            if as_unicode:
                super(ClientResource, self)._load_resource()
            else:
                # Call with response.content to try ASCII serialization

                response = self._make_request(self._url, self._params)
                self.populate_field_values(self._meta.deserializer.to_dict(response.content))

        except ClientError:
            raise  # Prevents double wrapping errors that inherit from types handled below

        except (HTTPException, NotFoundException, requests.exceptions.HTTPError) as ex:
            status_code = getattr(getattr(ex, "response", None), "status_code", None)

            if status_code in (401, 403):
                if status_code == 401:
                    message = "The map service requires authentication"
                else:
                    message = "The map service cannot be accessed"

                raise ServiceError(
                    message, status_code=status_code, underlying=ex, url=self._url
                )
            raise HTTPError(
                "The map service did not respond correctly",
                params=self._params, underlying=ex, url=self._url
            )
        except requests.exceptions.Timeout as ex:
            timeout_error = type(ex).__name__  # This may be a Connect or Read timeout
            raise ServiceTimeout(
                f"{timeout_error}: the map service did not respond in time",
                status_code=response.status_code, underlying=ex, url=self._url
            )
        except requests.exceptions.RequestException as ex:
            network_error = type(ex).__name__  # HTTPError and timeouts are handled above: this is anything else
            raise NetworkError(
                f"{network_error}: the map service is unavailable",
                underlying=ex, url=self._url
            )
        except (SyntaxError, ValueError) as ex:
            # Handles invalid JSON or XML content
            raise ContentError(
                "The map service returned unparsable content",
                params=self._params, underlying=ex, url=self._url
            )

        except UnicodeEncodeError:
            if not as_unicode:
                raise  # Already tried ASCII (response.content)
            self._load_resource(as_unicode=False)

    def _make_request(self, url, params=None, **kwargs):
        """ Encapsulates adding Data Basin user-agent to header for all requests """

        headers = kwargs.pop("headers", self._session.headers)
        headers["User-agent"] = self._client_user_agent

        response = self._session.get(url, params=params, headers=headers, **kwargs)
        response.raise_for_status()

        return response

    def populate_field_values(self, data):
        """ Overridden to define custom API for all resources, and validate Extent """

        try:
            super(ClientResource, self).populate_field_values(data)
        except MissingFieldException as ex:
            to_camel = self._incoming_casing in {"camel", "pascal"}
            present = set((snake_to_camel(k) if to_camel else k).lower() for k in data)
            missing = [m for m in self._required_fields if m.lower() not in present]

            raise MissingFields(
                "The map service is missing required fields",
                missing=missing, underlying=ex, url=self._url
            )

        self.validate_version()
        self.validate_extent()

    def get_image(self, extent, width, height, **kwargs):
        class_name = self.__class__.__name__
        raise NotImplementedError(f"{class_name}.get_image")

    def validate_extent(self):
        """ Validates extent data dereferenced from standard extent properties """

        for extent_attr in ("extent", "full_extent", "initial_extent"):
            extent = getattr(self, extent_attr, None)

            if extent is None:
                continue
            elif isinstance(extent, dict):
                coords = (extent.get(key) for key in EXTENT_KEYS)
            else:
                coords = (getattr(extent, key, None) for key in EXTENT_KEYS)

            if any(not is_number(coord) for coord in coords):
                raise BadExtent("Invalid extent coordinates", extent=extent, url=self._url)

    def validate_version(self):
        """ Validates version against min and max defined on resource """

        invalid, supported = None, None

        if not self.version:
            invalid = "Unavailable"

        elif not is_number(self.version):
            # True for WMS resources: 1.1.1, 1.3.0
            supported = tuple(v for v in (self._minimum_version, self._maximum_version) if v)
            if supported and self.version not in supported:
                invalid = self.version

        elif float(self.version) < float(self._minimum_version or self.version):
            supported = self._minimum_version
            invalid = self.version

        elif float(self.version) > float(self._maximum_version or self.version):
            supported = self._maximum_version
            invalid = self.version

        if invalid:
            raise UnsupportedVersion(
                "The map service version is not supported",
                invalid=invalid, supported=supported, url=self._url
            )
