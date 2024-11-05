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

@pytest.fixture
def fake_config():
    return config.Config('uat', 'data', 'auth_id', 'version',
                         'foobar', 'output', 'ummg', 'stream',
                         'bucket', True, True, 'sha', 3)

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

def test_s3_object_path_has_no_leading_slash():
    mapping = {
        'auth_id': 'ABCD',
        'version': 2,
        'uuid': 'abcd-1234',
    }
    expected = 'external/ABCD/2/abcd-1234/xyzzy.bin'
    assert metgen._s3_object_path(mapping, 'xyzzy.bin') == expected

def test_s3_url_simple_case():
    mapping = {
        'auth_id': 'ABCD',
        'version': 2,
        'uuid': 'abcd-1234',
        'staging_bucket_name': 'xyzzy-bucket'
    }
    expected = 's3://xyzzy-bucket/external/ABCD/2/abcd-1234/xyzzy.bin'
    assert metgen.s3_url(mapping, 'xyzzy.bin') == expected

@patch('nsidc.metgen.metgen.scrub_json_files')
def test_does_scrub_ummg(scrub_mock, fake_config):
    fake_config.overwrite_ummg = True
    metgen.prepare_output_dirs(fake_config)
    assert scrub_mock.called

@patch('nsidc.metgen.metgen.scrub_json_files')
def test_keeps_existing_ummg(scrub_mock, fake_config):
    fake_config.overwrite_ummg = False
    metgen.prepare_output_dirs(fake_config)
    assert not scrub_mock.called

@patch('nsidc.metgen.metgen.scrub_json_files')
def test_builds_output_paths(scrub_mock, fake_config):
    ummg_path, cnm_path = metgen.prepare_output_dirs(fake_config)
    assert str(ummg_path) == '/'.join([fake_config.local_output_dir, fake_config.ummg_dir])
    assert str(cnm_path) == '/'.join([fake_config.local_output_dir, 'cnm'])
