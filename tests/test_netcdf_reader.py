import re
from unittest.mock import patch

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
