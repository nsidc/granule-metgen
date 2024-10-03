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

def test_banner():
    assert len(metgen.banner()) > 0

def test_read_config(cfg_parser):
    mapping = metgen.read_config(config.configuration(cfg_parser, {}))

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
