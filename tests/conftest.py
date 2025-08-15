"""Shared test fixtures for the test suite."""

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
