# mapservice-clientlib

[![Build Status](https://travis-ci.org/consbio/mapservice-clientlib.png?branch=main)](https://travis-ci.org/consbio/mapservice-clientlib)
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

# Query a secure map service
token_obj = ArcGISSecureResource.generate_token(
    service_url, "user", "pass",  duration=15
)
client = MapServerResource.get(
    service_url, username="user", password="pass", token=token_obj.token
)

# Reproject an ArcGIS extent to web mercator
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

# Query a WMS service and generate an image (supports NcWMS as well)
client = WMSResource.get(url=wms_url, version="1.3.0", spatial_ref="EPSG:3857")
wms_image = client.get_image(
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
from clients.thredds import WMSResource

client = ThreddsResource.get(url=self.import_obj.mapservice.public_url)
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

# Query a public ScienceBase service
client = ScienceBaseResource.get(service_url, lazy=False)
client.summary

# Query a private ScienceBase service

sb_session = ScienceBaseSession(
    josso_session_id="token",
    username="sciencebase_user"
)
sb_session.login("sciencebase_user", "pass")

client = ScienceBaseResource.get(
    url=service_url,
    token=sb_session._jossosessionid,
    session=sb_session,
    lazy=False
)
```
