from configparser import ConfigParser
from unittest.mock import patch

import pytest

from nsidc.metgen import config
from nsidc.metgen import constants
from nsidc.metgen import metgen

# Unit tests for the 'metgen' module functions.
#
# The test boundary is the metgen module's interface with the filesystem and
# the aws & config modules, so in addition to testing the metgen module's
# behavior, the tests should mock those module's functions and assert that
# metgen functions call them with the correct parameters, correctly handle
# their return values, and handle any exceptions they may throw.

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
        'kinesis_stream_name': 'xyzzy-stream'
    }
    return cp

def test_banner():
    assert len(metgen.banner()) > 0

def test_sums_file_sizes():
    details = {
        'first_id': {
            'size_in_bytes': 100,
            'production_date_time': 'then',
            'temporal': 'now',
            'geometry': 'big'
        },
        'second_id': {
            'size_in_bytes': 200,
            'production_date_time': 'before',
            'temporal': 'after',
            'geometry': 'small'
        }
    }
    summary = metgen.metadata_summary(details)
    assert summary['size_in_bytes'] == 300
    assert summary['production_date_time'] == 'then'
    assert summary['temporal'] == 'now'
    assert summary['geometry'] == 'big'

# TODO: Test that it writes files if 'write cnm' flag is True

# TODO: Test that it does not write files if 'write cnm' flag is False
