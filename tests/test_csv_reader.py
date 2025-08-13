import pytest

from nsidc.metgen import config
from nsidc.metgen.readers import csv as csv_reader
from nsidc.metgen.readers import snowex_csv as snowex_csv_reader

# Unit tests for the 'csv' and 'snowex_csv' module functions.
#
# The test boundary is the csv module's interface with the filesystem
# so in addition to testing the csv module's behavior, the tests
# should mock those module's functions and assert that csv functions
# call them with the correct parameters, correctly handle their return values,
# and handle any exceptions they may throw.


@pytest.fixture
def generic_csv_content():
    return """LAT,LON,TIME,THICK,ELEVATION,FRAME,SURFACE,BOTTOM,QUALITY,DATE,DEM_SELECT
61.418877,-148.562393,82800.0000,-9999.00,1324.0513,20120316T235145,77.00,10076.00,0,160312,1
61.208763,-147.734161,3600.0000,-9999.00,1560.3271,20120317T002051,-223.93,9775.07,0,170312,1
61.330322,-146.849136,7200.3516,573.80,1889.3734,20120317T010256,1475.92,902.11,3,170312,0
61.274773,-146.751678,10800.4453,840.02,998.6060,20120317T014926,675.06,-164.96,1,170312,0
61.397221,-146.965454,14400.1172,316.81,2610.4827,20120317T021410,1944.39,1627.58,3,170312,0
61.260956,-148.987869,18000.1234,-9999.00,1226.2109,20120317T032026,758.17,10757.17,0,170312,0"""


@pytest.fixture
def generic_csv(tmp_path, generic_csv_content):
    d = tmp_path / __name__
    d.mkdir()
    p = d / "test.csv"
    p.write_text(generic_csv_content, encoding="utf-8")

    return p


@pytest.fixture
def snowex_csv(request, tmp_path):
    content = [
        "# Date (yyyy-mm-ddTHH:MM),2023-03-06T11:00,,,",
        "#Name field campaign,SnowEx 2023,,,",
        f"#UTM_Zone,{request},,,",
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
        environment="test",
        data_dir="./",
        auth_id="abcd",
        version="1",
        provider="provider",
        local_output_dir="./output",
        ummg_dir="./output/ummg",
        kinesis_stream_name="stream",
        staging_bucket_name="bucket",
        write_cnm_file=True,
        overwrite_ummg=True,
        checksum_type="SHA256",
        number=3,
        dry_run=True,
        premet_dir="",
        spatial_dir="",
        granule_regex="data*.dat",
    )


@pytest.mark.parametrize("snowex_csv", ["6", "6W", "6N", "6ABC"], indirect=True)
def test_extract_snex_metadata(test_config, snowex_csv):
    metadata = snowex_csv_reader.extract_metadata(
        snowex_csv, None, None, test_config, None
    )
    assert metadata["temporal"] == ["2023-03-06T11:00:00.000Z"]
    assert metadata["geometry"] == [
        {"Latitude": 64.86197446452954, "Longitude": -147.71408586635164}
    ]


def test_extract_generic_metadata(test_config, generic_csv_content, generic_csv):
    metadata = csv_reader.extract_metadata(generic_csv, None, None, test_config, None)
    assert metadata["temporal"] == [
        {
            "BeginningDateTime": "2012-03-16T23:00:00.000Z",
            "EndingDateTime": "2012-03-17T05:00:00.123Z",
        }
    ]
    assert len(metadata["geometry"]) == 5
    assert metadata["geometry"] == [
        {"Latitude": 61.418877, "Longitude": -148.987869},
        {"Latitude": 61.208763, "Longitude": -148.987869},
        {"Latitude": 61.208763, "Longitude": -146.751678},
        {"Latitude": 61.418877, "Longitude": -146.751678},
        {"Latitude": 61.418877, "Longitude": -148.987869},
    ]
