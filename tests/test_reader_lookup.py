import pytest

from nsidc.metgen import constants
from nsidc.metgen.readers import generic, netcdf_reader
from nsidc.metgen.readers.registry import lookup


@pytest.mark.parametrize(
    "extension,expected",
    [
        (constants.NETCDF_SUFFIX, netcdf_reader.extract_metadata),
        (".666", generic.extract_metadata),
    ],
)
def test_reader(extension, expected):
    assert lookup(extension) is expected
