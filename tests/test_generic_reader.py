from unittest.mock import Mock, patch

import pytest
from nsidc.metgen import metgen
from nsidc.metgen.readers import generic, registry


def test_generic_reader_extract_metadata():
    """Test that generic reader extracts metadata correctly."""
    # Mock configuration
    mock_config = Mock()
    mock_config.date_modified = "2023-12-25T00:00:00.000Z"

    # Mock premet content with temporal data
    premet_content = {
        "RangeBeginningDate": "2023-01-01",
        "RangeBeginningTime": "12:00:00",
        "RangeEndingDate": "2023-01-02",
        "RangeEndingTime": "13:00:00",
    }

    # Mock spatial content
    spatial_content = [
        {"Longitude": -180.0, "Latitude": 90.0},
        {"Longitude": 180.0, "Latitude": -90.0},
    ]

    # Create a temporary file for testing
    with patch("os.path.getsize", return_value=1024):
        metadata = generic.extract_metadata(
            "test_file.dat", premet_content, spatial_content, mock_config, "CARTESIAN"
        )

    assert metadata["size_in_bytes"] == 1024
    assert metadata["production_date_time"] == "2023-12-25T00:00:00.000Z"
    assert len(metadata["temporal"]) == 2
    assert metadata["geometry"] == spatial_content


def test_generic_reader_no_premet():
    """Test generic reader with no premet content but with spatial content."""
    mock_config = Mock()
    mock_config.date_modified = "2023-12-25T00:00:00.000Z"

    # Mock spatial content
    spatial_content = [
        {"Longitude": -180.0, "Latitude": 90.0},
        {"Longitude": 180.0, "Latitude": -90.0},
    ]

    with patch("os.path.getsize", return_value=2048):
        metadata = generic.extract_metadata(
            "test_file.dat",
            None,  # No premet
            spatial_content,
            mock_config,
            "GEODETIC",
        )

    assert metadata["size_in_bytes"] == 2048
    assert metadata["temporal"] == [
        "2023-12-25T00:00:00.000Z"
    ]  # Falls back to production date
    assert metadata["geometry"] == spatial_content


def test_generic_reader_no_spatial():
    """Test generic reader with premet content but no spatial content."""
    mock_config = Mock()
    mock_config.date_modified = "2023-12-25T00:00:00.000Z"

    # Mock premet content with temporal data
    premet_content = {
        "RangeBeginningDate": "2023-01-01",
        "RangeBeginningTime": "12:00:00",
        "RangeEndingDate": "2023-01-02",
        "RangeEndingTime": "13:00:00",
    }

    with patch("os.path.getsize", return_value=2048):
        metadata = generic.extract_metadata(
            "test_file.dat",
            premet_content,
            [],  # No spatial
            mock_config,
            "GEODETIC",
        )

    assert metadata["size_in_bytes"] == 2048
    assert len(metadata["temporal"]) == 2  # From premet
    assert metadata["geometry"] == []  # Empty geometry


def test_generic_reader_no_premet_no_spatial():
    """Test generic reader with neither premet nor spatial content."""
    mock_config = Mock()
    mock_config.date_modified = "2023-12-25T00:00:00.000Z"

    with patch("os.path.getsize", return_value=4096):
        metadata = generic.extract_metadata(
            "test_file.dat",
            None,  # No premet
            [],  # No spatial
            mock_config,
            "GEODETIC",
        )

    assert metadata["size_in_bytes"] == 4096
    assert metadata["temporal"] == [
        "2023-12-25T00:00:00.000Z"
    ]  # Falls back to production date
    assert metadata["geometry"] == []  # Empty geometry


def test_registry_fallback_to_generic():
    """Test that registry falls back to generic reader for unknown file types."""
    # Test unknown extension
    with pytest.raises(KeyError):
        registry.lookup("UNKNOWN_COLLECTION", ".xyz")

    # Test that data_reader returns generic reader for unknown types
    reader = metgen.data_reader("UNKNOWN_COLLECTION", {"file.xyz"})
    assert reader == generic.extract_metadata
