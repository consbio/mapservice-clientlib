from clients.utils.geometry import Extent, union_extent


def test_projection():
    original_extent = Extent([-180.0, -90.0, 180.0, 90.0], spatial_reference="EPSG:4326")
    new_extent = original_extent.project_to_web_mercator()
    assert new_extent.as_list() == [-20037508.342789244, -20037471.205137067, 20037508.342789244, 20037471.20513706]
    assert original_extent.spatial_reference.srs == "EPSG:4326"
    # Note: this is equivalent to -180, -85.051, 180, 85.051


def test_union():
    assert union_extent([None, Extent([-180, -90, 180, 90])]).as_list() == [-180, -90, 180, 90]
    assert union_extent([Extent([-180, -90, 180, 90]), None]).as_list() == [-180, -90, 180, 90]
    assert union_extent([Extent([-10, -10, 10, 10]), Extent([-20, -20, 5, 5])]).as_list() == [-20, -20, 10, 10]


def test_corrected_image_extent():
    assert Extent([-180, -90, 180, 90]).fit_to_dimensions(100, 100).as_list() == [-180, -180.0, 180, 180.0]
    assert Extent([-180, -90, 180, 90]).fit_to_dimensions(100, 200).as_list() == [-180, -360.0, 180, 360.0]
    assert Extent([-180, -90, 180, 90]).fit_to_dimensions(200, 100).as_list() == [-180.0, -90, 180.0, 90]


def test_get_scale_string():
    extent = Extent([-180.0, -90.0, 180.0, 90.0], spatial_reference="EPSG:4326")
    image_width = 946
    assert extent.get_scale_string(image_width) == "350 km (220 miles)"

    # Same in web mercator
    extent = Extent(
        [-20037508.342789244, -20037471.205137067, 20037508.342789244, 20037471.20513706],
        spatial_reference="EPSG:3857"
    )
    assert extent.get_scale_string(image_width) == "350 km (220 miles)"
