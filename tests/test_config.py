from configparser import ConfigParser
from unittest.mock import patch

import pytest

from nsidc.metgen import config
from nsidc.metgen import constants
from nsidc.metgen import metgen


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
                'kinesis_arn',
                'write_cnm_file',
                'checksum_type',
                'number'])

@pytest.fixture
def cfg_parser():
    cp = ConfigParser()
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
        'kinesis_arn': 'abcd-1234',
        'write_cnm_file': False
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
    cfg = config.configuration(cfg_parser, {})

    config_keys = set(cfg.__dict__)
    assert len(config_keys - expected_keys) == 0

    assert cfg.data_dir == '/data/example'
    assert cfg.auth_id == 'DATA-0001'
    assert cfg.kinesis_arn == 'abcd-1234'
    assert cfg.environment == 'uat'
    assert not cfg.write_cnm_file

def test_config_with_write_cnm(cfg_parser, expected_keys):
    cfg_parser.set("Destination", "write_cnm_file", 'True')
    cfg = config.configuration(cfg_parser, {})

    config_keys = set(cfg.__dict__)
    assert len(config_keys - expected_keys) == 0

    assert cfg.data_dir == '/data/example'
    assert cfg.auth_id == 'DATA-0001'
    assert cfg.kinesis_arn == 'abcd-1234'
    assert cfg.environment == 'uat'
    assert cfg.write_cnm_file == True

def test_enhanced_config():
    myconfig = config.Config('env', 'data_dir', 'auth_id', 'version',
                  'provider', 'output_dir', 'ummg_dir', 'arn',
                  'write_cnm_file', 'checksum_type', 'number')
    enhanced_config = myconfig.enhance('pgid')
    assert set(['auth_id', 'version', 'producer_granule_id',
                'submission_time', 'uuid']) <= set(enhanced_config.keys())

def test_get_configuration_value(cfg_parser):
    result = config._get_configuration_value("Source", "data_dir", str, cfg_parser, {})
    assert result == cfg_parser.get("Source", "data_dir")

def test_get_configuration_value_with_override(cfg_parser):
    overrides = { 'data_dir': 'foobar' }
    result = config._get_configuration_value("Source", "data_dir", str, cfg_parser, overrides)
    assert result == overrides['data_dir']

def test_get_configuration_value_with_default(cfg_parser):
    default_value = '/etc/foobar'
    result = config._get_configuration_value("Source", "foobar_dir", str, cfg_parser, {}, default_value)
    assert result == default_value

def test_get_configuration_value_with_default_and_override(cfg_parser):
    overrides = { 'data_dir': 'foobar' }
    default_value = '/etc/foobar'
    result = config._get_configuration_value("Source", "data_dir", str, cfg_parser, overrides, default_value)
    assert result == overrides['data_dir']
