import re
from unittest.mock import MagicMock, patch

import pytest
from shapely import LinearRing

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


def test_points_from_geospatial_bounds_missing_attribute():
    """Test error when geospatial_bounds attribute is missing"""
    mock_netcdf = MagicMock()
    mock_netcdf.ncattrs.return_value = ["other_attr"]

    with pytest.raises(Exception) as exc_info:
        netcdf_reader.points_from_geospatial_bounds(mock_netcdf)

    assert "geospatial_bounds attribute not found" in str(exc_info.value)


def test_points_from_geospatial_bounds_invalid_wkt():
    """Test error when WKT string is malformed"""
    mock_netcdf = MagicMock()
    mock_netcdf.ncattrs.return_value = ["geospatial_bounds"]
    mock_netcdf.getncattr.return_value = "INVALID_WKT_STRING"

    with pytest.raises(Exception) as exc_info:
        netcdf_reader.points_from_geospatial_bounds(mock_netcdf)

    assert "Failed to parse geospatial_bounds WKT" in str(exc_info.value)


def test_points_from_geospatial_bounds_non_polygon():
    """Test error when WKT geometry is not a POLYGON"""
    mock_netcdf = MagicMock()
    mock_netcdf.ncattrs.return_value = ["geospatial_bounds"]
    mock_netcdf.getncattr.return_value = "POINT(50.0 -180.0)"

    with pytest.raises(Exception) as exc_info:
        netcdf_reader.points_from_geospatial_bounds(mock_netcdf)

    assert "geospatial_bounds must be a POLYGON, found Point" in str(exc_info.value)


def test_points_from_geospatial_bounds_with_crs_transformation():
    """Test coordinate transformation when geospatial_bounds_crs is provided"""
    mock_netcdf = MagicMock()
    mock_netcdf.ncattrs.return_value = ["geospatial_bounds", "geospatial_bounds_crs"]
    # Polygon in Web Mercator coordinates (roughly around London area)
    mock_netcdf.getncattr.side_effect = lambda attr: {
        "geospatial_bounds": "POLYGON((-20000 6700000, -20000 6710000, -10000 6710000, -10000 6700000, -20000 6700000))",
        "geospatial_bounds_crs": "EPSG:3857",
    }[attr]

    result = netcdf_reader.points_from_geospatial_bounds(mock_netcdf)

    # We expect 5 points (4 corners + closing point), all transformed to lat/lon
    assert len(result) == 5
    # Verify structure - all points should have Longitude/Latitude keys
    for point in result:
        assert "Longitude" in point
        assert "Latitude" in point
        # Coordinates should be reasonable lat/lon values (not the original projected coords)
        assert -180 <= point["Longitude"] <= 180
        assert -90 <= point["Latitude"] <= 90
        assert point["Longitude"] != -20000  # Ensure transformation occurred
        assert point["Latitude"] != 6700000  # Ensure transformation occurred

    result_ring = LinearRing((r["Longitude"], r["Latitude"]) for r in result)
    assert result_ring.is_ccw


def test_points_from_geospatial_bounds_no_crs_assumes_epsg4326():
    """Test that missing geospatial_bounds_crs assumes coordinates are already in EPSG:4326"""
    mock_netcdf = MagicMock()
    mock_netcdf.ncattrs.return_value = ["geospatial_bounds"]  # No geospatial_bounds_crs
    mock_netcdf.getncattr.return_value = (
        "POLYGON((50.0 -180.0,56.0 -180.0,56.0 -155.0,50.0 -155.0,50.0 -180.0))"
    )

    result = netcdf_reader.points_from_geospatial_bounds(mock_netcdf)

    # Should return coordinates untransformed but in counter-clockwise order
    expected = [
        {"Longitude": -180.0, "Latitude": 50.0},
        {"Longitude": -155.0, "Latitude": 50.0},
        {"Longitude": -155.0, "Latitude": 56.0},
        {"Longitude": -180.0, "Latitude": 56.0},
        {"Longitude": -180.0, "Latitude": 50.0},
    ]
    assert result == expected


def test_points_from_geospatial_bounds_epsg4326_no_transform():
    """Test that EPSG:4326 CRS does not trigger transformation"""
    mock_netcdf = MagicMock()
    mock_netcdf.ncattrs.return_value = ["geospatial_bounds", "geospatial_bounds_crs"]
    mock_netcdf.getncattr.side_effect = lambda attr: {
        "geospatial_bounds": "POLYGON((50.0 -180.0, 50.0 -155.0, 56.0 -155.0, 56.0 -180.0, 50.0 -180.0))",
        "geospatial_bounds_crs": "EPSG:4326",
    }[attr]

    result = netcdf_reader.points_from_geospatial_bounds(mock_netcdf)

    # Should return coordinates untransformed, no change to order
    expected = [
        {"Longitude": -180.0, "Latitude": 50.0},
        {"Longitude": -155.0, "Latitude": 50.0},
        {"Longitude": -155.0, "Latitude": 56.0},
        {"Longitude": -180.0, "Latitude": 56.0},
        {"Longitude": -180.0, "Latitude": 50.0},
    ]
    assert result == expected


def test_points_from_geospatial_bounds_epsg4326_reversed_to_ccw():
    """Test that points in clockwise order are reversed"""
    mock_netcdf = MagicMock()
    mock_netcdf.ncattrs.return_value = ["geospatial_bounds", "geospatial_bounds_crs"]
    mock_netcdf.getncattr.side_effect = lambda attr: {
        "geospatial_bounds": "POLYGON((50.0 -180.0, 56.0 -180.0, 56.0 155.0, 50.0 155.0, 50.0 -180.0))",
        "geospatial_bounds_crs": "EPSG:4326",
    }[attr]

    result = netcdf_reader.points_from_geospatial_bounds(mock_netcdf)

    # Should return coordinates untransformed, rearranged to counter-clockwise
    expected = [
        {"Longitude": -180.0, "Latitude": 50.0},
        {"Longitude": 155.0, "Latitude": 50.0},
        {"Longitude": 155.0, "Latitude": 56.0},
        {"Longitude": -180.0, "Latitude": 56.0},
        {"Longitude": -180.0, "Latitude": 50.0},
    ]
    assert result == expected
