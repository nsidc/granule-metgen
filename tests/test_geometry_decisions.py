"""
Unit tests for the geometry_decisions module.

These tests verify that geometry specifications are correctly determined
based on configuration, collection metadata, and available files.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from nsidc.metgen.config import Config
from nsidc.metgen.geometry_decisions import (
    GeometrySource,
    GeometryType,
    determine_geometry_spec,
)
from nsidc.metgen.models import Collection


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
        collection_geometry_override=False,
        spatial_polygon_enabled=False,
    )


@pytest.fixture
def collection():
    """Create a test collection with spatial representation."""
    return Collection(
        short_name="TEST",
        version="1",
        entry_title="Test Collection",
        granule_spatial_representation="GEODETIC",
        spatial_extent=[
            {
                "WestBoundingCoordinate": -180,
                "EastBoundingCoordinate": 180,
                "NorthBoundingCoordinate": 90,
                "SouthBoundingCoordinate": -90,
            }
        ],
    )


@pytest.fixture
def collection_cartesian():
    """Create a test collection with cartesian representation."""
    return Collection(
        short_name="TEST",
        version="1",
        entry_title="Test Collection",
        granule_spatial_representation="CARTESIAN",
        spatial_extent=[
            {
                "WestBoundingCoordinate": 0,
                "EastBoundingCoordinate": 100,
                "NorthBoundingCoordinate": 100,
                "SouthBoundingCoordinate": 0,
            }
        ],
    )


@pytest.fixture
def collection_no_spatial():
    """Create a test collection without spatial representation."""
    return Collection(
        short_name="TEST",
        version="1",
        entry_title="Test Collection",
        granule_spatial_representation=None,
    )


class TestGeometryDecisions:
    """Test the geometry decision logic."""

    def test_no_spatial_representation(self, config, collection_no_spatial):
        """Test when collection has no spatial representation."""
        spec = determine_geometry_spec(
            config,
            collection_no_spatial,
            "test_granule",
            {Path("test.nc")},
        )

        assert spec.source == GeometrySource.NOT_PROVIDED
        assert spec.geometry_type == GeometryType.NONE
        assert spec.representation is None

    def test_collection_geometry_override(self, config, collection):
        """Test when collection geometry override is enabled."""
        config.collection_geometry_override = True

        spec = determine_geometry_spec(
            config,
            collection,
            "test_granule",
            {Path("test.nc")},
        )

        assert spec.source == GeometrySource.COLLECTION
        assert spec.geometry_type == GeometryType.BOUNDING_BOX
        assert spec.representation == "CARTESIAN"

    def test_spatial_file_match(self, config, collection):
        """Test when a matching spatial file is found."""
        spatial_files = [
            Path("/data/test_granule.nc.spatial"),
            Path("/data/other_granule.nc.spatial"),
        ]

        spec = determine_geometry_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
            spatial_files,
        )

        assert spec.source == GeometrySource.SPATIAL_FILE
        assert spec.geometry_type == GeometryType.POLYGON
        assert spec.representation == "GEODETIC"
        assert spec.spatial_filename == "/data/test_granule.nc.spatial"

    def test_spatial_file_no_match(self, config, collection):
        """Test when no matching spatial file is found."""
        spatial_files = [
            Path("/data/other_granule.nc.spatial"),
            Path("/data/another_granule.nc.spatial"),
        ]

        spec = determine_geometry_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
            spatial_files,
        )

        assert spec.source == GeometrySource.GRANULE_METADATA
        assert spec.geometry_type == GeometryType.POLYGON
        assert spec.representation == "GEODETIC"

    def test_granule_metadata_default(self, config, collection):
        """Test default case extracting from granule metadata."""
        spec = determine_geometry_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
        )

        assert spec.source == GeometrySource.GRANULE_METADATA
        assert spec.geometry_type == GeometryType.POLYGON
        assert spec.representation == "GEODETIC"

    def test_cartesian_representation(self, config, collection_cartesian):
        """Test with cartesian spatial representation."""
        spec = determine_geometry_spec(
            config,
            collection_cartesian,
            "test_granule",
            {Path("test_granule.nc")},
        )

        assert spec.source == GeometrySource.GRANULE_METADATA
        assert spec.geometry_type == GeometryType.POLYGON
        assert spec.representation == "CARTESIAN"

    def test_empty_spatial_files(self, config, collection):
        """Test with empty spatial files list."""
        spec = determine_geometry_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
            [],
        )

        assert spec.source == GeometrySource.GRANULE_METADATA
        assert spec.geometry_type == GeometryType.POLYGON

    def test_none_spatial_files(self, config, collection):
        """Test with None spatial files."""
        spec = determine_geometry_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
            None,
        )

        assert spec.source == GeometrySource.GRANULE_METADATA
        assert spec.geometry_type == GeometryType.POLYGON

    def test_multiple_data_files(self, config, collection):
        """Test with multiple science data files."""
        data_files = {
            Path("test_granule_01.nc"),
            Path("test_granule_02.nc"),
            Path("test_granule_03.nc"),
        }

        spec = determine_geometry_spec(
            config,
            collection,
            "test_granule",
            data_files,
        )

        assert spec.source == GeometrySource.GRANULE_METADATA
        assert spec.geometry_type == GeometryType.POLYGON

    @patch("nsidc.metgen.geometry_decisions.logger")
    def test_logging_no_spatial_representation(
        self, mock_logger, config, collection_no_spatial
    ):
        """Test that appropriate logging occurs when no spatial representation."""
        determine_geometry_spec(
            config,
            collection_no_spatial,
            "test_granule",
            {Path("test.nc")},
        )

        mock_logger.debug.assert_called_with(
            "No granule spatial representation for test_granule"
        )

    @patch("nsidc.metgen.geometry_decisions.logger")
    def test_logging_collection_override(self, mock_logger, config, collection):
        """Test that appropriate logging occurs for collection override."""
        config.collection_geometry_override = True

        determine_geometry_spec(
            config,
            collection,
            "test_granule",
            {Path("test.nc")},
        )

        mock_logger.debug.assert_called_with(
            "Using collection geometry override for test_granule"
        )

    @patch("nsidc.metgen.geometry_decisions.logger")
    def test_logging_spatial_file(self, mock_logger, config, collection):
        """Test that appropriate logging occurs when spatial file is found."""
        spatial_files = [Path("/data/test_granule.nc.spatial")]

        determine_geometry_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
            spatial_files,
        )

        mock_logger.debug.assert_called_with(
            "Found spatial file /data/test_granule.nc.spatial for test_granule"
        )

    @patch("nsidc.metgen.geometry_decisions.logger")
    def test_logging_granule_metadata(self, mock_logger, config, collection):
        """Test that appropriate logging occurs for granule metadata extraction."""
        determine_geometry_spec(
            config,
            collection,
            "test_granule",
            {Path("test.nc")},
        )

        mock_logger.debug.assert_called_with(
            "Will extract geometry from granule metadata for test_granule"
        )

    def test_spatial_file_partial_match(self, config, collection):
        """Test that spatial file matching requires full granule name."""
        spatial_files = [
            Path("/data/test.nc.spatial"),  # Partial match
            Path("/data/test_granule_v2.nc.spatial"),  # Contains but not exact
        ]

        spec = determine_geometry_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
            spatial_files,
        )

        # Should not match partial names
        assert spec.source == GeometrySource.GRANULE_METADATA
        assert spec.spatial_filename is None
