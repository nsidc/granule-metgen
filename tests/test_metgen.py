from configparser import ConfigParser
from unittest.mock import patch

import pytest

from nsidc.metgen import metgen


@pytest.fixture
def cfg_parser():
    cp = ConfigParser()
    cp['Source'] = {
         'data_dir': '/data/example'
    }
    cp['Collection'] = {
         'auth_id': 'DATA-0001',
         'version': 1,
         'provider': 'FOO'
    }
    cp['Destination'] = {
        'local_output_dir': '/output/here',
        'ummg_dir': 'ummg',
        'kinesis_arn': 'abcd-1234'
    }
    return cp

def test_banner():
    assert len(metgen.banner()) > 0

def test_config_parser_without_filename():
    with pytest.raises(ValueError):
        metgen.config_parser(None)

@patch('nsidc.metgen.metgen.os.path.exists', return_value = True)
def test_config_parser_return_type(mock):
    result = metgen.config_parser('foo.ini')

    assert isinstance(result, ConfigParser)

def test_config_from_config_parser(cfg_parser):
    config = metgen.configuration(cfg_parser)

    assert isinstance(config, metgen.Config)

def test_config_with_values(cfg_parser):
    config = metgen.configuration(cfg_parser)

    assert config.data_dir == '/data/example'
    assert config.auth_id == 'DATA-0001'
    assert config.kinesis_arn == 'abcd-1234'
