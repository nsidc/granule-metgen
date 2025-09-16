"""Shared test fixtures for the test suite."""

from configparser import ConfigParser, ExtendedInterpolation

import pytest

from nsidc.metgen.models import CollectionMetadata


@pytest.fixture
def simple_collection_metadata():
    """Standard test collection metadata used across multiple test files.

    Returns a CollectionMetadata instance with minimal required fields
    that can be used as-is, or as a base for more specific tests.
    """
    return CollectionMetadata(
        short_name="ABCD", version="2", entry_title="Test Collection ABCD V002"
    )


@pytest.fixture
def cfg_parser():
    cp = ConfigParser(interpolation=ExtendedInterpolation())
    cp["Source"] = {"data_dir": "/data/example"}
    cp["Collection"] = {"auth_id": "DATA-0001", "version": 42, "provider": "FOO"}
    cp["Destination"] = {
        "local_output_dir": "/output/here",
        "ummg_dir": "ummg",
        "kinesis_stream_name": "xyzzy-${environment}-stream",
        "staging_bucket_name": "xyzzy-${environment}-bucket",
        "write_cnm_file": False,
    }
    cp["Settings"] = {
        "checksum_type": "SHA256",
        "number": 1,
        "log_dir": "/tmp",
    }
    return cp
