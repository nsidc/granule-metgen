"""
Unit tests for the collection metadata reader module.

These tests use mocked responses to avoid actual CMR API calls.
"""

from unittest.mock import patch

import earthaccess
import pytest

from nsidc.metgen.collection_metadata import (
    CollectionMetadataReader,
    get_collection_metadata,
)
from nsidc.metgen.models import CollectionMetadata


@pytest.fixture
def sample_ummc_response():
    """Sample UMM-C response for testing, following existing test patterns."""
    return [
        {
            "umm": {
                "ShortName": "SNEX23_SSADUCk",
                "Version": "1",
                "EntryTitle": "SnowEx23 Snow Sensor Array Duck Pass Time Series V001",
                "ProcessingLevel": {"Id": "3"},
                "CollectionDataType": "SCIENCE_QUALITY",
                "SpatialExtent": {
                    "GranuleSpatialRepresentation": "GEODETIC",
                    "HorizontalSpatialDomain": {
                        "Geometry": {
                            "BoundingRectangles": [
                                {
                                    "WestBoundingCoordinate": -119.5,
                                    "NorthBoundingCoordinate": 37.8,
                                    "EastBoundingCoordinate": -119.0,
                                    "SouthBoundingCoordinate": 37.5,
                                }
                            ]
                        }
                    },
                },
                "TemporalExtents": [
                    {
                        "RangeDateTimes": [
                            {
                                "BeginningDateTime": "2023-01-01T00:00:00.000Z",
                                "EndingDateTime": "2023-12-31T23:59:59.999Z",
                            }
                        ]
                    }
                ],
            }
        }
    ]


@pytest.fixture
def sample_ummc_single_temporal():
    """Sample UMM-C response with single temporal value."""
    return [
        {
            "umm": {
                "ShortName": "TEST_COLLECTION",
                "Version": "1",
                "EntryTitle": "Test Collection V001",
                "SpatialExtent": {
                    "GranuleSpatialRepresentation": "CARTESIAN",
                },
                "TemporalExtents": [{"SingleDateTimes": ["2023-06-15T12:00:00.000Z"]}],
            }
        }
    ]


@pytest.fixture
def ummc_multi_temporal_extent():
    """UMM-C with multiple temporal extents (should trigger error)."""
    return [
        {
            "umm": {
                "ShortName": "TEST",
                "Version": "1",
                "EntryTitle": "Test",
                "TemporalExtents": [
                    {"RangeDateTimes": [{"BeginningDateTime": "2023-01-01T00:00:00Z"}]},
                    {"RangeDateTimes": [{"BeginningDateTime": "2023-06-01T00:00:00Z"}]},
                ],
            }
        }
    ]


@pytest.fixture
def ummc_multi_temporal_range():
    """UMM-C with multiple temporal ranges in single extent (should trigger error)."""
    return [
        {
            "umm": {
                "ShortName": "TEST",
                "Version": "1",
                "EntryTitle": "Test",
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
                ],
            }
        }
    ]


@pytest.fixture
def minimal_ummc_response():
    """Minimal valid UMM-C response."""
    return [
        {
            "umm": {
                "ShortName": "MINIMAL",
                "Version": "1",
                "EntryTitle": "Minimal Collection",
            }
        }
    ]


@pytest.fixture
def collection_metadata_reader_uat():
    """Collection reader instance for UAT environment."""
    return CollectionMetadataReader(environment="uat")


@pytest.fixture
def collection_metadata_reader_prod():
    """Collection reader instance for production environment."""
    return CollectionMetadataReader(environment="prod")


class TestCollectionMetadataReader:
    """Test cases for the CMRReader class."""

    def test_initialization_uat(self, collection_metadata_reader_uat):
        """Test CMR reader initialization for UAT environment."""
        assert collection_metadata_reader_uat.environment == "uat"
        assert collection_metadata_reader_uat.provider == "NSIDC_CUAT"
        assert (
            collection_metadata_reader_uat._get_earthaccess_system() == earthaccess.UAT
        )

    def test_initialization_prod(self, collection_metadata_reader_prod):
        """Test CMR reader initialization for production environment."""
        assert collection_metadata_reader_prod.environment == "prod"
        assert collection_metadata_reader_prod.provider == "NSIDC_CPRD"
        assert (
            collection_metadata_reader_prod._get_earthaccess_system()
            == earthaccess.PROD
        )

    def test_initialization_int_environment(self):
        """Test CMR reader handles 'int' environment as UAT."""
        reader = CollectionMetadataReader(environment="int")
        assert reader.environment == "int"
        assert reader.provider == "NSIDC_CUAT"
        assert reader._get_earthaccess_system() == earthaccess.UAT

    def test_initialization_case_insensitive(self):
        """Test CMR reader handles uppercase environment names."""
        reader_uat = CollectionMetadataReader(environment="UAT")
        assert reader_uat.environment == "uat"
        assert reader_uat.provider == "NSIDC_CUAT"

        reader_prod = CollectionMetadataReader(environment="PROD")
        assert reader_prod.environment == "prod"
        assert reader_prod.provider == "NSIDC_CPRD"

    @patch("earthaccess.login")
    @patch("earthaccess.search_datasets")
    def test_get_collection_metadata_returns_correct_type(
        self,
        mock_search,
        mock_login,
        collection_metadata_reader_uat,
        sample_ummc_response,
    ):
        """Test that get_collection_metadata returns a CollectionMetadata instance."""
        mock_login.return_value = True
        mock_search.return_value = sample_ummc_response

        metadata = collection_metadata_reader_uat.get_collection_metadata(
            "SNEX23_SSADUCk", "1"
        )

        assert isinstance(metadata, CollectionMetadata)

    @patch("earthaccess.login")
    @patch("earthaccess.search_datasets")
    def test_get_collection_metadata_basic_fields(
        self,
        mock_search,
        mock_login,
        collection_metadata_reader_uat,
        sample_ummc_response,
    ):
        """Test that basic collection metadata fields are correctly parsed."""
        mock_login.return_value = True
        mock_search.return_value = sample_ummc_response

        metadata = collection_metadata_reader_uat.get_collection_metadata(
            "SNEX23_SSADUCk", "1"
        )

        assert metadata.short_name == "SNEX23_SSADUCk"
        assert metadata.version == "1"
        assert (
            metadata.entry_title
            == "SnowEx23 Snow Sensor Array Duck Pass Time Series V001"
        )

    @patch("earthaccess.login")
    @patch("earthaccess.search_datasets")
    def test_get_collection_metadata_spatial_representation(
        self,
        mock_search,
        mock_login,
        collection_metadata_reader_uat,
        sample_ummc_response,
    ):
        """Test that granule spatial representation is correctly extracted."""
        mock_login.return_value = True
        mock_search.return_value = sample_ummc_response

        metadata = collection_metadata_reader_uat.get_collection_metadata(
            "SNEX23_SSADUCk", "1"
        )

        assert metadata.granule_spatial_representation == "GEODETIC"

    @patch("earthaccess.login")
    @patch("earthaccess.search_datasets")
    def test_get_collection_metadata_spatial_extent(
        self,
        mock_search,
        mock_login,
        collection_metadata_reader_uat,
        sample_ummc_response,
    ):
        """Test that spatial extent is correctly parsed."""
        mock_login.return_value = True
        mock_search.return_value = sample_ummc_response

        metadata = collection_metadata_reader_uat.get_collection_metadata(
            "SNEX23_SSADUCk", "1"
        )

        assert metadata.spatial_extent is not None
        assert len(metadata.spatial_extent) == 1
        assert metadata.spatial_extent[0]["WestBoundingCoordinate"] == -119.5
        assert metadata.spatial_extent[0]["NorthBoundingCoordinate"] == 37.8
        assert metadata.spatial_extent[0]["EastBoundingCoordinate"] == -119.0
        assert metadata.spatial_extent[0]["SouthBoundingCoordinate"] == 37.5

    @patch("earthaccess.login")
    @patch("earthaccess.search_datasets")
    def test_get_collection_metadata_temporal_extent(
        self,
        mock_search,
        mock_login,
        collection_metadata_reader_uat,
        sample_ummc_response,
    ):
        """Test that temporal extent is correctly parsed."""
        mock_login.return_value = True
        mock_search.return_value = sample_ummc_response

        metadata = collection_metadata_reader_uat.get_collection_metadata(
            "SNEX23_SSADUCk", "1"
        )

        assert metadata.temporal_extent is not None
        assert len(metadata.temporal_extent) == 1
        assert (
            metadata.temporal_extent[0]["BeginningDateTime"]
            == "2023-01-01T00:00:00.000Z"
        )
        assert (
            metadata.temporal_extent[0]["EndingDateTime"] == "2023-12-31T23:59:59.999Z"
        )

    @patch("earthaccess.login")
    @patch("earthaccess.search_datasets")
    def test_get_collection_metadata_earthdata_login_called(
        self,
        mock_search,
        mock_login,
        collection_metadata_reader_uat,
        sample_ummc_response,
    ):
        """Test that Earthdata login is called with correct parameters."""
        mock_login.return_value = True
        mock_search.return_value = sample_ummc_response

        collection_metadata_reader_uat.get_collection_metadata("SNEX23_SSADUCk", "1")

        mock_login.assert_called_once_with(
            strategy="environment", system=earthaccess.UAT
        )

    @patch("earthaccess.login")
    @patch("earthaccess.search_datasets")
    def test_get_collection_metadata_search_called_correctly(
        self,
        mock_search,
        mock_login,
        collection_metadata_reader_uat,
        sample_ummc_response,
    ):
        """Test that earthaccess.search_datasets is called with correct parameters."""
        mock_login.return_value = True
        mock_search.return_value = sample_ummc_response

        collection_metadata_reader_uat.get_collection_metadata("SNEX23_SSADUCk", "1")

        mock_search.assert_called_once_with(
            short_name="SNEX23_SSADUCk",
            version="1",
            has_granules=None,
            provider="NSIDC_CUAT",
        )

    @patch("earthaccess.login")
    def test_get_collection_metadata_login_failure(
        self, mock_login, collection_metadata_reader_uat
    ):
        """Test handling of Earthdata login failure."""
        mock_login.return_value = False

        with pytest.raises(Exception) as exc_info:
            collection_metadata_reader_uat.get_collection_metadata("TEST", "1")

        assert "Earthdata login failed" in str(exc_info.value)

    @patch("earthaccess.login")
    @patch("earthaccess.search_datasets")
    def test_get_collection_metadata_empty_response(
        self, mock_search, mock_login, collection_metadata_reader_uat
    ):
        """Test handling of empty CMR response."""
        mock_login.return_value = True
        mock_search.return_value = []

        with pytest.raises(ValueError) as exc_info:
            collection_metadata_reader_uat.get_collection_metadata("MISSING", "1")

        assert "Empty UMM-C response" in str(exc_info.value)

    @patch("earthaccess.login")
    @patch("earthaccess.search_datasets")
    def test_get_collection_metadata_multiple_responses(
        self,
        mock_search,
        mock_login,
        collection_metadata_reader_uat,
        sample_ummc_response,
    ):
        """Test handling of multiple CMR responses."""
        mock_login.return_value = True
        # Create multiple responses
        mock_search.return_value = sample_ummc_response * 2

        with pytest.raises(ValueError) as exc_info:
            collection_metadata_reader_uat.get_collection_metadata("DUPLICATE", "1")

        assert "Multiple UMM-C records" in str(exc_info.value)

    @patch("earthaccess.login")
    @patch("earthaccess.search_datasets")
    def test_get_collection_metadata_response_without_umm_key(
        self, mock_search, mock_login, collection_metadata_reader_uat
    ):
        """Test that response without 'umm' key raises ValueError."""
        mock_login.return_value = True
        # Response without umm key should raise exception
        mock_search.return_value = [
            {"ShortName": "TEST", "Version": "1", "EntryTitle": "Test Collection"}
        ]

        with pytest.raises(ValueError) as exc_info:
            collection_metadata_reader_uat.get_collection_metadata("TEST", "1")

        assert "No UMM-C content in CMR response" in str(exc_info.value)

    @patch("earthaccess.login")
    @patch("earthaccess.search_datasets")
    def test_single_temporal_value(
        self,
        mock_search,
        mock_login,
        collection_metadata_reader_uat,
        sample_ummc_single_temporal,
    ):
        """Test parsing of single temporal value."""
        mock_login.return_value = True
        mock_search.return_value = sample_ummc_single_temporal

        metadata = collection_metadata_reader_uat.get_collection_metadata(
            "TEST_COLLECTION", "1"
        )

        assert metadata.temporal_extent == ["2023-06-15T12:00:00.000Z"]
        assert metadata.temporal_extent_error is None

    @patch("earthaccess.login")
    @patch("earthaccess.search_datasets")
    def test_multiple_temporal_extents_error(
        self,
        mock_search,
        mock_login,
        collection_metadata_reader_uat,
        ummc_multi_temporal_extent,
    ):
        """Test error handling for multiple temporal extents."""
        mock_login.return_value = True
        mock_search.return_value = ummc_multi_temporal_extent

        metadata = collection_metadata_reader_uat.get_collection_metadata("TEST", "1")

        assert metadata.temporal_extent_error is not None
        assert "must only contain one temporal extent" in metadata.temporal_extent_error

    @patch("earthaccess.login")
    @patch("earthaccess.search_datasets")
    def test_multiple_temporal_ranges_error(
        self,
        mock_search,
        mock_login,
        collection_metadata_reader_uat,
        ummc_multi_temporal_range,
    ):
        """Test error handling for multiple temporal ranges."""
        mock_login.return_value = True
        mock_search.return_value = ummc_multi_temporal_range

        metadata = collection_metadata_reader_uat.get_collection_metadata("TEST", "1")

        assert metadata.temporal_extent_error is not None
        assert "must only contain one temporal range" in metadata.temporal_extent_error

    @patch("earthaccess.login")
    @patch("earthaccess.search_datasets")
    def test_missing_optional_fields(
        self,
        mock_search,
        mock_login,
        collection_metadata_reader_uat,
        minimal_ummc_response,
    ):
        """Test handling of missing optional fields."""
        mock_login.return_value = True
        mock_search.return_value = minimal_ummc_response

        metadata = collection_metadata_reader_uat.get_collection_metadata(
            "MINIMAL", "1"
        )

        assert metadata.short_name == "MINIMAL"
        assert metadata.version == "1"
        assert metadata.entry_title == "Minimal Collection"
        assert metadata.granule_spatial_representation is None
        assert metadata.spatial_extent is None
        assert metadata.temporal_extent is None
        assert metadata.temporal_extent_error is None

    @patch("earthaccess.login")
    @patch("earthaccess.search_datasets")
    def test_version_as_integer(
        self,
        mock_search,
        mock_login,
        collection_metadata_reader_uat,
        sample_ummc_response,
    ):
        """Test that integer versions are converted to strings."""
        mock_login.return_value = True
        mock_search.return_value = sample_ummc_response

        # Call with integer version
        metadata = collection_metadata_reader_uat.get_collection_metadata("TEST", 1)

        # Should still work and store as string
        assert metadata.version == "1"

        # Verify search was called with string version
        mock_search.assert_called_once()
        call_args = mock_search.call_args[1]
        assert call_args["version"] == "1"

    @patch("earthaccess.login")
    @patch("earthaccess.search_datasets")
    def test_invalid_ummc_format(
        self, mock_search, mock_login, collection_metadata_reader_uat
    ):
        """Test handling of invalid UMM-C format."""
        mock_login.return_value = True
        # Return a string instead of dict
        mock_search.return_value = [{"umm": "invalid string format"}]

        with pytest.raises(ValueError) as exc_info:
            collection_metadata_reader_uat.get_collection_metadata("INVALID", "1")

        assert "Invalid UMM-C format" in str(exc_info.value)

    def test_extract_nested_value_missing_keys(self, collection_metadata_reader_uat):
        """Test _extract_nested_value handles missing keys gracefully."""
        test_data = {"Level1": {"Level2": {"Level3": "found_value"}}}

        # Test successful extraction
        value = collection_metadata_reader_uat._extract_nested_value(
            test_data, ["Level1", "Level2", "Level3"]
        )
        assert value == "found_value"

        # Test missing key at various levels
        assert (
            collection_metadata_reader_uat._extract_nested_value(test_data, ["Missing"])
            is None
        )
        assert (
            collection_metadata_reader_uat._extract_nested_value(
                test_data, ["Level1", "Missing"]
            )
            is None
        )
        assert (
            collection_metadata_reader_uat._extract_nested_value(
                test_data, ["Level1", "Level2", "Missing"]
            )
            is None
        )

        # Test with empty dict
        assert (
            collection_metadata_reader_uat._extract_nested_value({}, ["Any", "Key"])
            is None
        )

        # Test with None input
        assert (
            collection_metadata_reader_uat._extract_nested_value(None, ["Any"]) is None
        )


class TestConvenienceFunction:
    """Test the convenience function for getting collection metadata."""

    @patch("earthaccess.login")
    @patch("earthaccess.search_datasets")
    def test_get_collection_uat(self, mock_search, mock_login, minimal_ummc_response):
        """Test the convenience function with UAT environment."""
        mock_login.return_value = True
        mock_search.return_value = minimal_ummc_response

        metadata = get_collection_metadata("uat", "TEST", "1")

        assert isinstance(metadata, CollectionMetadata)
        assert metadata.short_name == "TEST"
        assert metadata.version == "1"

        # Should use UAT environment
        mock_login.assert_called_once_with(
            strategy="environment", system=earthaccess.UAT
        )
        mock_search.assert_called_once()
        call_args = mock_search.call_args[1]
        assert call_args["provider"] == "NSIDC_CUAT"

    @patch("earthaccess.login")
    @patch("earthaccess.search_datasets")
    def test_get_collection_prod(self, mock_search, mock_login, minimal_ummc_response):
        """Test the convenience function with production environment."""
        mock_login.return_value = True
        mock_search.return_value = minimal_ummc_response

        metadata = get_collection_metadata("prod", "TEST", "2")

        assert isinstance(metadata, CollectionMetadata)
        assert metadata.short_name == "TEST"
        assert metadata.version == "2"

        # Should use production environment
        mock_login.assert_called_once_with(
            strategy="environment", system=earthaccess.PROD
        )
        mock_search.assert_called_once()
        call_args = mock_search.call_args[1]
        assert call_args["provider"] == "NSIDC_CPRD"
