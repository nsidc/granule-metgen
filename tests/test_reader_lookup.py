import pytest

from nsidc.metgen import constants
from nsidc.metgen.readers import csv, netcdf_reader, snowex_csv
from nsidc.metgen.readers.registry import lookup


@pytest.mark.parametrize(
    "collection,extension,expected",
    [
        ("NSIDC-0081DUCk", constants.NETCDF_SUFFIX, netcdf_reader.extract_metadata),
        ("SNEX23_SSADUCk", constants.CSV_SUFFIX, snowex_csv.extract_metadata),
        ("IRWIS2DUCk", constants.CSV_SUFFIX, csv.extract_metadata),
    ],
)
def test_reader(collection, extension, expected):
    assert lookup(collection, extension) is expected
