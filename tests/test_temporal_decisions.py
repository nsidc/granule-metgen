"""
Unit tests for the temporal_decisions module.

These tests verify that temporal specifications are correctly determined
based on configuration, collection metadata, and available files.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from nsidc.metgen.config import Config
from nsidc.metgen.models import Collection
from nsidc.metgen.temporal_decisions import (
    TemporalSource,
    TemporalType,
    determine_temporal_spec,
)


@pytest.fixture
def config():
    """Create a test configuration."""
    return Config(
        environment="uat",
        data_dir="/data",
        auth_id="TEST",
        version="1",
        provider="NSIDC",
        local_output_dir="/output",
        ummg_dir="ummg",
        kinesis_stream_name="test-stream",
        staging_bucket_name="test-bucket",
        write_cnm_file=True,
        overwrite_ummg=True,
        checksum_type="sha256",
        number=10,
        dry_run=False,
        collection_temporal_override=False,
        time_start_regex=None,
        time_coverage_duration=None,
    )


@pytest.fixture
def collection():
    """Create a test collection with temporal extent."""
    return Collection(
        short_name="TEST",
        version="1",
        entry_title="Test Collection",
        temporal_extent=[
            {
                "BeginningDateTime": "2023-01-01T00:00:00.000Z",
                "EndingDateTime": "2023-12-31T23:59:59.999Z",
            }
        ],
        temporal_extent_error=None,
    )


@pytest.fixture
def collection_single_temporal():
    """Create a test collection with single temporal value."""
    return Collection(
        short_name="TEST",
        version="1",
        entry_title="Test Collection",
        temporal_extent=["2023-06-15T12:00:00.000Z"],
        temporal_extent_error=None,
    )


@pytest.fixture
def collection_temporal_error():
    """Create a test collection with temporal extent error."""
    return Collection(
        short_name="TEST",
        version="1",
        entry_title="Test Collection",
        temporal_extent=None,
        temporal_extent_error="Multiple temporal extents found",
    )


class TestTemporalDecisions:
    """Test the temporal decision logic."""

    def test_collection_temporal_override_range(self, config, collection):
        """Test when collection temporal override is enabled with range temporal."""
        config.collection_temporal_override = True

        spec = determine_temporal_spec(
            config,
            collection,
            "test_granule",
            {Path("test.nc")},
        )

        assert spec.source == TemporalSource.COLLECTION
        assert spec.temporal_type == TemporalType.RANGE_DATETIME
        assert spec.collection_override is True

    def test_collection_temporal_override_single(
        self, config, collection_single_temporal
    ):
        """Test when collection temporal override is enabled with single temporal."""
        config.collection_temporal_override = True

        spec = determine_temporal_spec(
            config,
            collection_single_temporal,
            "test_granule",
            {Path("test.nc")},
        )

        assert spec.source == TemporalSource.COLLECTION
        assert spec.temporal_type == TemporalType.SINGLE_DATETIME
        assert spec.collection_override is True

    def test_collection_temporal_override_with_error(
        self, config, collection_temporal_error
    ):
        """Test when collection temporal override has error."""
        config.collection_temporal_override = True

        spec = determine_temporal_spec(
            config,
            collection_temporal_error,
            "test_granule",
            {Path("test.nc")},
        )

        assert spec.source == TemporalSource.NOT_PROVIDED
        assert spec.temporal_type == TemporalType.NONE
        assert spec.collection_override is True

    def test_premet_file_match(self, config, collection):
        """Test when a matching premet file is found."""
        premet_files = [
            Path("/data/test_granule.nc.premet"),
            Path("/data/other_granule.nc.premet"),
        ]

        spec = determine_temporal_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
            premet_files,
        )

        assert spec.source == TemporalSource.PREMET_FILE
        assert spec.temporal_type == TemporalType.RANGE_DATETIME
        assert spec.premet_filename == "/data/test_granule.nc.premet"

    def test_premet_file_no_match(self, config, collection):
        """Test when no matching premet file is found."""
        premet_files = [
            Path("/data/other_granule.nc.premet"),
            Path("/data/another_granule.nc.premet"),
        ]

        spec = determine_temporal_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
            premet_files,
        )

        assert spec.source == TemporalSource.GRANULE_METADATA
        assert spec.temporal_type == TemporalType.SINGLE_DATETIME

    def test_granule_metadata_default(self, config, collection):
        """Test default case extracting from granule metadata."""
        spec = determine_temporal_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
        )

        assert spec.source == TemporalSource.GRANULE_METADATA
        assert spec.temporal_type == TemporalType.SINGLE_DATETIME
        assert spec.metadata_fields is None

    def test_granule_metadata_with_time_coverage(self, config, collection):
        """Test when time coverage duration is configured."""
        config.time_coverage_duration = "P1D"  # 1 day duration

        spec = determine_temporal_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
        )

        assert spec.source == TemporalSource.GRANULE_METADATA
        assert spec.temporal_type == TemporalType.RANGE_DATETIME

    def test_granule_metadata_with_time_regex(self, config, collection):
        """Test when time start regex is configured."""
        config.time_start_regex = r"(\d{4})(\d{2})(\d{2})"

        spec = determine_temporal_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
        )

        assert spec.source == TemporalSource.GRANULE_METADATA
        assert spec.temporal_type == TemporalType.SINGLE_DATETIME
        assert spec.metadata_fields is None  # Reader will use the regex

    def test_empty_premet_files(self, config, collection):
        """Test with empty premet files list."""
        spec = determine_temporal_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
            [],
        )

        assert spec.source == TemporalSource.GRANULE_METADATA
        assert spec.temporal_type == TemporalType.SINGLE_DATETIME

    def test_none_premet_files(self, config, collection):
        """Test with None premet files."""
        spec = determine_temporal_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
            None,
        )

        assert spec.source == TemporalSource.GRANULE_METADATA
        assert spec.temporal_type == TemporalType.SINGLE_DATETIME

    @patch("nsidc.metgen.temporal_decisions.logger")
    def test_logging_collection_override(self, mock_logger, config, collection):
        """Test that appropriate logging occurs for collection override."""
        config.collection_temporal_override = True

        determine_temporal_spec(
            config,
            collection,
            "test_granule",
            {Path("test.nc")},
        )

        mock_logger.debug.assert_called_with(
            "Using collection temporal override for test_granule"
        )

    @patch("nsidc.metgen.temporal_decisions.logger")
    def test_logging_collection_error(
        self, mock_logger, config, collection_temporal_error
    ):
        """Test that warning is logged for collection temporal error."""
        config.collection_temporal_override = True

        determine_temporal_spec(
            config,
            collection_temporal_error,
            "test_granule",
            {Path("test.nc")},
        )

        mock_logger.warning.assert_called_with(
            "Collection temporal extent has error: Multiple temporal extents found"
        )

    @patch("nsidc.metgen.temporal_decisions.logger")
    def test_logging_premet_file(self, mock_logger, config, collection):
        """Test that appropriate logging occurs when premet file is found."""
        premet_files = [Path("/data/test_granule.nc.premet")]

        determine_temporal_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
            premet_files,
        )

        mock_logger.debug.assert_called_with(
            "Found premet file /data/test_granule.nc.premet for test_granule"
        )

    @patch("nsidc.metgen.temporal_decisions.logger")
    def test_logging_granule_metadata(self, mock_logger, config, collection):
        """Test that appropriate logging occurs for granule metadata extraction."""
        determine_temporal_spec(
            config,
            collection,
            "test_granule",
            {Path("test.nc")},
        )

        mock_logger.debug.assert_called_with(
            "Will extract temporal from granule metadata for test_granule"
        )

    def test_premet_file_partial_match(self, config, collection):
        """Test that premet file matching requires full granule name."""
        premet_files = [
            Path("/data/test.nc.premet"),  # Partial match
            Path("/data/test_granule_v2.nc.premet"),  # Contains but not exact
        ]

        spec = determine_temporal_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
            premet_files,
        )

        # Should not match partial names
        assert spec.source == TemporalSource.GRANULE_METADATA
        assert spec.premet_filename is None

    def test_multiple_data_files(self, config, collection):
        """Test with multiple science data files."""
        data_files = {
            Path("test_granule_01.nc"),
            Path("test_granule_02.nc"),
            Path("test_granule_03.nc"),
        }

        spec = determine_temporal_spec(
            config,
            collection,
            "test_granule",
            data_files,
        )

        assert spec.source == TemporalSource.GRANULE_METADATA
        assert spec.temporal_type == TemporalType.SINGLE_DATETIME
