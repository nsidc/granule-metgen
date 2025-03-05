import re
from unittest.mock import patch

import pytest
from nsidc.metgen import constants, netcdf_reader

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


@pytest.mark.parametrize(
    "input,expected",
    [
        pytest.param("2001-01-01", "2001-01-01T00:00:00.000Z", id="Date and no time"),
        pytest.param(
            "2001-01-01 18:59:59", "2001-01-01T18:59:59.000Z", id="Date with time"
        ),
        pytest.param(
            "2001-01-01 18:59.5",
            "2001-01-01T18:59:30.000Z",
            id="Datetime and fractional minutes",
        ),
        pytest.param(
            "2001-01-01 18:59.500",
            "2001-01-01T18:59:30.000Z",
            id="Datetime and zero padded fractional minutes",
        ),
        pytest.param(
            "2001-01-01 18:59.34",
            "2001-01-01T18:59:20.000Z",
            id="Datetime and other fractional minutes value",
        ),
        pytest.param(
            "2001-01-01 18:59.999",
            "2001-01-01T18:59:59.000Z",
            id="Datetime and other fractional minutes value",
        ),
        pytest.param(
            "2001-01-01 18:59:20.666",
            "2001-01-01T18:59:20.666Z",
            id="Datetime and fractional seconds",
        ),
        pytest.param(
            "2001-01-01 18:59",
            "2001-01-01T18:59:00.000Z",
            id="Datetime and hours/minutes",
        ),
    ],
)
def test_correctly_reads_date_time_strings(input, expected):
    result = netcdf_reader.ensure_iso(input)
    assert result == expected


def test_shows_bad_filename():
    with patch("xarray.open_dataset", side_effect=Exception("oops")):
        with pytest.raises(Exception) as exc_info:
            netcdf_reader.extract_metadata("fake.nc", {})
        assert re.search("Could not open netCDF file fake.nc", exc_info.value.args[0])
