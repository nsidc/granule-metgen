import dataclasses
import re
from configparser import ConfigParser, ExtendedInterpolation
from unittest.mock import patch

import pytest

from nsidc.metgen import config, constants

# Unit tests for the 'config' module functions.
#
# The test boundary is the config module's interface with the filesystem and
# the aws module, so in addition to testing the config module's behavior, the
# tests should mock those module's functions and assert that config functions
# call them with the correct parameters, correctly handle their return values,
# and handle any exceptions they may throw.


@pytest.fixture
def expected_keys():
    return set(
        [
            "environment",
            "data_dir",
            "auth_id",
            "version",
            "provider",
            "local_output_dir",
            "ummg_dir",
            "kinesis_stream_name",
            "staging_bucket_name",
            "write_cnm_file",
            "overwrite_ummg",
            "checksum_type",
            "number",
            "dry_run",
            "premet_dir",
            "spatial_dir",
            "collection_geometry_override",
            "collection_temporal_override",
            "time_start_regex",
            "time_coverage_duration",
            "pixel_size",
            "browse_regex",
            "granule_regex",
            "reference_file_regex",
            "spatial_polygon_enabled",
            "spatial_polygon_target_coverage",
            "spatial_polygon_max_vertices",
            "spatial_polygon_cartesian_tolerance",
        ]
    )


@pytest.fixture
def cfg_parser():
    cp = ConfigParser(interpolation=ExtendedInterpolation())
    cp["Source"] = {"data_dir": "/data/example"}
    cp["Collection"] = {"auth_id": "DATA-0001", "version": 42, "provider": "FOO"}
    cp["Destination"] = {
        "local_output_dir": "/output/here",
        "ummg_dir": "ummg",
        "kinesis_stream_name": "xyzzy-${environment}-stream",
        "staging_bucket_name": "xyzzy-${environment}-bucket",
        "write_cnm_file": False,
    }
    cp["Settings"] = {"checksum_type": "SHA256", "number": 1}
    return cp


def test_config_parser_without_filename():
    with pytest.raises(ValueError):
        config.config_parser_factory(None)


@patch("nsidc.metgen.metgen.os.path.exists", return_value=True)
def test_config_parser_return_type(mock):
    result = config.config_parser_factory("foo.ini")
    assert isinstance(result, ConfigParser)


@patch("nsidc.metgen.metgen.os.path.exists", return_value=True)
def test_config_parser_handles_empty_strings_for_booleans(mock):
    cp = config.config_parser_factory("foo.ini")
    cp["foo"] = {"success": ""}
    assert not cp.getboolean("foo", "success")


def test_config_from_config_parser(cfg_parser):
    cfg = config.configuration(cfg_parser, {}, constants.DEFAULT_CUMULUS_ENVIRONMENT)
    assert isinstance(cfg, config.Config)


def test_config_with_no_write_cnm(cfg_parser, expected_keys):
    cfg = config.configuration(cfg_parser, {}, constants.DEFAULT_CUMULUS_ENVIRONMENT)

    config_keys = set(cfg.__dict__)
    assert len(config_keys - expected_keys) == 0

    assert cfg.environment == "uat"
    assert cfg.data_dir == "/data/example"
    assert cfg.auth_id == "DATA-0001"
    assert cfg.kinesis_stream_name == "xyzzy-uat-stream"
    assert not cfg.write_cnm_file


def test_config_with_write_cnm(cfg_parser, expected_keys):
    cfg_parser.set("Destination", "write_cnm_file", "True")
    cfg = config.configuration(cfg_parser, {})

    config_keys = set(cfg.__dict__)
    assert len(config_keys - expected_keys) == 0

    assert cfg.data_dir == "/data/example"
    assert cfg.auth_id == "DATA-0001"
    assert cfg.kinesis_stream_name == "xyzzy-uat-stream"
    assert cfg.environment == "uat"
    assert cfg.write_cnm_file


def test_config_with_no_overwrite_ummg(cfg_parser, expected_keys):
    cfg = config.configuration(cfg_parser, {}, constants.DEFAULT_CUMULUS_ENVIRONMENT)

    config_keys = set(cfg.__dict__)
    assert len(config_keys - expected_keys) == 0
    assert not cfg.overwrite_ummg


def test_config_with_overwrite_ummg(cfg_parser, expected_keys):
    cfg_parser.set("Destination", "overwrite_ummg", "True")
    cfg = config.configuration(cfg_parser, {})

    config_keys = set(cfg.__dict__)
    assert len(config_keys - expected_keys) == 0
    assert cfg.overwrite_ummg


def test_get_configuration_value(cfg_parser):
    environment = constants.DEFAULT_CUMULUS_ENVIRONMENT
    result = config._get_configuration_value(
        environment, "Source", "data_dir", str, cfg_parser, {}
    )
    assert result == cfg_parser.get("Source", "data_dir")


def test_get_configuration_value_with_override(cfg_parser):
    environment = constants.DEFAULT_CUMULUS_ENVIRONMENT
    overrides = {"data_dir": "foobar"}
    result = config._get_configuration_value(
        environment, "Source", "data_dir", str, cfg_parser, overrides
    )
    assert result == overrides["data_dir"]


def test_get_configuration_value_interpolates_the_environment(cfg_parser):
    environment = constants.DEFAULT_CUMULUS_ENVIRONMENT
    result = config._get_configuration_value(
        environment, "Destination", "kinesis_stream_name", str, cfg_parser, {}
    )
    assert result == "xyzzy-uat-stream"


@pytest.mark.parametrize(
    "section,option,expected",
    [
        ("Source", "premet_dir", None),
        ("Source", "spatial_dir", None),
        (
            "Source",
            "collection_geometry_override",
            constants.DEFAULT_COLLECTION_GEOMETRY_OVERRIDE,
        ),
        (
            "Source",
            "collection_temporal_override",
            constants.DEFAULT_COLLECTION_TEMPORAL_OVERRIDE,
        ),
        (
            "Destination",
            "kinesis_stream_name",
            f"nsidc-cumulus-{constants.DEFAULT_CUMULUS_ENVIRONMENT}-external_notification",
        ),
        (
            "Destination",
            "staging_bucket_name",
            f"nsidc-cumulus-{constants.DEFAULT_CUMULUS_ENVIRONMENT}-ingest-staging",
        ),
        ("Destination", "write_cnm_file", constants.DEFAULT_WRITE_CNM_FILE),
        ("Settings", "checksum_type", constants.DEFAULT_CHECKSUM_TYPE),
        ("Settings", "number", constants.DEFAULT_NUMBER),
        ("Collection", "time_start_regex", None),
        ("Collection", "granule_regex", None),
        ("Collection", "browse_regex", constants.DEFAULT_BROWSE_REGEX),
        ("Collection", "time_coverage_duration", None),
        ("Collection", "pixel_size", None),
        ("Collection", "time_coverage_duration", None),
    ],
)
def test_configuration_has_good_defaults(cfg_parser, section, option, expected):
    cfg_parser.remove_option(section, option)
    result = config.configuration(cfg_parser, {}, constants.DEFAULT_CUMULUS_ENVIRONMENT)
    result_dict = dataclasses.asdict(result)
    assert result_dict[option] == expected


@patch("nsidc.metgen.metgen.os.path.exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.kinesis_stream_exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.staging_bucket_exists", return_value=True)
def test_validate_with_valid_checks(m1, m2, m3, cfg_parser):
    cfg = config.configuration(cfg_parser, {})
    valid = config.validate(cfg)
    assert valid


@patch("nsidc.metgen.metgen.os.path.exists", return_value=False)
@patch("nsidc.metgen.metgen.aws.kinesis_stream_exists", return_value=False)
@patch("nsidc.metgen.metgen.aws.staging_bucket_exists", return_value=False)
def test_validate_with_invalid_checks(m1, m2, m3, cfg_parser):
    cfg = config.configuration(cfg_parser, {})
    with pytest.raises(config.ValidationError) as exc_info:
        config.validate(cfg)
    assert len(exc_info.value.errors) == 4


@pytest.mark.parametrize(
    "dir_type,dir_path",
    [
        ("premet_dir", "fake_premet_dir"),
        ("spatial_dir", "fake_spatial_dir"),
    ],
)
@patch(
    "nsidc.metgen.metgen.os.path.exists",
    side_effect=lambda path: path not in ["fake_premet_dir", "fake_spatial_dir"],
)
@patch("nsidc.metgen.metgen.aws.kinesis_stream_exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.staging_bucket_exists", return_value=True)
def test_validates_optional_dirs_with_values(
    m1, m2, m3, cfg_parser, dir_type, dir_path
):
    cfg_parser.set("Source", dir_type, dir_path)
    cfg = config.configuration(cfg_parser, {})
    with pytest.raises(config.ValidationError) as exc_info:
        config.validate(cfg)
    assert f"The {dir_type} does not exist." in exc_info.value.errors


@pytest.mark.parametrize(
    "dir_type,dir_path",
    [
        ("premet_dir", ""),
        ("spatial_dir", ""),
    ],
)
@patch("nsidc.metgen.metgen.os.path.exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.kinesis_stream_exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.staging_bucket_exists", return_value=True)
def test_validates_optional_dirs_without_values(
    m1, m2, m3, cfg_parser, dir_type, dir_path
):
    cfg_parser.set("Source", dir_type, dir_path)
    cfg = config.configuration(cfg_parser, {})
    # When optional dirs are empty strings, validation should pass
    valid = config.validate(cfg)
    assert valid is True


@patch("nsidc.metgen.metgen.os.path.exists", return_value=True)
def test_prevents_geometry_clash(cfg_parser):
    cfg_parser.set("Source", "spatial_dir", "path/to/files")
    cfg_parser.set("Source", "collection_geometry_override", "True")
    cfg = config.configuration(cfg_parser, {})
    with pytest.raises(config.ValidationError) as exc_info:
        config.validate_spatial_source(cfg)
    assert re.search("Cannot declare both", exc_info.value.errors[0])


def test_spatial_polygon_configuration_defaults(cfg_parser):
    """Test that spatial polygon configuration has correct defaults."""
    cfg = config.configuration(cfg_parser, {})
    assert cfg.spatial_polygon_enabled is True
    assert cfg.spatial_polygon_target_coverage == 0.98
    assert cfg.spatial_polygon_max_vertices == 100


def test_spatial_polygon_configuration_from_ini(cfg_parser):
    """Test reading spatial polygon configuration from ini file."""
    cfg_parser["Spatial"] = {
        "spatial_polygon_enabled": "False",
        "spatial_polygon_target_coverage": "0.95",
        "spatial_polygon_max_vertices": "150",
    }
    cfg = config.configuration(cfg_parser, {})
    assert cfg.spatial_polygon_enabled is False
    assert cfg.spatial_polygon_target_coverage == 0.95
    assert cfg.spatial_polygon_max_vertices == 150


def test_spatial_polygon_configuration_overrides(cfg_parser):
    """Test that overrides work for spatial polygon configuration."""
    overrides = {
        "spatial_polygon_enabled": True,
        "spatial_polygon_target_coverage": 0.90,
        "spatial_polygon_max_vertices": 200,
    }
    cfg = config.configuration(cfg_parser, overrides)
    assert cfg.spatial_polygon_enabled is True
    assert cfg.spatial_polygon_target_coverage == 0.90
    assert cfg.spatial_polygon_max_vertices == 200


@patch("nsidc.metgen.metgen.os.path.exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.kinesis_stream_exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.staging_bucket_exists", return_value=True)
def test_spatial_polygon_target_coverage_validation_valid(m1, m2, m3, cfg_parser):
    """Test validation of valid spatial polygon target coverage values."""
    cfg_parser["Spatial"] = {"spatial_polygon_target_coverage": "0.85"}
    cfg = config.configuration(cfg_parser, {})
    assert config.validate(cfg) is True


@patch("nsidc.metgen.metgen.os.path.exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.kinesis_stream_exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.staging_bucket_exists", return_value=True)
def test_spatial_polygon_target_coverage_validation_too_low(m1, m2, m3, cfg_parser):
    """Test validation rejects spatial polygon target coverage below 0.80."""
    cfg_parser["Spatial"] = {"spatial_polygon_target_coverage": "0.75"}
    cfg = config.configuration(cfg_parser, {})
    with pytest.raises(config.ValidationError) as exc_info:
        config.validate(cfg)
    assert (
        "The spatial polygon target coverage must be between 0.80 and 1.0."
        in exc_info.value.errors
    )


@patch("nsidc.metgen.metgen.os.path.exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.kinesis_stream_exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.staging_bucket_exists", return_value=True)
def test_spatial_polygon_target_coverage_validation_too_high(m1, m2, m3, cfg_parser):
    """Test validation rejects spatial polygon target coverage above 1.0."""
    cfg_parser["Spatial"] = {"spatial_polygon_target_coverage": "1.1"}
    cfg = config.configuration(cfg_parser, {})
    with pytest.raises(config.ValidationError) as exc_info:
        config.validate(cfg)
    assert (
        "The spatial polygon target coverage must be between 0.80 and 1.0."
        in exc_info.value.errors
    )


@patch("nsidc.metgen.metgen.os.path.exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.kinesis_stream_exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.staging_bucket_exists", return_value=True)
def test_spatial_polygon_max_vertices_validation_valid(m1, m2, m3, cfg_parser):
    """Test validation of valid spatial polygon max vertices values."""
    cfg_parser["Spatial"] = {"spatial_polygon_max_vertices": "500"}
    cfg = config.configuration(cfg_parser, {})
    assert config.validate(cfg) is True


@patch("nsidc.metgen.metgen.os.path.exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.kinesis_stream_exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.staging_bucket_exists", return_value=True)
def test_spatial_polygon_max_vertices_validation_too_low(m1, m2, m3, cfg_parser):
    """Test validation rejects spatial polygon max vertices below 10."""
    cfg_parser["Spatial"] = {"spatial_polygon_max_vertices": "5"}
    cfg = config.configuration(cfg_parser, {})
    with pytest.raises(config.ValidationError) as exc_info:
        config.validate(cfg)
    assert (
        "The spatial polygon max vertices must be between 10 and 1000."
        in exc_info.value.errors
    )


@patch("nsidc.metgen.metgen.os.path.exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.kinesis_stream_exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.staging_bucket_exists", return_value=True)
def test_spatial_polygon_max_vertices_validation_too_high(m1, m2, m3, cfg_parser):
    """Test validation rejects spatial polygon max vertices above 1000."""
    cfg_parser["Spatial"] = {"spatial_polygon_max_vertices": "1500"}
    cfg = config.configuration(cfg_parser, {})
    with pytest.raises(config.ValidationError) as exc_info:
        config.validate(cfg)
    assert (
        "The spatial polygon max vertices must be between 10 and 1000."
        in exc_info.value.errors
    )


def test_spatial_polygon_cartesian_tolerance_defaults(cfg_parser):
    """Test that spatial polygon cartesian tolerance has correct default."""
    cfg = config.configuration(cfg_parser, {})
    assert cfg.spatial_polygon_cartesian_tolerance == 0.0001


def test_spatial_polygon_cartesian_tolerance_from_ini(cfg_parser):
    """Test reading spatial polygon cartesian tolerance from ini file."""
    cfg_parser["Spatial"] = {
        "spatial_polygon_cartesian_tolerance": "0.001",
    }
    cfg = config.configuration(cfg_parser, {})
    assert cfg.spatial_polygon_cartesian_tolerance == 0.001


@patch("nsidc.metgen.metgen.os.path.exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.kinesis_stream_exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.staging_bucket_exists", return_value=True)
def test_spatial_polygon_cartesian_tolerance_validation_valid(m1, m2, m3, cfg_parser):
    """Test validation of valid spatial polygon cartesian tolerance values."""
    cfg_parser["Spatial"] = {"spatial_polygon_cartesian_tolerance": "0.001"}
    cfg = config.configuration(cfg_parser, {})
    assert config.validate(cfg) is True


@patch("nsidc.metgen.metgen.os.path.exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.kinesis_stream_exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.staging_bucket_exists", return_value=True)
def test_spatial_polygon_cartesian_tolerance_validation_too_low(m1, m2, m3, cfg_parser):
    """Test validation rejects spatial polygon cartesian tolerance below 0.00001."""
    cfg_parser["Spatial"] = {"spatial_polygon_cartesian_tolerance": "0.000001"}
    cfg = config.configuration(cfg_parser, {})
    with pytest.raises(config.ValidationError) as exc_info:
        config.validate(cfg)
    assert (
        "The spatial polygon cartesian tolerance must be between 0.00001 and 0.01 degrees."
        in exc_info.value.errors
    )


@patch("nsidc.metgen.metgen.os.path.exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.kinesis_stream_exists", return_value=True)
@patch("nsidc.metgen.metgen.aws.staging_bucket_exists", return_value=True)
def test_spatial_polygon_cartesian_tolerance_validation_too_high(
    m1, m2, m3, cfg_parser
):
    """Test validation rejects spatial polygon cartesian tolerance above 0.01."""
    cfg_parser["Spatial"] = {"spatial_polygon_cartesian_tolerance": "0.02"}
    cfg = config.configuration(cfg_parser, {})
    with pytest.raises(config.ValidationError) as exc_info:
        config.validate(cfg)
    assert (
        "The spatial polygon cartesian tolerance must be between 0.00001 and 0.01 degrees."
        in exc_info.value.errors
    )
