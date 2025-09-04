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


class TestGeospatialBounds:
    """Test cases for geospatial_bounds WKT parsing functionality"""

    def test_bounding_rectangle_from_geospatial_bounds_valid_polygon(self):
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

    def test_bounding_rectangle_from_geospatial_bounds_missing_attribute(self):
        """Test error when geospatial_bounds attribute is missing"""
        mock_netcdf = MagicMock()
        mock_netcdf.ncattrs.return_value = ["other_attr"]

        with pytest.raises(Exception) as exc_info:
            netcdf_reader.bounding_rectangle_from_geospatial_bounds(mock_netcdf)

        assert "geospatial_bounds attribute not found" in str(exc_info.value)

    def test_bounding_rectangle_from_geospatial_bounds_invalid_wkt(self):
        """Test error when WKT string is malformed"""
        mock_netcdf = MagicMock()
        mock_netcdf.ncattrs.return_value = ["geospatial_bounds"]
        mock_netcdf.getncattr.return_value = "INVALID_WKT_STRING"

        with pytest.raises(Exception) as exc_info:
            netcdf_reader.bounding_rectangle_from_geospatial_bounds(mock_netcdf)

        assert "Failed to parse geospatial_bounds WKT" in str(exc_info.value)

    def test_bounding_rectangle_from_geospatial_bounds_non_polygon(self):
        """Test error when WKT geometry is not a POLYGON"""
        mock_netcdf = MagicMock()
        mock_netcdf.ncattrs.return_value = ["geospatial_bounds"]
        mock_netcdf.getncattr.return_value = "POINT(50.0 -180.0)"

        with pytest.raises(Exception) as exc_info:
            netcdf_reader.bounding_rectangle_from_geospatial_bounds(mock_netcdf)

        assert "geospatial_bounds must be a POLYGON, found Point" in str(exc_info.value)

    def test_bounding_rectangle_from_latlon_attrs_valid(self):
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

    def test_bounding_rectangle_from_latlon_attrs_missing(self):
        """Test error when lat/lon attributes are missing"""
        mock_netcdf = MagicMock()
        mock_netcdf.ncattrs.return_value = ["other_attr"]

        with pytest.raises(Exception) as exc_info:
            netcdf_reader.bounding_rectangle_from_latlon_attrs(mock_netcdf)

        assert "Global attributes for bounding rectangle not available" in str(
            exc_info.value
        )


class TestConfigurationDrivenBehavior:
    """Test cases for configuration-driven method selection and fallback"""

    def test_prefer_geospatial_bounds_true_success(self):
        """Test that geospatial_bounds is used when prefer_geospatial_bounds=True"""
        mock_netcdf = MagicMock()
        mock_netcdf.ncattrs.return_value = ["geospatial_bounds"]
        mock_netcdf.getncattr.return_value = (
            "POLYGON((50.0 -180.0,56.0 -180.0,56.0 -155.0,50.0 -155.0,50.0 -180.0))"
        )

        mock_config = MagicMock()
        mock_config.prefer_geospatial_bounds = True

        result = netcdf_reader.bounding_rectangle_from_attrs(mock_netcdf, mock_config)

        expected = [
            {"Longitude": 50.0, "Latitude": -155.0},
            {"Longitude": 56.0, "Latitude": -180.0},
        ]
        assert result == expected

    def test_prefer_geospatial_bounds_false_success(self):
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

    def test_fallback_from_geospatial_bounds_to_latlon(self):
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
            result = netcdf_reader.bounding_rectangle_from_attrs(
                mock_netcdf, mock_config
            )

        expected = [
            {"Longitude": 50.0, "Latitude": -155.0},
            {"Longitude": 56.0, "Latitude": -180.0},
        ]
        assert result == expected

    def test_fallback_from_latlon_to_geospatial_bounds(self):
        """Test fallback from lat/lon to geospatial_bounds when primary fails"""
        mock_netcdf = MagicMock()
        # Mock that lat/lon attrs don't exist but geospatial_bounds does
        mock_netcdf.ncattrs.return_value = ["geospatial_bounds"]
        mock_netcdf.getncattr.return_value = (
            "POLYGON((50.0 -180.0,56.0 -180.0,56.0 -155.0,50.0 -155.0,50.0 -180.0))"
        )

        mock_config = MagicMock()
        mock_config.prefer_geospatial_bounds = False

        with patch("nsidc.metgen.readers.netcdf_reader.logging.getLogger"):
            result = netcdf_reader.bounding_rectangle_from_attrs(
                mock_netcdf, mock_config
            )

        expected = [
            {"Longitude": 50.0, "Latitude": -155.0},
            {"Longitude": 56.0, "Latitude": -180.0},
        ]
        assert result == expected

    def test_both_methods_fail(self):
        """Test error when both primary and fallback methods fail"""
        mock_netcdf = MagicMock()
        mock_netcdf.ncattrs.return_value = ["other_attr"]

        mock_config = MagicMock()
        mock_config.prefer_geospatial_bounds = True

        with pytest.raises(Exception) as exc_info:
            netcdf_reader.bounding_rectangle_from_attrs(mock_netcdf, mock_config)

        assert "Both bounding rectangle methods failed" in str(exc_info.value)

    def test_config_attribute_missing_defaults_to_false(self):
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
