# mapservice-clientlib

[![Build Status](https://travis-ci.com/consbio/mapservice-clientlib.png?branch=main)](https://travis-ci.com/consbio/mapservice-clientlib)
[![Coverage Status](https://coveralls.io/repos/github/consbio/mapservice-clientlib/badge.svg?branch=main)](https://coveralls.io/github/consbio/mapservice-clientlib?branch=main)


A library to make web service calls to map service REST APIs easier. Currently supported:

* ArcGIS (version 10.1 and greater)
* THREDDS
* WMS / NcWMS (versions 1.1.1 and 1.3.0)
* ScienceBase

Each leverages the [restle](https://github.com/consbio/restle) library to represent queried map service data as Python objects.
Each also provides some default functionality for rendering projected map service data as images, which may be overridden per class as needed.

Beyond this are some utilities for working with images (PIL) and extents (mostly Geographic, Web Mercator and other proj4 compatible projections).

## Installation

Install with `pip install mapservice-clientlib`.


## Usage

Below are some examples of each supported map service web API standard:


### ArcGIS Resources

ArcGIS Map, Feature and Image services may be queried.

```python
from clients.arcgis import MapServerResource, ArcGISSecureResource
from clients.arcgis import FeatureLayerResource, FeatureServerResource, ImageServerResource
from clients.utils.geometry import Extent


# Query the feature service, or an individual layer (lazy=False: query executed right away)
client = FeatureServerResource.get(service_url, lazy=False)
layer = FeatureLayerResource.get(service_url + "/0", lazy=False)

# Query an image service lazily (default behavior: executes query on property reference)
client = ImageServerResource.get(service_url, lazy=True)
client.extent  # Query executes here

# Query a map service and generate an image
arcgis_image = MapServerResource.get(service_url).get_image(
    extent, width=400, height=200,
    layers="show:0",
    layer_defs="<arcgis_layer_defs>",
    time="<arcgis_time_val>",
    custom_renderers={}  # Renderer JSON
)

# Query a secure map service (generates token from URL and credentials)
client = MapServerResource.get(service_url, username="user", password="pass")

# Query a secure map service with existing token
token_obj = ArcGISSecureResource.generate_token(
    service_url, "user", "pass",  duration=15
)
client = MapServerResource.get(service_url, token=token_obj.token)

# Reproject an ArcGIS extent to Web Mercator
old_extent = Extent(
    {'xmin': -180.0000, 'xmax': 180.0000, 'ymin': -90.0000, 'ymax': 90.0000},
    spatial_reference={'wkid': 4326}
)
geometry_url = 'http://tasks.arcgisonline.com/arcgis/rest/services/Geometry/GeometryServer'
client = GeometryServiceClient(geometry_url)
extent = client.project_extent(old_extent, {'wkid': 3857}).limit_to_global_extent()
```


### WMS

WMS services may be queried, with support for NcWMS

```python
from clients.wms import WMSResource


# Query a secure WMS service
client = WMSResource.get(
    url=wms_url, token="token", token_id="josso", version="1.3.0", spatial_ref="EPSG:3857"
)

# Query a public WMS service and generate an image (supports NcWMS as well)
wms_image = WMSResource.get(
    wms_url
).get_image(
    extent, width=400, height=200,
    layer_ids=[...],
    style_ids=[...],
    time_range="<wms_time_val>",
    params={...},  # Additional image params
    image_format="png"
)
```


### THREDDS

THREDDS resources may be queried, with metadata from related WMS endpoint:

```python
from clients.thredds import ThreddsResource


client = ThreddsResource.get(url)

# See gis-metadata-parser for more
metadata = client._metadata_parser
metadata.data_credits
metadata.use_constraints

# Makes a WMS image request
thredds_image = client.get_image(
    extent, width, height,
    layer_ids=[...],
    style_ids=[...],
    time_range="<wms_time_val>",
    params={...},  # Additional image params
    image_format="png"
)
```


### ScienceBase

Public and private ScienceBase items may be queried:

```python
from clients.sciencebase import ScienceBaseResource, ScienceBaseSession


# Query a public ScienceBase item
client = ScienceBaseResource.get(service_url, lazy=False)
client.summary

# Query a private WMS-backed ScienceBase item

sb_session = ScienceBaseSession(
    josso_session_id="token",
    username="sciencebase_user"
)
sb_session.login("sciencebase_user", "pass")

client = ScienceBaseResource.get(
    url=service_url,
    lazy=False,
    session=sb_session,
    # Same token for WMS as for base item
    token=sb_session._jossosessionid
)
client.service_client.full_extent  # WMSResource.full_extent

# Query a private ArcGIS-backed ScienceBase item

sb_session = ScienceBaseSession(
    josso_session_id="token",
    username="sciencebase_user"
)
sb_session.login("sciencebase_user", "pass")

client = ScienceBaseResource.get(
    url=service_url,
    lazy=False,
    session=sb_session,
    token=sb_session._jossosessionid,
    # Separate credentials for ArcGIS service
    arcgis_credentials={
        # Or just use "token": "existing_token"
        "username": "arcgis_user",
        "password": "arcgis_pass"
    }
)
client.service_client.full_extent  # ArcGISResource.full_extent
```


### Extent Utilities

Extent objects have a number of useful methods. Here are some examples that support projection:

```python
from clients.utils.geometry import Extent


extent_from_dict = Extent({
    "xmin": -180.0, "ymin": -90.0, "xmax": 180.0, "ymax": 90.0,
    "spatial_reference": {"wkid": 4326}
})
web_mercator_extent = extent_from_dict.project_to_web_mercator()

extent_from_list = Extent(
    # In order of xmin, ymin, xmax, ymax
    [-20037508.342789244, -20037471.205137067, 20037508.342789244, 20037471.20513706],
    spatial_reference="EPSG:3857"
)
geographic_extent = extent_from_dict.project_to_geographic()
```
