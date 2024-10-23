from unittest.mock import patch

import pytest
import xarray as xr

from nsidc.metgen import netcdf_reader

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

def test_spatial_values_are_thinned(xdata, ydata):
    result = netcdf_reader.thinned_perimeter(xdata, ydata)
    assert len(result) == (len(xdata) * 2) + (len(ydata) * 2) - 3

def test_perimeter_is_closed_polygon(xdata, ydata):
    result = netcdf_reader.thinned_perimeter(xdata, ydata)
    assert result[0] == result[-1]

def test_no_other_duplicate_values(xdata, ydata):
    result = netcdf_reader.thinned_perimeter(xdata, ydata)
    result_set = set(result)
    assert len(result_set) == len(result) -1

def test_time_defaults_to_zero():
    result = netcdf_reader.ensure_iso('2001-01-01')
    assert result == '2001-01-01T00:00:00+00:00'

def test_some_fractional_minutes_are_modified():
    result = netcdf_reader.ensure_iso('2001-01-01 18:59.99')
    assert result == '2001-01-01T18:59:59.990000+00:00'

def test_other_fractional_minutes_are_ignored():
    result = netcdf_reader.ensure_iso('2001-01-01 18:59.33')
    assert result == '2001-01-01T18:59:00.330000+00:00'

def test_fractional_seconds_are_retained():
    result = netcdf_reader.ensure_iso('2001-01-01 18:59:10.99')
    assert result == '2001-01-01T18:59:10.990000+00:00'

def test_assumes_zero_seconds_for_hhmm():
    result = netcdf_reader.ensure_iso('2001-01-01 18:59')
    assert result == '2001-01-01T18:59:00+00:00'

def test_correctly_formats_hhmmss():
    result = netcdf_reader.ensure_iso('2001-01-01 18:59:59')
    assert result == '2001-01-01T18:59:59+00:00'

