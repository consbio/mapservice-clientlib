from setuptools import Command, setup


class RunTests(Command):
    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        errno = 0
        raise SystemExit(errno)


with open("README.md") as readme:
    long_description = readme.read()


setup(
    name="mapservice-clients",
    description="Library to query geospatial dataset mapservices including ArcGIS, THREDDS, WMS and ScienceBase",
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords="arcgis,thredds,ncwms,wms,sciencebase,geospatial,gis,mapservice,clients,mapservice_clientlib",
    version="0.1",
    packages=[
        "clients", "clients.tests"
    ],
    install_requires=[
        "gis-metadata-parser", "restle", "Pillow==7.2.*", "pyproj==2.6.1", "python-ags==0.3.2", "sciencebasepy==1.6.4"
    ],
    tests_require=["mock", "pytest", "pytest-cov"],
    url="https://github.com/consbio/mapservice-clients",
    license="BSD",
    cmdclass={"test": RunTests}
)
