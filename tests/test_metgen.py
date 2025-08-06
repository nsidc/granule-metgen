import datetime as dt
import json
import re
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
from funcy import identity, partial

from nsidc.metgen import config, constants, metgen

# Unit tests for the 'metgen' module functions.
#
# The test boundary is the metgen module's interface with the filesystem and
# the aws & config modules, so in addition to testing the metgen module's
# behavior, the tests should mock those module's functions and assert that
# metgen functions call them with the correct parameters, correctly handle
# their return values, and handle any exceptions they may throw.


@pytest.fixture
def test_config():
    return config.Config(
        environment="uat",
        staging_bucket_name="cloud_bucket",
        data_dir="foo",
        auth_id="nsidc-0000",
        version=1,
        provider="blah",
        local_output_dir="output",
        ummg_dir="ummg",
        kinesis_stream_name="fake_stream",
        write_cnm_file=True,
        overwrite_ummg=True,
        checksum_type="sha",
        number=3,
        dry_run=False,
    )


@pytest.fixture
def test_collection():
    return metgen.Collection("ABCD", 2)


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
    return {
        "ShortName": "BigData",
        "Version": 1,
        "TemporalExtents": ["then", "now"],
        "SpatialExtent": {"here": "there"},
    }


@pytest.fixture
def ummc_valid_temporal_extent():
    return {
        "TemporalExtents": [
            {
                "RangeDateTimes": [{"begin": 1, "end": 2}],
            },
        ]
    }


@pytest.fixture
def ummc_multi_temporal_extent():
    return {
        "TemporalExtents": [
            {
                "RangeDateTimes": [{"begin": 1, "end": 2}],
            },
            {
                "RangeDateTimes": [{"begin": 3, "end": 4}],
            },
        ]
    }


@pytest.fixture
def ummc_multi_temporal_range():
    return {
        "TemporalExtents": [
            {
                "RangeDateTimes": [
                    {
                        "BeginningDateTime": "2021-11-01T00:00:00.000Z",
                        "EndingDateTime": "2021-11-30T00:00:00.000Z",
                    },
                    {
                        "BeginningDateTime": "2022-12-01T00:00:00.000Z",
                        "EndingDateTime": "2022-12-31T00:00:00.000Z",
                    },
                ],
            }
        ]
    }


@pytest.fixture
def file_list():
    file_list = [
        "aaa_gid1_bbb.nc",
        "aaa_gid1_browse_bbb.png",
        "ccc_gid2_ddd.nc",
        "ccc_gid2_browse_ddd.png",
        "eee_gid3_fff.nc",
    ]
    return [Path(f) for f in file_list]


# Regex with optional browse part and optional two-letter chunk
@pytest.fixture
def regex():
    return "([a-z]{3}_)(?P<granuleid>gid[1-3]?)(?:_browse)?(?:_[a-z]{2})?(_[a-z]{3})"


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


def test_no_cartesian_points():
    with pytest.raises(Exception):
        metgen.populate_spatial(constants.CARTESIAN, ["a point"])


def test_returns_polygon():
    result = metgen.populate_spatial(
        constants.GEODETIC, ["pt 1", "pt 2", "pt 3", "pt 4"]
    )
    assert "GPolygons" in result


def test_returns_single_datetime():
    result = metgen.populate_temporal([123])
    assert '"SingleDateTime": "123"' in result


def test_keys_from_regex(file_list, regex):
    expected = {"gid1", "gid2", "gid3"}
    found = metgen.granule_keys_from_regex(regex, file_list)
    assert expected == found


def test_keys_from_filename(file_list):
    expected = {"aaa_gid1_bbb", "ccc_gid2_ddd", "eee_gid3_fff"}
    found = metgen.granule_keys_from_filename("_browse", file_list)
    assert expected == found


def test_granule_name_from_single_file(regex):
    data_files = ["aaa_gid1_bbb.nc"]
    assert metgen.derived_granule_name(regex, data_files) == "aaa_gid1_bbb.nc"


def test_granule_name_from_regex(regex):
    data_files = ["aaa_gid1_yy_bbb.nc", "aaa_gid1_bbb.tif"]
    assert metgen.derived_granule_name(regex, data_files) == "aaa_gid1_bbb"


@pytest.mark.parametrize(
    "granuleid,data_files,browse_files,premet_files,spatial_files,expected",
    [
        (
            "aaa_gid1_bbb",
            ["aaa_gid1_bbb.nc"],
            [],
            [],
            ["aaa_gid1_bbb.nc.spatial"],
            (
                "aaa_gid1_bbb.nc",
                {"aaa_gid1_bbb.nc"},
                set(),
                "",
                "aaa_gid1_bbb.nc.spatial",
            ),
        ),
        (
            "aaa_gid1_bbb",
            ["aaa_gid1_bbb.nc"],
            ["aaa_gid1_browse_bbb.png"],
            [],
            ["aaa_gid1_ccc.nc.spatial"],
            ("aaa_gid1_bbb.nc", {"aaa_gid1_bbb.nc"}, set(), "", ""),
        ),
        (
            "aaa_gid1_bbb",
            ["aaa_gid1_bbb.nc"],
            ["aaa_gid1_browse_bbb.png"],
            ["aaa_gid1_bbb.nc.premet"],
            [],
            (
                "aaa_gid1_bbb.nc",
                {"aaa_gid1_bbb.nc"},
                set(),
                "aaa_gid1_bbb.nc.premet",
                "",
            ),
        ),
        (
            "aaa_gid1_bbb",
            ["aaa_gid1_bbb.nc"],
            ["aaa_gid1_bbb_browse.png"],
            [],
            [],
            (
                "aaa_gid1_bbb.nc",
                {"aaa_gid1_bbb.nc"},
                {"aaa_gid1_bbb_browse.png"},
                "",
                "",
            ),
        ),
        (
            "aaa_gid1_bbb",
            ["aaa_gid1_bbb.nc"],
            ["aaa_gid1_bbb_browse.png"],
            ["aaa_gid1_bbb.nc.premet"],
            [],
            (
                "aaa_gid1_bbb.nc",
                {"aaa_gid1_bbb.nc"},
                {"aaa_gid1_bbb_browse.png"},
                "aaa_gid1_bbb.nc.premet",
                "",
            ),
        ),
        (
            "aaa_gid1_bbb",
            ["aaa_gid1_bbb.nc"],
            ["aaa_gid1_bbb_browse.png"],
            ["ccc_gid1_ddd.nc.premet"],
            [],
            (
                "aaa_gid1_bbb.nc",
                {"aaa_gid1_bbb.nc"},
                {"aaa_gid1_bbb_browse.png"},
                "",
                "",
            ),
        ),
        (
            "aaa_gid1_bbb",
            ["aaa_gid1_bbb.nc", "aaa_gid1_bbb.tif"],
            ["aaa_gid1_bbb_browse.png"],
            [],
            [],
            (
                "aaa_gid1_bbb",
                {"aaa_gid1_bbb.nc", "aaa_gid1_bbb.tif"},
                {"aaa_gid1_bbb_browse.png"},
                "",
                "",
            ),
        ),
        (
            "aaa_gid1_bbb",
            ["aaa_gid1_bbb.nc", "aaa_gid1_bbb.tif"],
            ["aaa_gid1_bbb_browse.png"],
            ["aaa_gid1_bbb.premet"],
            [],
            (
                "aaa_gid1_bbb",
                {"aaa_gid1_bbb.nc", "aaa_gid1_bbb.tif"},
                {"aaa_gid1_bbb_browse.png"},
                "aaa_gid1_bbb.premet",
                "",
            ),
        ),
        (
            "aaa_gid1_bbb",
            ["aaa_gid1_bbb.nc", "aaa_gid1_bbb.tif"],
            ["aaa_gid1_bbb_browse.png", "aaa_gid1_browse_bbb.tif"],
            [],
            [],
            (
                "aaa_gid1_bbb",
                {"aaa_gid1_bbb.nc", "aaa_gid1_bbb.tif"},
                {"aaa_gid1_bbb_browse.png"},
                "",
                "",
            ),
        ),
    ],
)
def test_granule_tuple_from_filenames(
    granuleid, data_files, browse_files, premet_files, spatial_files, expected
):
    granule = metgen.granule_tuple(
        granuleid,
        f"({granuleid})",
        "browse",
        [Path(p) for p in data_files + browse_files],
        [Path(p) for p in premet_files],
        [Path(p) for p in spatial_files],
    )
    assert granule == expected


@pytest.mark.parametrize(
    "granuleid,data_files,browse_files,premet_files,spatial_files,expected",
    [
        (
            "gid1",
            ["aaa_gid1_bbb.nc", "aaa_gid1_bbb.tif"],
            [],
            [],
            [],
            ("aaa_gid1_bbb", {"aaa_gid1_bbb.nc", "aaa_gid1_bbb.tif"}, set(), "", ""),
        ),
        (
            "gid1",
            ["aaa_gid1_bbb.nc", "aaa_gid1_bbb.tif"],
            ["aaa_gid1_browse_bbb.png"],
            ["aaa_gid1_bbb.premet"],
            [],
            (
                "aaa_gid1_bbb",
                {"aaa_gid1_bbb.nc", "aaa_gid1_bbb.tif"},
                {"aaa_gid1_browse_bbb.png"},
                "aaa_gid1_bbb.premet",
                "",
            ),
        ),
        (
            "gid1",
            ["aaa_gid1_xx_bbb.nc", "aaa_gid1_bbb.tif"],
            ["aaa_gid1_browse_bbb.png"],
            ["aaa_gid1_xx_bbb.premet"],
            [],
            (
                "aaa_gid1_bbb",
                {"aaa_gid1_xx_bbb.nc", "aaa_gid1_bbb.tif"},
                {"aaa_gid1_browse_bbb.png"},
                "aaa_gid1_xx_bbb.premet",
                "",
            ),
        ),
        (
            "gid1",
            ["aaa_gid1_zz_bbb.nc", "aaa_gid1_xx_bbb.tif"],
            ["aaa_gid1_browse_zz_bbb.png", "aaa_gid1_browse_yy_bbb.tif"],
            [],
            [],
            (
                "aaa_gid1_bbb",
                {"aaa_gid1_zz_bbb.nc", "aaa_gid1_xx_bbb.tif"},
                {"aaa_gid1_browse_zz_bbb.png", "aaa_gid1_browse_yy_bbb.tif"},
                "",
                "",
            ),
        ),
    ],
)
def test_granule_tuple_from_regex(
    granuleid, data_files, browse_files, premet_files, spatial_files, expected, regex
):
    granule = metgen.granule_tuple(
        granuleid,
        regex,
        "browse",
        [Path(p) for p in data_files + browse_files],
        [Path(p) for p in premet_files],
        [Path(p) for p in spatial_files],
    )
    assert granule == expected


@pytest.mark.parametrize(
    "granuleid,spatial_files,expected",
    [
        (
            "key1",
            ["file_with_key1.suffix", "file_with_key2.suffix"],
            "file_with_key1.suffix",
        ),
        (
            "file_with_key1.nc",
            ["file_with_key1.nc.suffix", "file_with_key2.nc.suffix"],
            "file_with_key1.nc.suffix",
        ),
        (
            "file_with_key1",
            ["file_with_key2.suffix", "file_with_key3.suffix"],
            "",
        ),
    ],
)
def test_matches_ancillary_files(granuleid, spatial_files, expected):
    assert (
        metgen.matched_ancillary_file(granuleid, [Path(p) for p in spatial_files])
        == expected
    )


def test_no_premet_content():
    assert metgen.populate_additional_attributes(None, "SomeKey") == ""


def test_no_matching_premet_key():
    assert (
        metgen.populate_additional_attributes({"MyKey": "MyValue"}, "UnmatchedKey")
        == ""
    )


def test_a_matching_premet_key():
    assert (
        metgen.populate_additional_attributes({"MyKey": "MyValue"}, "MyKey")
        == '"MyKey": "MyValue",'
    )


def test_no_attempt_to_match_empty_ancillary_files():
    assert metgen.matched_ancillary_file("key1", None) is None


@patch("nsidc.metgen.metgen.s3_object_path", return_value="/some/path")
@patch("nsidc.metgen.aws.stage_file", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data="data")
def test_stage_files(m1, m2, m3, test_config):
    granule = metgen.Granule(
        "foo",
        metgen.Collection("ABCD", 2),
        uuid="abcd-1234",
        data_filenames={"file1", "file2", "file3"},
        browse_filenames={"browse1", "browse2", "browse3"},
        ummg_filename="foo_ummg",
    )
    assert metgen.stage_files(test_config, granule)


def test_returns_datetime_range():
    result = metgen.populate_temporal(
        [{"BeginningDateTime": "123", "EndingDateTime": "456"}]
    )
    result_json = json.loads(result)
    assert isinstance(result_json["RangeDateTime"], dict)
    assert result_json["RangeDateTime"]["BeginningDateTime"] == "123"
    assert result_json["RangeDateTime"]["EndingDateTime"] == "456"


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


def test_handles_missing_ummc_key(fake_ummc_response):
    assert metgen.ummc_content({}, ["fakekey"]) is None
    assert metgen.ummc_content(fake_ummc_response, ["DOI"]) is None


def test_finds_existing_ummc_key(fake_ummc_response):
    assert metgen.ummc_content(fake_ummc_response, ["Version"]) == 1


def test_looks_for_umm_dict(fake_ummc_response):
    ummc = metgen.validate_cmr_response([{"umm": fake_ummc_response}])
    assert ummc == fake_ummc_response


@pytest.mark.parametrize(
    "umm_content,error",
    [
        ([], "Empty UMM-C response from CMR."),
        (
            ["ummc1", "ummc2"],
            "Multiple UMM-C records returned from CMR, none will be used.",
        ),
        (
            ["ummc1"],
            "No UMM-C content in CMR response.",
        ),
        (
            [{"ummc1": "some ummc"}],
            "No UMM-C content in CMR response.",
        ),
        (
            [{"umm": "some ummc"}],
            "Malformed UMM-C content returned from CMR.",
        ),
    ],
)
def test_umm_key_required(umm_content, error):
    with pytest.raises(config.ValidationError) as exc_info:
        metgen.validate_cmr_response(umm_content)
    assert re.search(error, exc_info.value.args[0])


def test_gsr_is_required(test_config, test_collection):
    errors = metgen.validate_collection_spatial(test_config, test_collection)
    assert re.search("GranuleSpatialRepresentation not available", " ".join(errors))


def test_cartesian_required_for_collection_geometry(test_config, test_collection):
    test_config.collection_geometry_override = True
    test_collection.spatial_extent = ["one extent"]
    test_collection.granule_spatial_representation = constants.GEODETIC
    errors = metgen.validate_collection_spatial(test_config, test_collection)
    assert re.search("GranuleSpatialRepresentation must be", " ".join(errors))


def test_spatial_extent_is_required_for_collection_geometry(
    test_config, test_collection
):
    test_config.collection_geometry_override = True
    test_collection.granule_spatial_representation = constants.CARTESIAN
    errors = metgen.validate_collection_spatial(test_config, test_collection)
    assert re.search("Collection must include a spatial extent", " ".join(errors))


def test_only_one_bounding_rectangle_allowed_in_spatial_extent(
    test_config, test_collection
):
    test_config.collection_geometry_override = True
    test_collection.granule_spatial_representation = constants.CARTESIAN
    test_collection.spatial_extent = ["extent one", "extent two"]
    errors = metgen.validate_collection_spatial(test_config, test_collection)
    assert re.search("spatial extent must only contain one", " ".join(errors))


def test_collection_temporal_ignored_if_no_override(test_config, test_collection):
    test_config.collection_temporal_override = False
    test_collection.temporal_extent_error = "Very bad temporal error"
    errors = metgen.validate_collection_temporal(test_config, test_collection)
    assert not errors


def test_collection_temporal_errors_returned(test_config, test_collection):
    test_config.collection_temporal_override = True
    test_collection.temporal_extent_error = "Very bad temporal error"
    errors = metgen.validate_collection_temporal(test_config, test_collection)
    assert errors[0] == "Very bad temporal error"


def test_only_one_collection_temporal_extent_allowed(ummc_multi_temporal_extent):
    temporal_details, error = metgen.temporal_from_ummc(ummc_multi_temporal_extent)
    assert re.search("one temporal extent", error)


def test_only_one_collection_temporal_details_allowed(ummc_multi_temporal_range):
    temporal_details, error = metgen.temporal_from_ummc(ummc_multi_temporal_range)
    assert re.search("one temporal range or a single temporal", error)


def test_valid_collection_temporal(ummc_valid_temporal_extent):
    temporal_details, error = metgen.temporal_from_ummc(ummc_valid_temporal_extent)
    assert not error
