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
def netcdf_file():
    x = [100, 200, 300]
    y = [100, 200, 300]
    return xr.Dataset(coords={"x": (["loc"], x), "y": (["loc"], y)})

@patch('nsidc.metgen.netcdf_reader.xr.open_dataset', return_value = netcdf_file)
@patch('nsidc.metgen.netcdf_reader.os.path.getsize', return_value = 42)
def test_spatial_values_returned_as_string(os_mock, netcdf_mock):
    result = netcdf_reader.extract_metadata('path_to_nowhere')

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

