import pytest
from nsidc.metgen import config
from nsidc.metgen.readers import csv as csv_reader

# Unit tests for the 'snowex_csv' module functions.
#
# The test boundary is the snowex_csv module's interface with the filesystem
# so in addition to testing the snowex_csv module's behavior, the tests
# should mock those module's functions and assert that snowex_csv functions
# call them with the correct parameters, correctly handle their return values,
# and handle any exceptions they may throw.


@pytest.fixture
def csv_content():
    return """LAT,LON,TIME,THICK,ELEVATION,FRAME,SURFACE,BOTTOM,QUALITY,DATE,DEM_SELECT
61.418877,-148.562393,82800.0000,-9999.00,1324.0513,20120316T235145,77.00,10076.00,0,160312,1
61.208763,-147.734161,3600.0000,-9999.00,1560.3271,20120317T002051,-223.93,9775.07,0,170312,1
61.330322,-146.849136,7200.3516,573.80,1889.3734,20120317T010256,1475.92,902.11,3,170312,0
61.274773,-146.751678,10800.4453,840.02,998.6060,20120317T014926,675.06,-164.96,1,170312,0
61.397221,-146.965454,14400.1172,316.81,2610.4827,20120317T021410,1944.39,1627.58,3,170312,0
61.260956,-148.987869,18000.1234,-9999.00,1226.2109,20120317T032026,758.17,10757.17,0,170312,0"""


@pytest.fixture
def csv(tmp_path, csv_content):
    d = tmp_path / __name__
    d.mkdir()
    p = d / "test.csv"
    p.write_text(csv_content, encoding="utf-8")

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


def test_extract_metadata(test_config, csv_content, csv):
    metadata = csv_reader.extract_metadata(csv, test_config)
    assert metadata["size_in_bytes"] == len(csv_content)
    assert metadata["production_date_time"] == test_config.date_modified
    assert metadata["temporal"] == [
        "2012-03-16T23:00:00.000Z",
        "2012-03-17T05:00:00.123Z",
    ]
    assert len(metadata["geometry"]["points"]) == 5
    assert metadata["geometry"] == {
        "points": [
            {"Latitude": 61.418877, "Longitude": -148.987869},
            {"Latitude": 61.208763, "Longitude": -148.987869},
            {"Latitude": 61.208763, "Longitude": -146.751678},
            {"Latitude": 61.418877, "Longitude": -146.751678},
            {"Latitude": 61.418877, "Longitude": -148.987869},
        ]
    }
