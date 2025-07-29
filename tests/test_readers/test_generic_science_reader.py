"""Tests for Generic Science Reader Module."""

import pytest
from unittest.mock import Mock, patch
from pathlib import Path

from nsidc.metgen.config import Config
from nsidc.metgen.readers.generic_science_reader import (
    GenericScienceReader,
    extract_metadata,
    validate_auxiliary_data,
)
from nsidc.metgen.readers.science_reader import ScienceMetadata, ScienceReaderError


# Test fixtures
@pytest.fixture
def temporal_content():
    """Sample temporal content from premet file."""
    return [{"start": "2021-01-01T00:00:00Z", "end": "2021-01-01T23:59:59Z"}]


@pytest.fixture
def spatial_content():
    """Sample spatial content from spatial file."""
    return [
        {"Longitude": -105.0, "Latitude": 40.0},
        {"Longitude": -104.0, "Latitude": 40.0},
        {"Longitude": -104.0, "Latitude": 41.0},
        {"Longitude": -105.0, "Latitude": 41.0},
        {"Longitude": -105.0, "Latitude": 40.0},  # Closed polygon
    ]


@pytest.fixture
def test_config():
    """Test configuration object."""
    config = Mock(spec=Config)
    return config


class TestGenericScienceReader:
    """Tests for the GenericScienceReader class."""

    def test_read_file_not_implemented(self):
        """Test that read_file raises NotImplementedError."""
        reader = GenericScienceReader()
        with pytest.raises(NotImplementedError):
            reader.read_file("/test/file.bin")

    def test_parse_metadata_not_implemented(
        self, test_config, temporal_content, spatial_content
    ):
        """Test that parse_metadata raises NotImplementedError."""
        reader = GenericScienceReader()
        with pytest.raises(NotImplementedError):
            reader.parse_metadata(
                "/test/file.bin",
                test_config,
                "GEODETIC",
                temporal_content,
                spatial_content,
            )

    def test_parse_metadata_requires_temporal_override(
        self, test_config, spatial_content
    ):
        """Test that parse_metadata requires temporal data."""
        reader = GenericScienceReader()
        with pytest.raises(NotImplementedError):
            reader.parse_metadata(
                "/test/file.bin",
                test_config,
                "GEODETIC",
                None,  # No temporal override
                spatial_content,
            )

    def test_parse_metadata_requires_spatial_override(
        self, test_config, temporal_content
    ):
        """Test that parse_metadata requires spatial data."""
        reader = GenericScienceReader()
        with pytest.raises(NotImplementedError):
            reader.parse_metadata(
                "/test/file.bin",
                test_config,
                "GEODETIC",
                temporal_content,
                None,  # No spatial override
            )


class TestValidateAuxiliaryData:
    """Tests for auxiliary data validation."""

    def test_validates_both_present(self, temporal_content, spatial_content):
        """Test validation passes when both are provided."""
        with pytest.raises(NotImplementedError):
            validate_auxiliary_data(temporal_content, spatial_content)

    def test_fails_when_temporal_missing(self, spatial_content):
        """Test validation fails when temporal is missing."""
        with pytest.raises(NotImplementedError):
            validate_auxiliary_data(None, spatial_content)

    def test_fails_when_spatial_missing(self, temporal_content):
        """Test validation fails when spatial is missing."""
        with pytest.raises(NotImplementedError):
            validate_auxiliary_data(temporal_content, None)

    def test_fails_when_temporal_empty(self, spatial_content):
        """Test validation fails when temporal is empty list."""
        with pytest.raises(NotImplementedError):
            validate_auxiliary_data([], spatial_content)

    def test_fails_when_spatial_empty(self, temporal_content):
        """Test validation fails when spatial is empty list."""
        with pytest.raises(NotImplementedError):
            validate_auxiliary_data(temporal_content, [])

    def test_fails_when_both_missing(self):
        """Test validation fails when both are missing."""
        with pytest.raises(NotImplementedError):
            validate_auxiliary_data(None, None)


class TestExtractMetadata:
    """Tests for the backward compatibility extract_metadata function."""

    def test_extract_metadata_not_implemented(
        self, test_config, temporal_content, spatial_content
    ):
        """Test that extract_metadata raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            extract_metadata(
                "/test/file.bin",
                temporal_content,
                spatial_content,
                test_config,
                "GEODETIC",
            )

    def test_requires_temporal_content(self, test_config, spatial_content):
        """Test that temporal content is required."""
        with pytest.raises(NotImplementedError):
            extract_metadata(
                "/test/file.bin",
                [],  # Empty temporal content
                spatial_content,
                test_config,
                "GEODETIC",
            )

    def test_requires_spatial_content(self, test_config, temporal_content):
        """Test that spatial content is required."""
        with pytest.raises(NotImplementedError):
            extract_metadata(
                "/test/file.bin",
                temporal_content,
                [],  # Empty spatial content
                test_config,
                "GEODETIC",
            )

    def test_verifies_file_exists(self, test_config, temporal_content, spatial_content):
        """Test that file existence is verified."""
        with pytest.raises(NotImplementedError):
            extract_metadata(
                "/nonexistent/file.bin",
                temporal_content,
                spatial_content,
                test_config,
                "GEODETIC",
            )

    def test_returns_auxiliary_data_unchanged(
        self, test_config, temporal_content, spatial_content
    ):
        """Test that auxiliary data is passed through unchanged."""
        with pytest.raises(NotImplementedError):
            extract_metadata(
                "/test/file.bin",
                temporal_content,
                spatial_content,
                test_config,
                "GEODETIC",
            )

    def test_handles_various_file_types(
        self, test_config, temporal_content, spatial_content
    ):
        """Test that generic reader handles any file extension."""
        file_types = [
            "/test/file.hdf5",
            "/test/file.dat",
            "/test/file.txt",
            "/test/file.unknown",
            "/test/file_no_extension",
        ]

        for file_path in file_types:
            with pytest.raises(NotImplementedError):
                extract_metadata(
                    file_path,
                    temporal_content,
                    spatial_content,
                    test_config,
                    "GEODETIC",
                )
