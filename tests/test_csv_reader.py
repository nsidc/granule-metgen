import os.path

import pytest

from nsidc.metgen import config, csv_reader

# Unit tests for the 'netcdf_reader' module functions.
#
# The test boundary is the csv_reader module's interface with the filesystem
# so in addition to testing the csv_reader module's behavior, the tests
# should mock those module's functions and assert that csv_reader functions
# call them with the correct parameters, correctly handle their return values,
# and handle any exceptions they may throw.

@pytest.fixture
def csv(request, tmp_path):
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
        date_modified="2023-12-25T00:00:00.000Z",
    )


@pytest.mark.parametrize("csv", ["6", "6W", "6N", "6ABC"], indirect=True)
def test_extract_metadata(test_config, csv):
    metadata = csv_reader.extract_metadata(csv, test_config)
    assert metadata["size_in_bytes"] == os.path.getsize(csv)
    assert metadata["production_date_time"] == test_config.date_modified
    assert metadata["temporal"] == ["2023-03-06T11:00:00.000Z"]
    assert metadata["geometry"] == {
        "points": [{"Latitude": 64.86197446452954, "Longitude": -147.71408586635164}]
    }
