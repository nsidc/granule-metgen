from configparser import ConfigParser
import datetime as dt
from unittest.mock import patch

from funcy import identity, partial
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
    granule = metgen.Granule(
        'foo',
        metgen.Collection('ABCD', 2),
        uuid='abcd-1234'
    )
    expected = 'external/ABCD/2/abcd-1234/xyzzy.bin'
    assert metgen.s3_object_path(granule, 'xyzzy.bin') == expected

def test_s3_url_simple_case():
    staging_bucket_name = 'xyzzy-bucket'
    granule = metgen.Granule(
        'foo',
        metgen.Collection('ABCD', 2),
        uuid='abcd-1234'
    )
    expected = 's3://xyzzy-bucket/external/ABCD/2/abcd-1234/xyzzy.bin'
    assert metgen.s3_url(staging_bucket_name, granule, 'xyzzy.bin') == expected

@patch("nsidc.metgen.metgen.dt.datetime")
def test_start_ledger(mock_datetime):
    now = dt.datetime(2099, 7, 4, 10, 11, 12)
    mock_datetime.now.return_value = now
    granule = metgen.Granule('abcd-1234')

    actual = metgen.start_ledger(granule)

    assert actual.granule == granule
    assert actual.startDatetime == now

@patch("nsidc.metgen.metgen.dt.datetime")
def test_end_ledger(mock_datetime):
    now = dt.datetime(2099, 7, 4, 10, 11, 12)
    mock_datetime.now.return_value = now
    granule = metgen.Granule('abcd-1234')
    ledger = metgen.Ledger(granule, [metgen.Action('foo', True, '')], startDatetime = now)

    actual = metgen.end_ledger(ledger)

    assert actual.granule == granule
    assert actual.successful == True
    assert actual.startDatetime == now
    assert actual.endDatetime == now

@patch("nsidc.metgen.metgen.dt.datetime")
def test_end_ledger_with_unsuccessful_actions(mock_datetime):
    now = dt.datetime(2099, 7, 4, 10, 11, 12)
    mock_datetime.now.return_value = now
    granule = metgen.Granule('abcd-1234')
    ledger = metgen.Ledger(granule,
                           [metgen.Action('foo', False, ''), metgen.Action('bar', False, 'Oops')],
                           startDatetime = now)

    actual = metgen.end_ledger(ledger)

    assert actual.granule == granule
    assert actual.successful == False
    assert actual.startDatetime == now
    assert actual.endDatetime == now

def test_recorder():
    granule = metgen.Granule('abcd-1234')
    ledger = metgen.start_ledger(granule)

    new_ledger = partial(metgen.recorder, identity)(ledger)

    assert new_ledger.granule == ledger.granule
    assert len(new_ledger.actions) == 1

def test_recorder_with_failing_operation():
    granule = metgen.Granule('abcd-1234')
    ledger = metgen.start_ledger(granule)
    def failing_op():
        raise Exception()

    new_ledger = partial(metgen.recorder, failing_op)(ledger)

    assert new_ledger.granule == ledger.granule
    assert len(new_ledger.actions) == 1
    assert new_ledger.actions[0].successful == False
