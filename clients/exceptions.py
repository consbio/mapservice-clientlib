""" A module to define custom exceptions raised specifically in the clients app """

import requests

from parserutils.collections import wrap_value
from restle.exceptions import MissingFieldException


class ClientError(Exception):
    """
    A class to represent the set of specific errors that can occur during a client request,
    with a level of detail sufficient for a caller to generate a user facing message.
    """

    def __init__(self, message, url=None, **kwargs):
        super(ClientError, self).__init__(message)

        self.url = url
        self.underlying = kwargs.get("underlying")
        self.error_context = {} if url is None else {"url": url}
        self.error_context.update({kw: arg for kw, arg in kwargs.items() if arg})


class ContentError(ClientError, requests.exceptions.ContentDecodingError):

    def __init__(self, message, params=None, **kwargs):
        super(ContentError, self).__init__(message, **kwargs)
        self.error_context["params"] = self.params = params


class HTTPError(ClientError, requests.exceptions.HTTPError):

    def __init__(self, message, params=None, status_code=None, **kwargs):
        super(HTTPError, self).__init__(message, **kwargs)

        self.error_context["params"] = self.params = params
        self.error_context["status_code"] = self.status_code = status_code


class NetworkError(ClientError, requests.exceptions.RequestException):
    pass


class ImageError(ClientError):

    def __init__(self, message, params=None, tile_info=None, **kwargs):
        super(ImageError, self).__init__(message, **kwargs)

        self.error_context["params"] = self.params = params
        self.error_context["tile_info"] = self.tile_info = tile_info


class ServiceError(ClientError):
    """ A class to represent a range of service errors differentiated by status code """

    def __init__(self, message, status_code=None, **kwargs):
        super(ServiceError, self).__init__(message, **kwargs)
        self.error_context["status_code"] = self.status_code = status_code


class ServiceTimeout(ServiceError, requests.exceptions.Timeout):
    """ A class to represent server-side timeouts, not client (408) """

    def __init__(self, message, status_code=504, **kwargs):
        super(ServiceTimeout, self).__init__(message, **kwargs)
        self.error_context["status_code"] = self.status_code = status_code


class ValidationError(ClientError, AttributeError):

    def __init__(self, message, **kwargs):
        super(ValidationError, self).__init__(message, **kwargs)


class BadExtent(ValidationError, ValueError):

    def __init__(self, message, extent=None, **kwargs):
        super(BadExtent, self).__init__(message, **kwargs)
        self.error_context["extent"] = self.extent = extent


class BadSpatialReference(BadExtent):

    def __init__(self, message, spatial_reference=None, **kwargs):
        super(BadSpatialReference, self).__init__(message, **kwargs)
        self.error_context["spatial_reference"] = self.spatial_reference = spatial_reference


class BadTileScheme(ValidationError, ValueError):

    def __init__(self, message, tile_info=None, **kwargs):
        super(BadTileScheme, self).__init__(message, **kwargs)
        self.error_context["tile_info"] = self.tile_info = tile_info


class NoLayers(ValidationError):
    pass


class MissingFields(ValidationError, MissingFieldException):

    def __init__(self, message, missing=None, **kwargs):
        super(MissingFields, self).__init__(message, **kwargs)
        self.error_context["missing"] = self.missing = wrap_value(missing)


class UnsupportedVersion(ValidationError):

    def __init__(self, message, invalid=None, supported=None, **kwargs):
        super(UnsupportedVersion, self).__init__(message, **kwargs)

        self.invalid = invalid
        self.supported = wrap_value(supported)
        self.error_context.update({"invalid": self.invalid, "supported": self.supported})
