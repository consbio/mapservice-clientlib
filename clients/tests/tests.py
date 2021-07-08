from .arcgis_tests import ArcGISTestCase
from .sciencebase_tests import ScienceBaseTestCase
from .thredds_tests import THREDDSTestCase
from .wms_tests import WMSTestCase

from .conversion_tests import ConversionTestCase
from .geometry_tests import ExtentTestCase, SpatialReferenceTestCase, TileLevelsTestCase
from .images_tests import ImagesTestCase
from .query_tests import ActionsTestCase, FieldsTestCase, SerializersTestCase
from .resource_tests import ClientResourceTestCase


# class FullClientsTestCase(ArcGISTestCase, ClientResourceTestCase, ScienceBaseTestCase, THREDDSTestCase, WMSTestCase):
#     """ Consolidates all client tests for ease of execution """
#
#
# class FullQueryTestCase(ActionsTestCase, FieldsTestCase, SerializersTestCase):
#     """ Consolidates all field related tests for ease of execution """
#
#
# class FullUtilsTestCase(
#     ConversionTestCase, ExtentTestCase, ImagesTestCase, SpatialReferenceTestCase, TileLevelsTestCase
# ):
#     """ Consolidates all utility tests for ease of execution """
