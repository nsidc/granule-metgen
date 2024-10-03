from configparser import ConfigParser
from unittest.mock import patch

import pytest

from nsidc.metgen import config
from nsidc.metgen import constants
from nsidc.metgen import metgen


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
        'kinesis_arn': 'abcd-1234'
    }
    return cp


def test_config_parser_without_filename():
    with pytest.raises(ValueError):
        config.config_parser(None)

@patch('nsidc.metgen.metgen.os.path.exists', return_value = True)
def test_config_parser_return_type(mock):
    result = config.config_parser('foo.ini')
    assert isinstance(result, ConfigParser)

def test_config_from_config_parser(cfg_parser):
    cfg = config.configuration(cfg_parser, {}, constants.DEFAULT_CUMULUS_ENVIRONMENT)
    assert isinstance(cfg, config.Config)

def test_config_with_values(cfg_parser):
    expected_keys = set(['environment',
                         'data_dir',
                         'auth_id',
                         'version',
                         'provider',
                         'local_output_dir',
                         'ummg_dir',
                         'kinesis_arn',
                         'write_cnm_file',
                         'checksum_type'])
    cfg = config.configuration(cfg_parser, {})

    config_keys = set(cfg.__dict__)
    assert len(config_keys - expected_keys) == 0

    assert cfg.data_dir == '/data/example'
    assert cfg.auth_id == 'DATA-0001'
    assert cfg.kinesis_arn == 'abcd-1234'
    assert cfg.environment == 'uat'

def test_enhanced_config():
    myconfig = config.Config('env', 'data_dir', 'auth_id', 'version',
                  'provider', 'output_dir', 'ummg_dir', 'arn', 'write_cnm_file', 'checksum_type')
    enhanced_config = myconfig.enhance('pgid')
    assert set(['auth_id', 'version', 'producer_granule_id',
                'submission_time', 'uuid']) <= set(enhanced_config.keys())

def test_get_configuration_value(cfg_parser):
    result = config._get_configuration_value("Source", "data_dir", cfg_parser, {})
    assert result == cfg_parser.get("Source", "data_dir")

def test_get_configuration_value_with_override(cfg_parser):
    overrides = { 'data_dir': 'foobar' }
    result = config._get_configuration_value("Source", "data_dir", cfg_parser, overrides)
    assert result == overrides['data_dir']

def test_get_configuration_value_with_default(cfg_parser):
    default_value = '/etc/foobar'
    result = config._get_configuration_value("Source", "foobar_dir", cfg_parser, {}, default_value)
    assert result == default_value

def test_get_configuration_value_with_default_and_override(cfg_parser):
    overrides = { 'data_dir': 'foobar' }
    default_value = '/etc/foobar'
    result = config._get_configuration_value("Source", "data_dir", cfg_parser, overrides, default_value)
    assert result == overrides['data_dir']
