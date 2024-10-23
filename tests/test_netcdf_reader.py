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

@pytest.mark.skip
@patch('nsidc.metgen.netcdf_reader.xr.open_dataset', return_value = netcdf_file)
@patch('nsidc.metgen.netcdf_reader.os.path.getsize', return_value = 42)
def test_spatial_values_returned_as_string(os_mock, netcdf_mock):
    result = netcdf_reader.extract_metadata('path_to_nowhere')

@pytest.mark.parametrize("input,expected", [
    pytest.param('2001-01-01', '2001-01-01T00:00:00.000+00:00', id="Date and no time"),
    pytest.param('2001-01-01 18:59:59', '2001-01-01T18:59:59.000+00:00', id="Date with time"),
    pytest.param('2001-01-01 18:59.5', '2001-01-01T18:59:30.000+00:00', id="Datetime and fractional minutes"),
    pytest.param('2001-01-01 18:59.500', '2001-01-01T18:59:30.000+00:00', id="Datetime and zero padded fractional minutes"),
    pytest.param('2001-01-01 18:59.34', '2001-01-01T18:59:20.000+00:00', id="Datetime and other fractional minutes value"),
    pytest.param('2001-01-01 18:59.999', '2001-01-01T18:59:59.000+00:00', id="Datetime and other fractional minutes value"),
    pytest.param('2001-01-01 18:59:20.666', '2001-01-01T18:59:20.666+00:00', id="Datetime and fractional seconds"),
    pytest.param('2001-01-01 18:59', '2001-01-01T18:59:00.000+00:00', id="Datetime and hours/minutes"),
])
def test_correctly_formats_hhmmss(input, expected):
    result = netcdf_reader.ensure_iso(input)
    assert result == expected
