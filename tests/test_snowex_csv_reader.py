import pytest

from nsidc.metgen import config
from nsidc.metgen.readers import snowex_csv as csv_reader

# Unit tests for the 'csv' module functions.
#
# The test boundary is the csv module's interface with the filesystem
# so in addition to testing the csv module's behavior, the tests
# should mock those module's functions and assert that csv functions
# call them with the correct parameters, correctly handle their return values,
# and handle any exceptions they may throw.


@pytest.fixture
def csv(tmp_path):
    content = [
        "# Date (yyyy-mm-ddTHH:MM),2023-03-06T11:00,,,",
        "#Name field campaign,SnowEx 2023,,,",
        "#UTM_Zone,6,,,",
        "#Easting,466153,,,",
        "#Northing,7193263,,,",
        "#Timing,25 min,,,",
    ]

    d = tmp_path / __name__
    d.mkdir()
    p = d / "test.csv"
    p.write_text("\n".join(content), encoding="utf-8")

    return p


@pytest.fixture
def test_config():
    return config.Config(
        "test",
        "./",
        "abcd",
        "1",
        "provider",
        "./output",
        "./output/ummg",
        "stream",
        "bucket",
        True,
        True,
        "SHA256",
        3,
        True,
        "data*.dat",
        "fnre",
        None,
        None,
        "2023-12-25T00:00:00.000Z",
    )


def test_extract_metadata(test_config, csv):
    metadata = csv_reader.extract_metadata(csv, test_config)
    assert metadata["size_in_bytes"] == 154
    assert metadata["production_date_time"] == test_config.date_modified
    assert metadata["temporal"] == ["2023-03-06T11:00:00.000Z"]
    assert metadata["geometry"] == {
        "points": [{"Latitude": 64.86197446452954, "Longitude": -147.71408586635164}]
    }
