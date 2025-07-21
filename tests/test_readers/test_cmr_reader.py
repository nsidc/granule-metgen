"""Tests for CMR Collection Metadata Reader.

These tests are copied and adapted from existing CMR-related tests
to ensure the new reader maintains the same behavior.
"""

import pytest
from unittest.mock import patch, MagicMock

from nsidc.metgen.readers.cmr_reader import (
    CollectionMetadata,
    query_cmr_collection,
    parse_collection_metadata,
    read_collection_metadata,
    CMRError,
)
from nsidc.metgen import constants
from nsidc.metgen.config import ValidationError


# Test fixtures adapted from test_metgen.py
@pytest.fixture
def fake_ummc_response():
    """Basic UMM-C response for testing."""
    return {
        "ShortName": "BigData",
        "Version": 1,
        "TemporalExtents": ["then", "now"],
        "SpatialExtent": {"here": "there"},
    }


@pytest.fixture
def ummc_valid_temporal_extent():
    """UMM-C with valid temporal extent."""
    return {
        "TemporalExtents": [
            {
                "RangeDateTimes": [
                    {
                        "BeginningDateTime": "2021-11-01T00:00:00.000Z",
                        "EndingDateTime": "2021-11-30T00:00:00.000Z",
                    }
                ],
            },
        ]
    }


@pytest.fixture
def ummc_multi_temporal_extent():
    """UMM-C with multiple temporal extents (invalid for our use case)."""
    return {
        "TemporalExtents": [
            {
                "RangeDateTimes": [
                    {
                        "BeginningDateTime": "2021-11-01T00:00:00.000Z",
                        "EndingDateTime": "2021-11-30T00:00:00.000Z",
                    }
                ],
            },
            {
                "RangeDateTimes": [
                    {
                        "BeginningDateTime": "2022-12-01T00:00:00.000Z",
                        "EndingDateTime": "2022-12-31T00:00:00.000Z",
                    }
                ],
            },
        ]
    }


@pytest.fixture
def ummc_multi_temporal_range():
    """UMM-C with multiple temporal ranges (invalid for our use case)."""
    return {
        "TemporalExtents": [
            {
                "RangeDateTimes": [
                    {
                        "BeginningDateTime": "2021-11-01T00:00:00.000Z",
                        "EndingDateTime": "2021-11-30T00:00:00.000Z",
                    },
                    {
                        "BeginningDateTime": "2022-12-01T00:00:00.000Z",
                        "EndingDateTime": "2022-12-31T00:00:00.000Z",
                    },
                ],
            }
        ]
    }


@pytest.fixture
def ummc_with_granule_spatial_rep():
    """UMM-C with GranuleSpatialRepresentation field."""
    return {
        "ShortName": "TEST-COLLECTION",
        "Version": 1,
        "GranuleSpatialRepresentation": "CARTESIAN",
        "SpatialExtent": {
            "HorizontalSpatialDomain": {
                "Geometry": {
                    "BoundingRectangles": [
                        {
                            "WestBoundingCoordinate": -180,
                            "EastBoundingCoordinate": 180,
                            "NorthBoundingCoordinate": 90,
                            "SouthBoundingCoordinate": -90,
                        }
                    ]
                }
            }
        },
    }


@pytest.fixture
def complete_ummc_response():
    """Complete UMM-C response with all fields we care about."""
    return {
        "ShortName": "COMPLETE-TEST",
        "Version": 2,
        "DataSetId": "Complete Test Dataset",
        "ProcessingLevel": {"Id": "L2"},
        "GranuleSpatialRepresentation": "GEODETIC",
        "SpatialExtent": {
            "HorizontalSpatialDomain": {
                "Geometry": {
                    "BoundingRectangles": [
                        {
                            "WestBoundingCoordinate": -180,
                            "EastBoundingCoordinate": 180,
                            "NorthBoundingCoordinate": 90,
                            "SouthBoundingCoordinate": -90,
                        }
                    ]
                }
            }
        },
        "TemporalExtents": [
            {
                "RangeDateTimes": [
                    {
                        "BeginningDateTime": "2021-01-01T00:00:00.000Z",
                        "EndingDateTime": "2021-12-31T23:59:59.999Z",
                    }
                ],
            }
        ],
    }


class TestQueryCMRCollection:
    """Tests for the query_cmr_collection function."""

    @pytest.mark.skip(reason="Implementation not yet added")
    def test_queries_cmr_with_correct_parameters(self):
        """Test that CMR is queried with the right auth_id, version, and environment."""
        # This will test that earthaccess is called correctly
        pass

    @pytest.mark.skip(reason="Implementation not yet added")
    def test_handles_cmr_connection_error(self):
        """Test proper error handling when CMR is unavailable."""
        pass

    @pytest.mark.skip(reason="Implementation not yet added")
    def test_handles_authentication_error(self):
        """Test proper error handling for EDL authentication failures."""
        pass

    @pytest.mark.skip(reason="Implementation not yet added")
    def test_validates_cmr_response_structure(self):
        """Test that empty or malformed CMR responses are rejected."""
        # Should validate cases from test_umm_key_required
        pass

    @pytest.mark.skip(reason="Implementation not yet added")
    def test_caches_results(self):
        """Test that repeated queries use cached results."""
        pass


class TestParseCollectionMetadata:
    """Tests for the parse_collection_metadata function."""

    def test_parses_basic_fields(self, fake_ummc_response):
        """Test parsing of basic collection fields."""
        # When implemented, should extract ShortName and Version
        with pytest.raises(NotImplementedError):
            parse_collection_metadata(fake_ummc_response)

    def test_parses_granule_spatial_representation(self, ummc_with_granule_spatial_rep):
        """Test extraction of GranuleSpatialRepresentation."""
        # Should extract "CARTESIAN" from the fixture
        with pytest.raises(NotImplementedError):
            parse_collection_metadata(ummc_with_granule_spatial_rep)

    def test_parses_spatial_extent(self, ummc_with_granule_spatial_rep):
        """Test extraction of spatial extent bounding rectangles."""
        # Should extract the bounding rectangle data
        with pytest.raises(NotImplementedError):
            parse_collection_metadata(ummc_with_granule_spatial_rep)

    def test_parses_valid_temporal_extent(self, ummc_valid_temporal_extent):
        """Test extraction of valid temporal extent."""
        # Should extract begin and end times
        with pytest.raises(NotImplementedError):
            parse_collection_metadata(ummc_valid_temporal_extent)

    def test_handles_multiple_temporal_extents(self, ummc_multi_temporal_extent):
        """Test that multiple temporal extents are detected as errors."""
        # Should set temporal_extent_error field
        with pytest.raises(NotImplementedError):
            parse_collection_metadata(ummc_multi_temporal_extent)

    def test_handles_multiple_temporal_ranges(self, ummc_multi_temporal_range):
        """Test that multiple temporal ranges are detected as errors."""
        # Should set temporal_extent_error field
        with pytest.raises(NotImplementedError):
            parse_collection_metadata(ummc_multi_temporal_range)

    def test_handles_missing_optional_fields(self, fake_ummc_response):
        """Test that missing optional fields are handled gracefully."""
        # Should return None for missing fields
        with pytest.raises(NotImplementedError):
            parse_collection_metadata(fake_ummc_response)

    def test_creates_immutable_dataclass(self, complete_ummc_response):
        """Test that returned CollectionMetadata is immutable."""
        # When implemented, should verify frozen=True behavior
        with pytest.raises(NotImplementedError):
            parse_collection_metadata(complete_ummc_response)

    def test_extracts_all_relevant_fields(self, complete_ummc_response):
        """Test complete extraction of all CollectionMetadata fields."""
        # Should extract all fields from complete response
        with pytest.raises(NotImplementedError):
            parse_collection_metadata(complete_ummc_response)


class TestReadCollectionMetadata:
    """Tests for the main read_collection_metadata function."""

    @pytest.mark.skip(reason="Implementation not yet added")
    def test_combines_query_and_parse(self):
        """Test that read_collection_metadata properly combines query and parse steps."""
        pass

    @pytest.mark.skip(reason="Implementation not yet added")
    def test_propagates_cmr_errors(self):
        """Test that CMR errors are properly propagated."""
        pass

    @pytest.mark.skip(reason="Implementation not yet added")
    def test_propagates_parsing_errors(self):
        """Test that parsing errors are properly propagated."""
        pass


class TestCMRError:
    """Tests for the CMRError exception class."""

    def test_is_exception_subclass(self):
        """Test that CMRError is a proper Exception subclass."""
        assert issubclass(CMRError, Exception)

    def test_can_be_raised_with_message(self):
        """Test that CMRError can be raised with a message."""
        with pytest.raises(CMRError) as exc_info:
            raise CMRError("Test error message")
        assert str(exc_info.value) == "Test error message"


class TestCollectionMetadata:
    """Tests for the CollectionMetadata dataclass."""

    def test_is_frozen_dataclass(self):
        """Test that CollectionMetadata is immutable."""
        metadata = CollectionMetadata(auth_id="TEST-001", version=1)

        # Should not be able to modify fields
        with pytest.raises(AttributeError):
            metadata.auth_id = "MODIFIED"

    def test_has_required_fields(self):
        """Test that CollectionMetadata can be created with required fields."""
        metadata = CollectionMetadata(auth_id="TEST-001", version=1)
        assert metadata.auth_id == "TEST-001"
        assert metadata.version == 1

    def test_optional_fields_default_to_none(self):
        """Test that optional fields default to None."""
        metadata = CollectionMetadata(auth_id="TEST-001", version=1)
        assert metadata.granule_spatial_representation is None
        assert metadata.spatial_extent is None
        assert metadata.temporal_extent is None
        assert metadata.temporal_extent_error is None
        assert metadata.dataset_id is None
        assert metadata.processing_level_id is None
        assert metadata.short_name is None

    def test_can_set_all_fields(self):
        """Test that all fields can be set during creation."""
        metadata = CollectionMetadata(
            auth_id="TEST-001",
            version=2,
            granule_spatial_representation="CARTESIAN",
            spatial_extent=[{"bbox": [-180, -90, 180, 90]}],
            temporal_extent=[{"start": "2021-01-01", "end": "2021-12-31"}],
            temporal_extent_error=None,
            dataset_id="Test Dataset",
            processing_level_id="L2",
            short_name="TEST",
        )
        assert metadata.auth_id == "TEST-001"
        assert metadata.version == 2
        assert metadata.granule_spatial_representation == "CARTESIAN"
        assert metadata.spatial_extent == [{"bbox": [-180, -90, 180, 90]}]
        assert metadata.temporal_extent == [
            {"start": "2021-01-01", "end": "2021-12-31"}
        ]
        assert metadata.temporal_extent_error is None
        assert metadata.dataset_id == "Test Dataset"
        assert metadata.processing_level_id == "L2"
        assert metadata.short_name == "TEST"
