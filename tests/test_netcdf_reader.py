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
