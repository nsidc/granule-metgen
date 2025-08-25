from unittest.mock import Mock

import pytest

from nsidc.metgen import metgen
from nsidc.metgen.readers import generic, registry


def test_generic_reader_extract_metadata():
    """Test that generic reader extracts metadata correctly."""
    # Mock configuration
    mock_config = Mock()

    # Mock premet content with temporal data
    premet_content = [
        {
            "BeginningDatetime": "2023-01-01T12:00:00",
            "EndingDateTime": "2023-01-02T13:00:00",
        }
    ]

    # Mock spatial content
    spatial_content = [
        {"Longitude": -180.0, "Latitude": 90.0},
        {"Longitude": 180.0, "Latitude": -90.0},
    ]

    # Create a temporary file for testing
    metadata = generic.extract_metadata(
        "test_file.dat", premet_content, spatial_content, mock_config, "CARTESIAN"
    )

    assert metadata["temporal"] == premet_content
    assert metadata["geometry"] == spatial_content


def test_generic_reader_no_premet():
    """Test generic reader with no premet content but with spatial content."""
    mock_config = Mock()

    # Mock spatial content
    spatial_content = [
        {"Longitude": -180.0, "Latitude": 90.0},
        {"Longitude": 180.0, "Latitude": -90.0},
    ]

    metadata = generic.extract_metadata(
        "test_file.dat",
        None,  # No premet
        spatial_content,
        mock_config,
        "GEODETIC",
    )

    assert metadata["temporal"] == []
    assert metadata["geometry"] == spatial_content


def test_generic_reader_no_spatial():
    """Test generic reader with premet content but no spatial content."""
    mock_config = Mock()

    # Mock premet content with temporal data
    premet_content = [
        {
            "BeginningDatetime": "2023-01-01T12:00:00",
            "EndingDateTime": "2023-01-02T13:00:00",
        }
    ]

    metadata = generic.extract_metadata(
        "test_file.dat",
        premet_content,
        [],  # No spatial
        mock_config,
        "GEODETIC",
    )

    assert metadata["temporal"] == premet_content
    assert metadata["geometry"] == []  # Empty geometry


def test_generic_reader_no_premet_no_spatial():
    """Test generic reader with neither premet nor spatial content."""
    mock_config = Mock()

    metadata = generic.extract_metadata(
        "test_file.dat",
        None,  # No premet
        [],  # No spatial
        mock_config,
        "GEODETIC",
    )

    assert metadata["temporal"] == []  # Empty temporal
    assert metadata["geometry"] == []  # Empty geometry


def test_registry_fallback_to_generic():
    """Test that registry falls back to generic reader for unknown file types."""
    # Test unknown extension
    with pytest.raises(KeyError):
        registry.lookup("UNKNOWN_COLLECTION", ".xyz")

    # Test that data_reader returns generic reader for unknown types
    reader = metgen.data_reader("UNKNOWN_COLLECTION", "file.xyz")
    assert reader == generic.extract_metadata
