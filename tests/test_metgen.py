from configparser import ConfigParser
from unittest.mock import patch

import pytest

from nsidc.metgen import config
from nsidc.metgen import metgen

# Unit tests for the 'metgen' module functions.
#
# The test boundary is the metgen module's interface with the filesystem and
# the aws & config modules, so in addition to testing the metgen module's
# behavior, the tests should mock those module's functions and assert that
# metgen functions call them with the correct parameters, correctly handle
# their return values, and handle any exceptions they may throw.

@pytest.fixture
def granule_metadata_list():
    return {
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

@pytest.fixture
def one_granule_metadata():
    return {
        'first_id': {
            'size_in_bytes': 150,
            'production_date_time': 'then',
            'temporal': 'now',
            'geometry': 'big'
        }
    }

def test_banner():
    assert len(metgen.banner()) > 0

def test_gets_single_file_size(one_granule_metadata):
    summary = metgen.metadata_summary(one_granule_metadata)
    assert summary['size_in_bytes'] == 150

def test_sums_multiple_file_sizes(granule_metadata_list):
    summary = metgen.metadata_summary(granule_metadata_list)
    assert summary['size_in_bytes'] == 300

def test_uses_first_file_as_default(granule_metadata_list):
    summary = metgen.metadata_summary(granule_metadata_list)
    assert summary['production_date_time'] == 'then'
    assert summary['temporal'] == 'now'
    assert summary['geometry'] == 'big'

def test_returns_only_gpolygon():
    result = metgen.populate_spatial({'points': 'some list of points'})
    assert "GPolygons" in result

def test_returns_single_datetime():
    result = metgen.populate_temporal([123])
    assert '"SingleDateTime": "123"' in result

def test_returns_datetime_range():
    result = metgen.populate_temporal([123, 456])
    assert 'RangeDateTime' in result
    assert '"BeginningDateTime": "123"' in result
    assert '"EndingDateTime": "456"' in result
