from configparser import ConfigParser, ExtendedInterpolation
import dataclasses
from unittest.mock import patch

import pytest

from nsidc.metgen import config
from nsidc.metgen import constants


# Unit tests for the 'config' module functions.
#
# The test boundary is the config module's interface with the filesystem and
# the aws module, so in addition to testing the config module's behavior, the
# tests should mock those module's functions and assert that config functions
# call them with the correct parameters, correctly handle their return values,
# and handle any exceptions they may throw.

@pytest.fixture
def expected_keys():
    return set(['environment',
                'data_dir',
                'auth_id',
                'version',
                'provider',
                'local_output_dir',
                'ummg_dir',
                'kinesis_stream_name',
                'staging_bucket_name',
                'write_cnm_file',
                'overwrite_ummg',
                'checksum_type',
                'number'])

@pytest.fixture
def cfg_parser():
    cp = ConfigParser(interpolation=ExtendedInterpolation())
    cp['Source'] = {
         'data_dir': '/data/example'
    }
    cp['Collection'] = {
         'auth_id': 'DATA-0001',
         'version': 42,
         'provider': 'FOO'
    }
    cp['Destination'] = {
        'local_output_dir': '/output/here',
        'ummg_dir': 'ummg',
        'kinesis_stream_name': "xyzzy-${environment}-stream",
        'staging_bucket_name': "xyzzy-${environment}-bucket",
        'write_cnm_file': False
    }
    cp['Settings'] = {
        'checksum_type': 'SHA256',
        'number': -1
    }
    return cp


def test_config_parser_without_filename():
    with pytest.raises(ValueError):
        config.config_parser_factory(None)

@patch('nsidc.metgen.metgen.os.path.exists', return_value = True)
def test_config_parser_return_type(mock):
    result = config.config_parser_factory('foo.ini')
    assert isinstance(result, ConfigParser)

def test_config_from_config_parser(cfg_parser):
    cfg = config.configuration(cfg_parser, {}, constants.DEFAULT_CUMULUS_ENVIRONMENT)
    assert isinstance(cfg, config.Config)

def test_config_with_no_write_cnm(cfg_parser, expected_keys):
    cfg = config.configuration(cfg_parser, {}, constants.DEFAULT_CUMULUS_ENVIRONMENT)

    config_keys = set(cfg.__dict__)
    assert len(config_keys - expected_keys) == 0

    assert cfg.environment == 'uat'
    assert cfg.data_dir == '/data/example'
    assert cfg.auth_id == 'DATA-0001'
    assert cfg.kinesis_stream_name == 'xyzzy-uat-stream'
    assert not cfg.write_cnm_file

def test_config_with_write_cnm(cfg_parser, expected_keys):
    cfg_parser.set("Destination", "write_cnm_file", 'True')
    cfg = config.configuration(cfg_parser, {})

    config_keys = set(cfg.__dict__)
    assert len(config_keys - expected_keys) == 0

    assert cfg.data_dir == '/data/example'
    assert cfg.auth_id == 'DATA-0001'
    assert cfg.kinesis_stream_name == 'xyzzy-uat-stream'
    assert cfg.environment == 'uat'
    assert cfg.write_cnm_file == True

def test_config_with_no_overwrite_ummg(cfg_parser, expected_keys):
    cfg = config.configuration(cfg_parser, {}, constants.DEFAULT_CUMULUS_ENVIRONMENT)

    config_keys = set(cfg.__dict__)
    assert len(config_keys - expected_keys) == 0
    assert not cfg.overwrite_ummg

def test_config_with_overwrite_ummg(cfg_parser, expected_keys):
    cfg_parser.set("Destination", "overwrite_ummg", 'True')
    cfg = config.configuration(cfg_parser, {})

    config_keys = set(cfg.__dict__)
    assert len(config_keys - expected_keys) == 0
    assert cfg.overwrite_ummg == True

def test_enhanced_config(expected_keys):
    myconfig = config.Config(*expected_keys)
    enhanced_config = myconfig.enhance('pgid')
    assert set(myconfig.__dict__.keys()) <= set(enhanced_config.keys())

def test_get_configuration_value(cfg_parser):
    environment = constants.DEFAULT_CUMULUS_ENVIRONMENT
    result = config._get_configuration_value(environment, "Source", "data_dir", str, cfg_parser, {})
    assert result == cfg_parser.get("Source", "data_dir")

def test_get_configuration_value_with_override(cfg_parser):
    environment = constants.DEFAULT_CUMULUS_ENVIRONMENT
    overrides = { 'data_dir': 'foobar' }
    result = config._get_configuration_value(environment, "Source", "data_dir", str, cfg_parser, overrides)
    assert result == overrides['data_dir']

def test_get_configuration_value_interpolates_the_environment(cfg_parser):
    environment = constants.DEFAULT_CUMULUS_ENVIRONMENT
    result = config._get_configuration_value(environment, "Destination", "kinesis_stream_name", str, cfg_parser, {})
    assert result == "xyzzy-uat-stream"

@pytest.mark.parametrize("section,option,expected", [
        ("Destination", "kinesis_stream_name", f"nsidc-cumulus-{constants.DEFAULT_CUMULUS_ENVIRONMENT}-external_notification"),
        ("Destination", "staging_bucket_name", f"nsidc-cumulus-{constants.DEFAULT_CUMULUS_ENVIRONMENT}-ingest-staging"),
        ("Destination", "write_cnm_file", constants.DEFAULT_WRITE_CNM_FILE),
        ("Settings", "checksum_type", constants.DEFAULT_CHECKSUM_TYPE),
        ("Settings", "number", constants.DEFAULT_NUMBER),
    ])
def test_configuration_has_good_defaults(cfg_parser, section, option, expected):
    cfg_parser.remove_option(section, option)
    result = config.configuration(cfg_parser, {}, constants.DEFAULT_CUMULUS_ENVIRONMENT)
    result_dict = dataclasses.asdict(result)
    assert result_dict[option] == expected


@patch('nsidc.metgen.metgen.os.path.exists', return_value = True)
@patch('nsidc.metgen.metgen.aws.kinesis_stream_exists', return_value = True)
@patch('nsidc.metgen.metgen.aws.staging_bucket_exists', return_value = True)
def test_validate_with_valid_checks(m1, m2, cfg_parser):
    cfg = config.configuration(cfg_parser, {})
    valid, errors = config.validate(cfg)
    assert valid == True
    assert len(errors) == 0

@patch('nsidc.metgen.metgen.os.path.exists', return_value = False)
@patch('nsidc.metgen.metgen.aws.kinesis_stream_exists', return_value = False)
@patch('nsidc.metgen.metgen.aws.staging_bucket_exists', return_value = False)
def test_validate_with_invalid_checks(m1, m2, cfg_parser):
    cfg = config.configuration(cfg_parser, {})
    valid, errors = config.validate(cfg)
    assert valid == False
    assert len(errors) == 4
