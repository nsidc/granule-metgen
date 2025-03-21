import datetime as dt
from pathlib import Path
from unittest.mock import patch

import pytest
from funcy import identity, partial
from nsidc.metgen import metgen

# Unit tests for the 'metgen' module functions.
#
# The test boundary is the metgen module's interface with the filesystem and
# the aws & config modules, so in addition to testing the metgen module's
# behavior, the tests should mock those module's functions and assert that
# metgen functions call them with the correct parameters, correctly handle
# their return values, and handle any exceptions they may throw.


@pytest.fixture
def multi_file_granule():
    return {
        "first_id": {
            "size_in_bytes": 100,
            "production_date_time": "then",
            "temporal": "now",
            "geometry": "big",
        },
        "second_id": {
            "size_in_bytes": 200,
            "production_date_time": "before",
            "temporal": "after",
            "geometry": "small",
        },
    }


@pytest.fixture
def single_file_granule():
    return {
        "first_id": {
            "size_in_bytes": 150,
            "production_date_time": "then",
            "temporal": "now",
            "geometry": "big",
        }
    }


@pytest.fixture
def fake_ummc_response():
    return [
        {
            "umm": {
                "ShortName": "BigData",
                "Version": 1,
                "TemporalExtents": ["then", "now"],
                "SpatialExtent": {"here": "there"},
            }
        }
    ]


def test_banner():
    assert len(metgen.banner()) > 0


def test_gets_single_file_size(single_file_granule):
    summary = metgen.metadata_summary(single_file_granule)
    assert summary["size_in_bytes"] == 150


def test_sums_multiple_file_sizes(multi_file_granule):
    summary = metgen.metadata_summary(multi_file_granule)
    assert summary["size_in_bytes"] == 300


def test_uses_first_file_as_default(multi_file_granule):
    summary = metgen.metadata_summary(multi_file_granule)
    assert summary["production_date_time"] == "then"
    assert summary["temporal"] == "now"
    assert summary["geometry"] == "big"


def test_returns_only_gpolygon():
    result = metgen.populate_spatial({"points": "some list of points"})
    assert "GPolygons" in result


def test_returns_single_datetime():
    result = metgen.populate_temporal([123])
    assert '"SingleDateTime": "123"' in result


def test_granule_id_for_one_file():
    granule_id = metgen.derived_granule_id(["path1.xyz"])
    assert granule_id == "path1.xyz"


def test_granule_id_for_multiple_files():
    granule_id = metgen.derived_granule_id(["path1.xyz", "path2.xyz", "path3.xyz"])
    assert granule_id == "path"


@pytest.mark.parametrize(
    "granule_str,data_files,browse_files,expected",
    [
        ("gfile", ["gfile.nc"], [], ("gfile.nc", ["gfile.nc"], [])),
        ("gfile.nc", ["gfile.nc"], [], ("gfile.nc", ["gfile.nc"], [])),
        (
            "gfile",
            ["gfile.nc"],
            ["gfile_browse.png"],
            ("gfile.nc", ["gfile.nc"], ["gfile_browse.png"]),
        ),
        (
            "gfile.nc",
            ["gfile.nc"],
            ["browse.png"],
            ("gfile.nc", ["gfile.nc"], []),
        ),
        (
            "gfile",
            ["gfile.nc", "gfile.tif"],
            [],
            ("gfile", ["gfile.nc", "gfile.tif"], []),
        ),
        (
            "gfile",
            ["gfile.nc", "gfile.tif"],
            ["gfile_browse.png"],
            ("gfile", ["gfile.nc", "gfile.tif"], ["gfile_browse.png"]),
        ),
        (
            "gfile",
            ["gfile.nc", "gfile.tif"],
            ["gfile_browse.png", "gfile_browse.tif"],
            (
                "gfile",
                ["gfile.nc", "gfile.tif"],
                ["gfile_browse.png", "gfile_browse.tif"],
            ),
        ),
    ],
)
def test_granule_file_combinations(granule_str, data_files, browse_files, expected):
    granule = metgen.granule_tuple(
        granule_str, "browse", [Path(p) for p in data_files + browse_files]
    )
    assert granule == expected


def test_returns_datetime_range():
    result = metgen.populate_temporal([123, 456])
    assert "RangeDateTime" in result
    assert '"BeginningDateTime": "123"' in result
    assert '"EndingDateTime": "456"' in result


def test_s3_object_path_has_no_leading_slash():
    granule = metgen.Granule("foo", metgen.Collection("ABCD", 2), uuid="abcd-1234")
    expected = "external/ABCD/2/abcd-1234/xyzzy.bin"
    assert metgen.s3_object_path(granule, "xyzzy.bin") == expected


def test_s3_url_simple_case():
    staging_bucket_name = "xyzzy-bucket"
    granule = metgen.Granule("foo", metgen.Collection("ABCD", 2), uuid="abcd-1234")
    expected = "s3://xyzzy-bucket/external/ABCD/2/abcd-1234/xyzzy.bin"
    assert metgen.s3_url(staging_bucket_name, granule, "xyzzy.bin") == expected


@patch("nsidc.metgen.metgen.dt.datetime")
def test_start_ledger(mock_datetime):
    now = dt.datetime(2099, 7, 4, 10, 11, 12)
    mock_datetime.now.return_value = now
    granule = metgen.Granule("abcd-1234")

    actual = metgen.start_ledger(granule)

    assert actual.granule == granule
    assert actual.startDatetime == now


@patch("nsidc.metgen.metgen.dt.datetime")
def test_end_ledger(mock_datetime):
    now = dt.datetime(2099, 7, 4, 10, 11, 12)
    mock_datetime.now.return_value = now
    granule = metgen.Granule("abcd-1234")
    ledger = metgen.Ledger(granule, [metgen.Action("foo", True, "")], startDatetime=now)

    actual = metgen.end_ledger(ledger)

    assert actual.granule == granule
    assert actual.successful
    assert actual.startDatetime == now
    assert actual.endDatetime == now


@patch("nsidc.metgen.metgen.dt.datetime")
def test_end_ledger_with_unsuccessful_actions(mock_datetime):
    now = dt.datetime(2099, 7, 4, 10, 11, 12)
    mock_datetime.now.return_value = now
    granule = metgen.Granule("abcd-1234")
    ledger = metgen.Ledger(
        granule,
        [metgen.Action("foo", False, ""), metgen.Action("bar", False, "Oops")],
        startDatetime=now,
    )

    actual = metgen.end_ledger(ledger)

    assert actual.granule == granule
    assert not actual.successful
    assert actual.startDatetime == now
    assert actual.endDatetime == now


def test_recorder():
    granule = metgen.Granule("abcd-1234")
    ledger = metgen.start_ledger(granule)

    new_ledger = partial(metgen.recorder, identity)(ledger)

    assert new_ledger.granule == ledger.granule
    assert len(new_ledger.actions) == 1


def test_recorder_with_failing_operation():
    granule = metgen.Granule("abcd-1234")
    ledger = metgen.start_ledger(granule)

    def failing_op():
        raise Exception()

    new_ledger = partial(metgen.recorder, failing_op)(ledger)

    assert new_ledger.granule == ledger.granule
    assert len(new_ledger.actions) == 1
    assert not new_ledger.actions[0].successful


def test_no_dummy_json_for_cnm():
    schema_path, dummy_json = metgen.schema_file_path("cnm")
    assert schema_path
    assert not dummy_json

    schema_path, dummy_json = metgen.schema_file_path("foobar")
    assert not schema_path
    assert not dummy_json


def test_dummy_json_for_ummg():
    schema_path, dummy_json = metgen.schema_file_path("ummg")
    assert schema_path
    assert dummy_json


@patch("nsidc.metgen.metgen.open")
@patch("nsidc.metgen.metgen.jsonschema.validate")
def test_dummy_json_used(mock_validate, mock_open):
    fake_json = {"key": [{"foo": "bar"}]}
    fake_dummy_json = {"missing_key": "missing_foo"}

    with patch("nsidc.metgen.metgen.json.load", return_value=fake_json):
        metgen.apply_schema("schema file", "json_file", fake_dummy_json)
        mock_validate.assert_called_once_with(
            instance=fake_json | fake_dummy_json, schema="schema file"
        )


@pytest.mark.parametrize(
    "ingest_env,edl_env",
    [("int", "UAT"), ("uat", "UAT"), ("prod", "PROD")],
)
def test_edl_login_environment(ingest_env, edl_env):
    environment = metgen.edl_environment(ingest_env)
    assert (environment) == edl_env

    environment = metgen.edl_environment(ingest_env.upper())
    assert (environment) == edl_env


def test_handles_no_cmr_response(fake_ummc_response):
    assert metgen.ummc_content([], "fakekey") is None
    assert metgen.ummc_content(fake_ummc_response, "DOI") is None


def test_handles_good_cmr_response(fake_ummc_response):
    assert metgen.ummc_content(fake_ummc_response, "Version") == 1


@patch("nsidc.metgen.metgen.edl_login", return_value=False)
def test_no_ummc_if_login_fails(mock_edl_login):
    new_collection = metgen.collection_from_cmr("uat", "BigData", 1)
    assert new_collection.spatial_extent is None
    assert new_collection.temporal_extent is None
