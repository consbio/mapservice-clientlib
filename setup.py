import subprocess
import sys

from setuptools import Command, setup


class RunTests(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        errno = subprocess.call([sys.executable, "-m", "unittest", "clients.tests"])
        raise SystemExit(errno)


with open("README.md") as readme:
    long_description = readme.read()


setup(
    name="mapservice-clientlib",
    description="Library to query mapservices including ArcGIS, THREDDS, WMS and ScienceBase",
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords="arcgis,thredds,ncwms,wms,sciencebase,geospatial,gis,mapservice,map service,clients,mapservice_clientlib",
    version="2.3.0",
    packages=["clients", "clients.query", "clients.utils"],
    install_requires=[
        "gis-metadata-parser>=2.0",
        "parserutils>=2.0.1",
        "restle>=0.5.1",
        "Pillow>=9.5",
        "pyproj==2.6.1",
        "python-ags==0.3.2",
        "sciencebasepy==2.*",
    ],
    tests_require=["mock", "requests-mock"],
    url="https://github.com/consbio/mapservice-clientlib",
    license="BSD",
    cmdclass={"test": RunTests},
)
