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
        assert spec.representation == "NONE"
        # Test the callable
        assert spec.get_geometry_type(0) == GeometryType.NONE
        assert spec.get_geometry_type(10) == GeometryType.NONE

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
        assert spec.representation == "CARTESIAN"
        # Collection always returns bounding box
        assert spec.get_geometry_type(0) == GeometryType.BOUNDING_BOX
        assert spec.get_geometry_type(10) == GeometryType.BOUNDING_BOX

    def test_spatial_file_match(self, config, collection):
        """Test when .spatial files exist."""
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
        assert spec.representation == "GEODETIC"
        # Test geodetic .spatial rules
        assert spec.get_geometry_type(1) == GeometryType.POINT
        assert spec.get_geometry_type(2) == GeometryType.POLYGON
        assert spec.get_geometry_type(5) == GeometryType.POLYGON

    def test_granule_metadata_default(self, config, collection):
        """Test default case extracting from granule metadata."""
        spec = determine_geometry_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
        )

        assert spec.source == GeometrySource.GRANULE_METADATA
        assert spec.representation == "GEODETIC"
        # Granule metadata with geodetic always returns polygon
        assert spec.get_geometry_type(0) == GeometryType.POLYGON
        assert spec.get_geometry_type(100) == GeometryType.POLYGON

    def test_cartesian_representation(self, config, collection_cartesian):
        """Test with cartesian spatial representation."""
        spec = determine_geometry_spec(
            config,
            collection_cartesian,
            "test_granule",
            {Path("test_granule.nc")},
        )

        assert spec.source == GeometrySource.GRANULE_METADATA
        assert spec.representation == "CARTESIAN"
        # Granule metadata with cartesian always returns bounding box
        assert spec.get_geometry_type(0) == GeometryType.BOUNDING_BOX
        assert spec.get_geometry_type(100) == GeometryType.BOUNDING_BOX

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
        assert spec.representation == "GEODETIC"

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
        assert spec.representation == "GEODETIC"

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
        """Test that appropriate logging occurs when spatial files exist."""
        spatial_files = [Path("/data/test_granule.nc.spatial")]

        determine_geometry_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
            spatial_files,
        )

        mock_logger.debug.assert_called_with(
            "Processing with .spatial file rules for test_granule"
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


class TestSpoFileHandling:
    """Test .spo file handling according to README rules."""

    def test_spo_file_with_geodetic(self, config, collection):
        """Test .spo file with geodetic representation (valid case)."""
        spatial_files = [
            Path("/data/test_granule.nc.spo"),
            Path("/data/test_granule.nc.spatial"),  # Should prefer .spo
        ]

        spec = determine_geometry_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
            spatial_files,
        )

        assert spec.source == GeometrySource.SPATIAL_FILE
        assert spec.representation == "GEODETIC"
        # Test .spo rules - valid polygon
        assert spec.get_geometry_type(3) == GeometryType.POLYGON
        assert spec.get_geometry_type(10) == GeometryType.POLYGON
        # Test invalid point counts
        with pytest.raises(ValueError, match="at least 3 points"):
            spec.get_geometry_type(2)
        with pytest.raises(ValueError, match="at least 3 points"):
            spec.get_geometry_type(1)

    @patch("nsidc.metgen.geometry_decisions.logger")
    def test_spo_file_with_cartesian_error(
        self, mock_logger, config, collection_cartesian
    ):
        """Test .spo file with cartesian representation (error case)."""
        spatial_files = [Path("/data/test_granule.nc.spo")]

        spec = determine_geometry_spec(
            config,
            collection_cartesian,
            "test_granule",
            {Path("test_granule.nc")},
            spatial_files,
        )

        # Should return error state
        assert spec.source == GeometrySource.NOT_PROVIDED
        assert spec.representation == "CARTESIAN"
        assert spec.get_geometry_type(10) == GeometryType.NONE

        # Should log error
        mock_logger.error.assert_called()
        error_msg = mock_logger.error.call_args[0][0]
        assert ".spo files require GEODETIC" in error_msg

    def test_spo_file_priority_over_spatial(self, config, collection):
        """Test that .spo files have priority over .spatial files."""
        spatial_files = [
            Path("/data/test_granule.nc.spatial"),
            Path("/data/test_granule.nc.spo"),
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
        # Should have .spo rules (error on <=2 points)
        with pytest.raises(ValueError, match="at least 3 points"):
            spec.get_geometry_type(2)

    @patch("nsidc.metgen.geometry_decisions.logger")
    def test_logging_spo_file_found(self, mock_logger, config, collection):
        """Test logging when .spo files exist."""
        spatial_files = [Path("/data/test_granule.nc.spo")]

        determine_geometry_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
            spatial_files,
        )

        mock_logger.debug.assert_any_call(
            "Processing with .spo file rules for test_granule"
        )


class TestSpatialFileWithSpoDistinction:
    """Test .spatial file handling when .spo files might also exist."""

    def test_spatial_file_with_cartesian(self, config, collection_cartesian):
        """Test .spatial file with cartesian."""
        spatial_files = [Path("/data/test_granule.nc.spatial")]

        spec = determine_geometry_spec(
            config,
            collection_cartesian,
            "test_granule",
            {Path("test_granule.nc")},
            spatial_files,
        )

        assert spec.source == GeometrySource.SPATIAL_FILE
        assert spec.representation == "CARTESIAN"
        # Test cartesian .spatial rules
        with pytest.raises(ValueError, match="single point with CARTESIAN"):
            spec.get_geometry_type(1)
        assert spec.get_geometry_type(2) == GeometryType.BOUNDING_BOX
        with pytest.raises(ValueError, match="Only 2 points"):
            spec.get_geometry_type(3)

    def test_spatial_file_with_geodetic(self, config, collection):
        """Test .spatial file with geodetic."""
        spatial_files = [Path("/data/test_granule.nc.spatial")]

        spec = determine_geometry_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
            spatial_files,
        )

        assert spec.source == GeometrySource.SPATIAL_FILE
        assert spec.representation == "GEODETIC"
        # Test geodetic .spatial rules
        assert spec.get_geometry_type(1) == GeometryType.POINT
        assert spec.get_geometry_type(2) == GeometryType.POLYGON
        assert spec.get_geometry_type(10) == GeometryType.POLYGON
        with pytest.raises(ValueError, match="no points found"):
            spec.get_geometry_type(0)

    def test_no_spo_fallback_to_spatial(self, config, collection):
        """Test that collection uses .spo rules when any .spo files exist."""
        spatial_files = [
            Path("/data/test_granule.nc.spatial"),
            Path("/data/other_granule.nc.spo"),  # Different granule
        ]

        spec = determine_geometry_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
            spatial_files,
        )

        # Should have .spo rules since .spo files exist in collection
        with pytest.raises(ValueError, match="at least 3 points"):
            spec.get_geometry_type(1)

    def test_only_spatial_files_no_spo(self, config, collection):
        """Test .spatial rules when only .spatial files exist (no .spo)."""
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

        # Should have .spatial rules (no .spo files in collection)
        assert spec.get_geometry_type(1) == GeometryType.POINT
        assert spec.get_geometry_type(2) == GeometryType.POLYGON

    def test_mixed_file_types(self, config, collection):
        """Test handling of mixed .spo and .spatial files."""
        spatial_files = [
            Path("/data/granule1.nc.spo"),
            Path("/data/granule2.nc.spatial"),
            Path("/data/test_granule.nc.spatial"),
            Path("/data/granule3.nc.spo"),
        ]

        spec = determine_geometry_spec(
            config,
            collection,
            "test_granule",
            {Path("test_granule.nc")},
            spatial_files,
        )

        # Should have .spo rules since .spo files exist in the collection
        with pytest.raises(ValueError, match="at least 3 points"):
            spec.get_geometry_type(1)
