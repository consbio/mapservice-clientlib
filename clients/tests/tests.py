from clients.tests.geometry_test import ExtentTestCase
from clients.tests.sciencebase_test import ScienceBaseTestCase
from clients.tests.wms_test import WMSTestCase


class FullGeometryTestCase(ExtentTestCase):
    """ Consolidates all geometry_tests for ease of execution """


class FullScienceBaseTestCase(ScienceBaseTestCase):
    """ Consolidates all sciencebase_tests for ease of execution """


class FullWMSTestCase(WMSTestCase):
    """ Consolidates all wms_tests for ease of execution """
