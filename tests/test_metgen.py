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


def test_size_is_zero_if_no_data_files(simple_collection_metadata):
    granule = metgen.Granule("foo", simple_collection_metadata, uuid="abcd-1234")
    assert granule.size() == 0


@patch("nsidc.metgen.metgen.os.path.getsize", return_value=100)
def test_gets_single_file_size(mock_size, simple_collection_metadata):
    granule = metgen.Granule("foo", simple_collection_metadata, uuid="abcd-1234")
    granule.data_filenames = {"/just/one/file"}
    assert granule.size() == 100


@patch("nsidc.metgen.metgen.os.path.getsize", return_value=100)
def test_sums_multiple_file_sizes(mock_size, simple_collection_metadata):
    granule = metgen.Granule("foo", simple_collection_metadata, uuid="abcd-1234")
    granule.data_filenames = {"/first/file", "/second/file"}
    assert granule.size() == 200


def test_ignores_regex_if_single_data_file():
    reference_file = metgen.reference_data_file("important_file", {"/first/file"})
    assert reference_file == "/first/file"


def test_finds_reference_data_file_with_regex():
    reference_file = metgen.reference_data_file(
        "important_file", {"/first/file", "/second/important_file", "/third/file"}
    )
    assert re.match("/second/important_file", reference_file)


def test_error_if_multiple_reference_file_matches():
    with pytest.raises(Exception):
        metgen.reference_data_file(
            "important_file", {"/first/important_file", "/second/important_file"}
        )


def test_error_if_no_reference_file_matches():
    with pytest.raises(Exception):
        metgen.reference_data_file("important_file", {"/first/file", "/second/file"})


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
            ("aaa_gid1_bbb.nc", "aaa_gid1_bbb.nc", {"aaa_gid1_bbb.nc"}, set(), "", ""),
        ),
        (
            "aaa_gid1_bbb",
            ["aaa_gid1_bbb.nc"],
            ["aaa_gid1_browse_bbb.png"],
            ["aaa_gid1_bbb.nc.premet"],
            [],
            (
                "aaa_gid1_bbb.nc",
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
                "aaa_gid1_bbb.nc",
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
                "aaa_gid1_bbb.nc",
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
                "aaa_gid1_bbb.nc",
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
        ".nc",
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
            (
                "aaa_gid1_bbb",
                "aaa_gid1_bbb.nc",
                {"aaa_gid1_bbb.nc", "aaa_gid1_bbb.tif"},
                set(),
                "",
                "",
            ),
        ),
        (
            "gid1",
            ["aaa_gid1_bbb.nc", "aaa_gid1_bbb.tif"],
            ["aaa_gid1_browse_bbb.png"],
            ["aaa_gid1_bbb.premet"],
            [],
            (
                "aaa_gid1_bbb",
                "aaa_gid1_bbb.nc",
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
                "aaa_gid1_xx_bbb.nc",
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
                "aaa_gid1_zz_bbb.nc",
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
        ".nc",
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
        metgen.populate_additional_attributes({"MyKey": "MyValue"}, "MyKey").rstrip()
        == '"MyKey": "MyValue",'
    )


def test_no_attempt_to_match_empty_ancillary_files():
    assert metgen.matched_ancillary_file("key1", None) is None


@patch("nsidc.metgen.metgen.s3_object_path", return_value="/some/path")
@patch("nsidc.metgen.aws.stage_file", return_value=True)
@patch("builtins.open", new_callable=mock_open, read_data="data")
def test_stage_files(m1, m2, m3, test_config, simple_collection_metadata):
    granule = metgen.Granule(
        "foo",
        simple_collection_metadata,
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


def test_s3_object_path_has_no_leading_slash(simple_collection_metadata):
    granule = metgen.Granule(
        "foo",
        simple_collection_metadata,
        uuid="abcd-1234",
    )
    expected = "external/ABCD/2/abcd-1234/xyzzy.bin"
    assert metgen.s3_object_path(granule, "xyzzy.bin") == expected


def test_s3_url_simple_case(simple_collection_metadata):
    staging_bucket_name = "xyzzy-bucket"
    granule = metgen.Granule(
        "foo",
        simple_collection_metadata,
        uuid="abcd-1234",
    )
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


def test_gsr_is_required(test_config, simple_collection_metadata):
    errors = metgen.validate_collection_spatial(test_config, simple_collection_metadata)
    assert re.search("GranuleSpatialRepresentation not available", " ".join(errors))


def test_cartesian_required_for_collection_geometry(
    test_config, simple_collection_metadata
):
    test_config.collection_geometry_override = True
    simple_collection_metadata.spatial_extent = ["one extent"]
    simple_collection_metadata.granule_spatial_representation = constants.GEODETIC
    errors = metgen.validate_collection_spatial(test_config, simple_collection_metadata)
    assert re.search("GranuleSpatialRepresentation must be", " ".join(errors))


def test_spatial_extent_is_required_for_collection_geometry(
    test_config, simple_collection_metadata
):
    test_config.collection_geometry_override = True
    simple_collection_metadata.granule_spatial_representation = constants.CARTESIAN
    errors = metgen.validate_collection_spatial(test_config, simple_collection_metadata)
    assert re.search("Collection must include a spatial extent", " ".join(errors))


def test_only_one_bounding_rectangle_allowed_in_spatial_extent(
    test_config, simple_collection_metadata
):
    test_config.collection_geometry_override = True
    simple_collection_metadata.granule_spatial_representation = constants.CARTESIAN
    simple_collection_metadata.spatial_extent = ["extent one", "extent two"]
    errors = metgen.validate_collection_spatial(test_config, simple_collection_metadata)
    assert re.search("spatial extent must only contain one", " ".join(errors))


def test_collection_temporal_ignored_if_no_override(
    test_config, simple_collection_metadata
):
    test_config.collection_temporal_override = False
    simple_collection_metadata.temporal_extent_error = "Very bad temporal error"
    errors = metgen.validate_collection_temporal(
        test_config, simple_collection_metadata
    )
    assert not errors


def test_collection_temporal_errors_returned(test_config, simple_collection_metadata):
    test_config.collection_temporal_override = True
    simple_collection_metadata.temporal_extent_error = "Very bad temporal error"
    errors = metgen.validate_collection_temporal(
        test_config, simple_collection_metadata
    )
    assert errors[0] == "Very bad temporal error"
