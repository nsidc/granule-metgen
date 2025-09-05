import re
from unittest.mock import MagicMock, patch

import pytest

from nsidc.metgen import constants
from nsidc.metgen.readers import netcdf_reader

# Unit tests for the 'netcdf_reader' module functions.
#
# The test boundary is the netcdf_reader module's interface with the filesystem
# so in addition to testing the netcdf_reader module's behavior, the tests
# should mock those module's functions and assert that netcdf_reader functions
# call them with the correct parameters, correctly handle their return values,
# and handle any exceptions they may throw.


@pytest.fixture
def xdata():
    return list(range(0, 6, 2))


@pytest.fixture
def ydata():
    return list(range(0, 25, 5))


@pytest.fixture
def big_xdata():
    return list(range(0, 20, 2))


@pytest.fixture
def big_ydata():
    return list(range(0, 50, 5))


def test_large_grids_are_thinned(big_xdata, big_ydata):
    result = netcdf_reader.thinned_perimeter(big_xdata, big_ydata)
    assert len(result) == (constants.DEFAULT_SPATIAL_AXIS_SIZE * 4) - 3


def test_perimeter_is_closed_polygon(xdata, ydata):
    result = netcdf_reader.thinned_perimeter(xdata, ydata)
    assert result[0] == result[-1]


def test_no_other_duplicate_values(big_xdata, big_ydata):
    result = netcdf_reader.thinned_perimeter(big_xdata, big_ydata)
    result_set = set(result)
    assert len(result_set) == len(result) - 1


def test_shows_bad_filename():
    with patch("xarray.open_dataset", side_effect=Exception("oops")):
        with pytest.raises(Exception) as exc_info:
            netcdf_reader.extract_metadata(
                "fake.nc", None, None, {}, constants.GEODETIC
            )
        assert re.search("Could not open netCDF file fake.nc", exc_info.value.args[0])


def test_bounding_rectangle_from_geospatial_bounds_valid_polygon():
    """Test parsing valid POLYGON WKT from geospatial_bounds attribute"""
    mock_netcdf = MagicMock()
    mock_netcdf.ncattrs.return_value = ["geospatial_bounds"]
    mock_netcdf.getncattr.return_value = "POLYGON((50.0000 -180.0000,56.2583 -180.0000,56.2583 -155.5594,50.0000 -155.5594,50.0000 -180.0000))"

    result = netcdf_reader.bounding_rectangle_from_geospatial_bounds(mock_netcdf)

    expected = [
        {"Longitude": 50.0, "Latitude": -155.5594},  # upper-left (minx, maxy)
        {"Longitude": 56.2583, "Latitude": -180.0},  # lower-right (maxx, miny)
    ]
    assert result == expected


def test_bounding_rectangle_from_geospatial_bounds_missing_attribute():
    """Test error when geospatial_bounds attribute is missing"""
    mock_netcdf = MagicMock()
    mock_netcdf.ncattrs.return_value = ["other_attr"]

    with pytest.raises(Exception) as exc_info:
        netcdf_reader.bounding_rectangle_from_geospatial_bounds(mock_netcdf)

    assert "geospatial_bounds attribute not found" in str(exc_info.value)


def test_bounding_rectangle_from_geospatial_bounds_invalid_wkt():
    """Test error when WKT string is malformed"""
    mock_netcdf = MagicMock()
    mock_netcdf.ncattrs.return_value = ["geospatial_bounds"]
    mock_netcdf.getncattr.return_value = "INVALID_WKT_STRING"

    with pytest.raises(Exception) as exc_info:
        netcdf_reader.bounding_rectangle_from_geospatial_bounds(mock_netcdf)

    assert "Failed to parse geospatial_bounds WKT" in str(exc_info.value)


def test_bounding_rectangle_from_geospatial_bounds_non_polygon():
    """Test error when WKT geometry is not a POLYGON"""
    mock_netcdf = MagicMock()
    mock_netcdf.ncattrs.return_value = ["geospatial_bounds"]
    mock_netcdf.getncattr.return_value = "POINT(50.0 -180.0)"

    with pytest.raises(Exception) as exc_info:
        netcdf_reader.bounding_rectangle_from_geospatial_bounds(mock_netcdf)

    assert "geospatial_bounds must be a POLYGON, found Point" in str(exc_info.value)


def test_bounding_rectangle_from_latlon_attrs_valid():
    """Test parsing valid lat/lon min/max attributes"""
    mock_netcdf = MagicMock()
    mock_netcdf.ncattrs.return_value = [
        "geospatial_lon_max",
        "geospatial_lat_max",
        "geospatial_lon_min",
        "geospatial_lat_min",
    ]
    mock_netcdf.getncattr.side_effect = lambda attr: {
        "geospatial_lon_max": 56.2583,
        "geospatial_lat_max": -155.5594,
        "geospatial_lon_min": 50.0,
        "geospatial_lat_min": -180.0,
    }[attr]

    result = netcdf_reader.bounding_rectangle_from_latlon_attrs(mock_netcdf)

    expected = [
        {"Longitude": 50.0, "Latitude": -155.5594},  # upper-left
        {"Longitude": 56.2583, "Latitude": -180.0},  # lower-right
    ]
    assert result == expected


def test_bounding_rectangle_from_latlon_attrs_missing():
    """Test error when lat/lon attributes are missing"""
    mock_netcdf = MagicMock()
    mock_netcdf.ncattrs.return_value = ["other_attr"]

    with pytest.raises(Exception) as exc_info:
        netcdf_reader.bounding_rectangle_from_latlon_attrs(mock_netcdf)

    assert "Global attributes for bounding rectangle not available" in str(
        exc_info.value
    )


def test_bounding_rectangle_from_attrs_with_valid_latlon():
    """Test that bounding_rectangle_from_attrs works with lat/lon attributes"""
    mock_netcdf = MagicMock()
    mock_netcdf.ncattrs.return_value = [
        "geospatial_lon_max", "geospatial_lat_max", 
        "geospatial_lon_min", "geospatial_lat_min"
    ]
    # Mock the getncattr calls for lat/lon bounds
    def mock_getncattr(attr):
        attrs = {
            "geospatial_lon_max": 56.0,
            "geospatial_lat_max": -155.0, 
            "geospatial_lon_min": 50.0,
            "geospatial_lat_min": -180.0
        }
        return attrs[attr]
    
    mock_netcdf.getncattr.side_effect = mock_getncattr

    mock_config = MagicMock()

    result = netcdf_reader.bounding_rectangle_from_attrs(mock_netcdf, mock_config)

    expected = [
        {"Longitude": 50.0, "Latitude": -155.0},  # upper-left (lon_min, lat_max)
        {"Longitude": 56.0, "Latitude": -180.0},  # lower-right (lon_max, lat_min)
    ]
    assert result == expected


def test_prefer_geospatial_bounds_false_success():
    """Test that lat/lon attributes are used when prefer_geospatial_bounds=False"""
    mock_netcdf = MagicMock()
    mock_netcdf.ncattrs.return_value = [
        "geospatial_lon_max",
        "geospatial_lat_max",
        "geospatial_lon_min",
        "geospatial_lat_min",
    ]
    mock_netcdf.getncattr.side_effect = lambda attr: {
        "geospatial_lon_max": 56.0,
        "geospatial_lat_max": -155.0,
        "geospatial_lon_min": 50.0,
        "geospatial_lat_min": -180.0,
    }[attr]

    mock_config = MagicMock()
    mock_config.prefer_geospatial_bounds = False

    result = netcdf_reader.bounding_rectangle_from_attrs(mock_netcdf, mock_config)

    expected = [
        {"Longitude": 50.0, "Latitude": -155.0},
        {"Longitude": 56.0, "Latitude": -180.0},
    ]
    assert result == expected


def test_fallback_from_geospatial_bounds_to_latlon():
    """Test fallback from geospatial_bounds to lat/lon when primary fails"""
    mock_netcdf = MagicMock()
    # Mock that geospatial_bounds doesn't exist but lat/lon attrs do
    mock_netcdf.ncattrs.return_value = [
        "geospatial_lon_max",
        "geospatial_lat_max",
        "geospatial_lon_min",
        "geospatial_lat_min",
    ]
    mock_netcdf.getncattr.side_effect = lambda attr: {
        "geospatial_lon_max": 56.0,
        "geospatial_lat_max": -155.0,
        "geospatial_lon_min": 50.0,
        "geospatial_lat_min": -180.0,
    }[attr]

    mock_config = MagicMock()
    mock_config.prefer_geospatial_bounds = True

    with patch("nsidc.metgen.readers.netcdf_reader.logging.getLogger"):
        result = netcdf_reader.bounding_rectangle_from_attrs(mock_netcdf, mock_config)

    expected = [
        {"Longitude": 50.0, "Latitude": -155.0},
        {"Longitude": 56.0, "Latitude": -180.0},
    ]
    assert result == expected


def test_bounding_rectangle_from_attrs_missing_latlon():
    """Test that bounding_rectangle_from_attrs raises exception when lat/lon attrs missing"""
    mock_netcdf = MagicMock()
    # Mock that lat/lon attrs don't exist
    mock_netcdf.ncattrs.return_value = ["geospatial_bounds"]

    mock_config = MagicMock()

    with pytest.raises(Exception) as exc_info:
        netcdf_reader.bounding_rectangle_from_attrs(mock_netcdf, mock_config)
    
    assert "Cannot find geospatial lat/lon bounding attributes" in str(exc_info.value)


def test_spatial_values_geodetic_prefers_geospatial_bounds():
    """Test that spatial_values uses geospatial_bounds for geodetic when prefer_geospatial_bounds=True"""
    mock_netcdf = MagicMock()
    mock_netcdf.ncattrs.return_value = ["geospatial_bounds"]
    mock_netcdf.getncattr.return_value = (
        "POLYGON((50.0 -180.0,56.0 -180.0,56.0 -155.0,50.0 -155.0,50.0 -180.0))"
    )

    mock_config = MagicMock()
    mock_config.prefer_geospatial_bounds = True

    # Mock the grid mapping functions that would be called for coordinate transformation
    with (
        patch("nsidc.metgen.readers.netcdf_reader.find_grid_mapping_var") as mock_grid_var,
        patch("nsidc.metgen.readers.netcdf_reader.crs_transformer") as mock_transformer,
        patch("nsidc.metgen.readers.netcdf_reader.pixel_padding") as mock_padding,
        patch("nsidc.metgen.readers.netcdf_reader.find_coordinate_data_by_standard_name") as mock_coord_data,
    ):
        result = netcdf_reader.spatial_values(mock_netcdf, mock_config, constants.GEODETIC)

    expected = [
        {"Longitude": 50.0, "Latitude": -155.0},
        {"Longitude": 56.0, "Latitude": -180.0},
    ]
    assert result == expected


def test_config_attribute_missing_defaults_to_false():
    """Test that missing prefer_geospatial_bounds attribute defaults to False"""
    mock_netcdf = MagicMock()
    mock_netcdf.ncattrs.return_value = [
        "geospatial_lon_max",
        "geospatial_lat_max",
        "geospatial_lon_min",
        "geospatial_lat_min",
    ]
    mock_netcdf.getncattr.side_effect = lambda attr: {
        "geospatial_lon_max": 56.0,
        "geospatial_lat_max": -155.0,
        "geospatial_lon_min": 50.0,
        "geospatial_lat_min": -180.0,
    }[attr]

    mock_config = MagicMock()
    # Simulate missing attribute by having getattr return default
    mock_config.prefer_geospatial_bounds = None

    result = netcdf_reader.bounding_rectangle_from_attrs(mock_netcdf, mock_config)

    expected = [
        {"Longitude": 50.0, "Latitude": -155.0},
        {"Longitude": 56.0, "Latitude": -180.0},
    ]
    assert result == expected
