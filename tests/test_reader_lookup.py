import pytest
from nsidc.metgen import netcdf_reader
from nsidc.metgen.readers import csv, snowex_csv
from nsidc.metgen.readers.registry import lookup


@pytest.mark.parametrize(
    "collection,extension,expected",
    [
        ("NSIDC-0081DUCk", ".nc", netcdf_reader.extract_metadata),
        ("SNEX23_SSADUCk", ".csv", snowex_csv.extract_metadata),
        ("IRWIS2DUCk", ".csv", csv.extract_metadata),
    ]
)
def test_reader(collection, extension, expected):
    assert lookup(collection, extension) is expected
