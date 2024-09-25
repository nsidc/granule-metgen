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
         'version': 42,
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
    expected_keys = set(['environment',
                         'data_dir',
                         'auth_id',
                         'version',
                         'provider',
                         'local_output_dir',
                         'ummg_dir',
                         'kinesis_arn'])
    config = metgen.configuration(cfg_parser)
    config_keys = set(config.__dict__)
    assert len(config_keys - expected_keys) == 0

    assert config.data_dir == '/data/example'
    assert config.auth_id == 'DATA-0001'
    assert config.kinesis_arn == 'abcd-1234'
    assert config.environment == 'uat'

def test_enhanced_config():
    myconfig = metgen.Config('env', 'data_dir', 'auth_id', 'version',
                  'provider', 'output_dir', 'ummg_dir', 'arn')
    enhanced_config = myconfig.enhance('pgid')
    assert set(['auth_id', 'version', 'producer_granule_id',
                'submission_time', 'uuid']) <= set(enhanced_config.keys())

def test_sums_file_sizes():
    details = {
        'first_id': {
            'size_in_bytes': 100,
            'production_date_time': 'then',
            'date_time': 'now',
            'geometry': 'big'
        },
        'second_id': {
            'size_in_bytes': 200,
            'production_date_time': 'before',
            'date_time': 'after',
            'geometry': 'small'
        }
    }
    summary = metgen.metadata_summary(details)
    assert summary['size_in_bytes'] == 300
    assert summary['production_date_time'] == 'then'
    assert summary['date_time'] == 'now'
    assert summary['geometry'] == 'big'
