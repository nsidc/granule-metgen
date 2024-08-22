from configparser import ConfigParser
from unittest.mock import patch

import pytest

from nsidc.metgen import metgen


def test_banner():
    assert len(metgen.banner()) > 0

def test_config_parser_without_filename():
    with pytest.raises(ValueError):
        metgen.config_parser(None)

@patch('nsidc.metgen.metgen.os.path.exists', return_value = True)
def test_config_parser_return_type(mock):
    result = metgen.config_parser('foo.ini')

    assert isinstance(result, ConfigParser)

def test_config_from_config_parser():
    cfg_parser = ConfigParser()
    cfg_parser['Source'] = { 'data_dir': 'bar' }
    cfg_parser['Destination'] = {
        'kinesis_arn': 'abcd-1234',
        's3_url': 's3://example/xyzzy'
    }

    config = metgen.configuration(cfg_parser)

    assert isinstance(config, metgen.Config)

def test_config_with_values():
    cfg_parser = ConfigParser()
    cfg_parser['Source'] = { 'data_dir': '/data/example' }
    cfg_parser['Destination'] = {
        'kinesis_arn': 'abcd-1234',
        's3_url': 's3://example/xyzzy'
    }

    config = metgen.configuration(cfg_parser)

    assert config.source_data_dir == '/data/example'
    assert config.destination_kinesis_arn == 'abcd-1234'
