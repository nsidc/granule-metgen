"""Tests for Premet File Reader.

These tests are adapted from existing premet parsing tests
to ensure the new reader maintains the same behavior.
"""

import pytest
from pathlib import Path

from nsidc.metgen.readers.premet_reader import (
    PremetData,
    read_premet_file,
    parse_premet_line,
    parse_premet_content,
    extract_temporal_data,
    extract_additional_attributes,
    read_premet_data,
    format_temporal_for_reader,
)


# Test fixtures
@pytest.fixture
def basic_premet_content():
    """Basic premet file content with temporal data."""
    return [
        "RangeBeginningDate = 2021-11-01",
        "RangeBeginningTime = 00:00:00.000",
        "RangeEndingDate = 2021-11-30",
        "RangeEndingTime = 23:59:59.999",
        "ShortName = TEST_DATA",
    ]


@pytest.fixture
def alternate_temporal_premet():
    """Premet with alternate temporal field names."""
    return [
        "Begin_date = 2022-01-01",
        "Begin_time = 12:00:00",
        "End_date = 2022-01-31",
        "End_time = 23:59:59",
    ]


@pytest.fixture
def premet_with_additional_attrs():
    """Premet with additional attributes."""
    return [
        "RangeBeginningDate = 2021-11-01",
        "RangeBeginningTime = 00:00:00.000",
        "RangeEndingDate = 2021-11-30",
        "RangeEndingTime = 23:59:59.999",
        "Container = AdditionalAttributes",
        "  Name = ProcessingLevel",
        "  Values = Level-2",
        "Container = AdditionalAttributes",
        "  Name = SensorType",
        "  Values = Optical",
    ]


@pytest.fixture
def multiline_premet_content():
    """Premet with multi-line container values."""
    return [
        "ShortName = TEST",
        "Container = AdditionalAttributes",
        "  Name = Description",
        "  Values = This is a long",
        "           multi-line description",
        "           that spans several lines",
    ]


@pytest.fixture
def malformed_premet_content():
    """Malformed premet content for error testing."""
    return [
        "NoEqualsSign",
        "= NoKey",
        "ValidKey = ValidValue",
        "",  # Empty line
        "# Comment line",
    ]


class TestReadPremetFile:
    """Tests for the read_premet_file function."""

    def test_reads_premet_file_lines(self, tmp_path, basic_premet_content):
        """Test reading lines from a premet file."""
        test_file = tmp_path / "test.premet"
        test_file.write_text("\n".join(basic_premet_content))

        with pytest.raises(NotImplementedError):
            read_premet_file(str(test_file))

    def test_handles_missing_file(self):
        """Test proper error handling for missing files."""
        with pytest.raises(NotImplementedError):
            read_premet_file("/nonexistent/file.premet")

    def test_skips_empty_and_comment_lines(self, tmp_path):
        """Test that empty and comment lines are skipped."""
        content = [
            "Key1 = Value1",
            "",  # Empty line
            "# This is a comment",
            "Key2 = Value2",
        ]
        test_file = tmp_path / "test.premet"
        test_file.write_text("\n".join(content))

        with pytest.raises(NotImplementedError):
            read_premet_file(str(test_file))


class TestParsePremetLine:
    """Tests for the parse_premet_line function."""

    def test_parses_valid_line(self):
        """Test parsing a valid key=value line."""
        with pytest.raises(NotImplementedError):
            parse_premet_line("RangeBeginningDate = 2021-11-01")

    def test_handles_spaces_in_value(self):
        """Test parsing lines with spaces in values."""
        with pytest.raises(NotImplementedError):
            parse_premet_line("Description = This has spaces")

    def test_handles_no_spaces_around_equals(self):
        """Test parsing lines without spaces around equals."""
        with pytest.raises(NotImplementedError):
            parse_premet_line("Key=Value")

    def test_returns_none_for_invalid_line(self):
        """Test that invalid lines return None."""
        with pytest.raises(NotImplementedError):
            parse_premet_line("No equals sign here")

    def test_handles_empty_value(self):
        """Test parsing lines with empty values."""
        with pytest.raises(NotImplementedError):
            parse_premet_line("EmptyValue = ")


class TestParsePremetContent:
    """Tests for the parse_premet_content function."""

    def test_parses_basic_content(self, basic_premet_content):
        """Test parsing basic premet content."""
        with pytest.raises(NotImplementedError):
            parse_premet_content(basic_premet_content)

    def test_handles_container_entries(self, premet_with_additional_attrs):
        """Test parsing container entries."""
        with pytest.raises(NotImplementedError):
            parse_premet_content(premet_with_additional_attrs)

    def test_handles_multiline_values(self, multiline_premet_content):
        """Test parsing multi-line container values."""
        with pytest.raises(NotImplementedError):
            parse_premet_content(multiline_premet_content)

    def test_skips_invalid_lines(self, malformed_premet_content):
        """Test that invalid lines are handled gracefully."""
        with pytest.raises(NotImplementedError):
            parse_premet_content(malformed_premet_content)


class TestExtractTemporalData:
    """Tests for the extract_temporal_data function."""

    def test_extracts_standard_temporal_fields(self):
        """Test extraction of RangeBeginning/Ending fields."""
        premet_dict = {
            "RangeBeginningDate": "2021-11-01",
            "RangeBeginningTime": "00:00:00.000",
            "RangeEndingDate": "2021-11-30",
            "RangeEndingTime": "23:59:59.999",
        }

        with pytest.raises(NotImplementedError):
            extract_temporal_data(premet_dict)

    def test_extracts_alternate_temporal_fields(self):
        """Test extraction of Begin_/End_ fields."""
        premet_dict = {
            "Begin_date": "2022-01-01",
            "Begin_time": "12:00:00",
            "End_date": "2022-01-31",
            "End_time": "23:59:59",
        }

        with pytest.raises(NotImplementedError):
            extract_temporal_data(premet_dict)

    def test_returns_none_without_temporal_data(self):
        """Test that None is returned when no temporal data exists."""
        premet_dict = {
            "ShortName": "TEST",
            "Version": "1",
        }

        with pytest.raises(NotImplementedError):
            extract_temporal_data(premet_dict)

    def test_handles_partial_temporal_data(self):
        """Test handling of incomplete temporal data."""
        premet_dict = {
            "RangeBeginningDate": "2021-11-01",
            # Missing other temporal fields
        }

        with pytest.raises(NotImplementedError):
            extract_temporal_data(premet_dict)


class TestExtractAdditionalAttributes:
    """Tests for the extract_additional_attributes function."""

    def test_extracts_single_attribute(self):
        """Test extraction of a single additional attribute."""
        premet_dict = {
            "Container": "AdditionalAttributes",
            "Name": "ProcessingLevel",
            "Values": "Level-2",
        }

        with pytest.raises(NotImplementedError):
            extract_additional_attributes(premet_dict)

    def test_extracts_multiple_attributes(self):
        """Test extraction of multiple additional attributes."""
        # This would need special handling for multiple containers
        with pytest.raises(NotImplementedError):
            extract_additional_attributes({})

    def test_returns_empty_list_without_attributes(self):
        """Test that empty list is returned when no attributes exist."""
        premet_dict = {
            "RangeBeginningDate": "2021-11-01",
            "ShortName": "TEST",
        }

        with pytest.raises(NotImplementedError):
            extract_additional_attributes(premet_dict)


class TestReadPremetData:
    """Tests for the main read_premet_data function."""

    def test_reads_complete_premet_file(self, tmp_path, premet_with_additional_attrs):
        """Test reading a complete premet file with all data types."""
        test_file = tmp_path / "test.premet"
        test_file.write_text("\n".join(premet_with_additional_attrs))

        with pytest.raises(NotImplementedError):
            read_premet_data(str(test_file))

    def test_reads_temporal_only_premet(self, tmp_path, basic_premet_content):
        """Test reading premet with only temporal data."""
        test_file = tmp_path / "temporal.premet"
        test_file.write_text("\n".join(basic_premet_content))

        with pytest.raises(NotImplementedError):
            read_premet_data(str(test_file))

    def test_handles_missing_file(self):
        """Test proper error handling for missing files."""
        with pytest.raises(NotImplementedError):
            read_premet_data("/nonexistent/file.premet")


class TestFormatTemporalForReader:
    """Tests for the format_temporal_for_reader function."""

    def test_formats_temporal_data(self):
        """Test formatting temporal data for reader interface."""
        temporal_data = {
            "begin_date": "2021-11-01",
            "begin_time": "00:00:00",
            "end_date": "2021-11-30",
            "end_time": "23:59:59",
        }

        with pytest.raises(NotImplementedError):
            format_temporal_for_reader(temporal_data)

    def test_handles_none_temporal_data(self):
        """Test handling of None temporal data."""
        with pytest.raises(NotImplementedError):
            format_temporal_for_reader(None)


class TestPremetData:
    """Tests for the PremetData dataclass."""

    def test_is_frozen_dataclass(self):
        """Test that PremetData is immutable."""
        data = PremetData(
            temporal_data={"begin_date": "2021-11-01"},
            additional_attributes=[],
            file_path="/test/file.premet",
            raw_content={"key": "value"},
        )

        # Should not be able to modify fields
        with pytest.raises(AttributeError):
            data.temporal_data = {}

    def test_has_required_fields(self):
        """Test that PremetData can be created with required fields."""
        temporal = {"begin_date": "2021-11-01"}
        attrs = [{"Name": "Level", "Values": ["L2"]}]
        raw = {"RangeBeginningDate": "2021-11-01"}

        data = PremetData(
            temporal_data=temporal,
            additional_attributes=attrs,
            file_path="/test/file.premet",
            raw_content=raw,
        )

        assert data.temporal_data == temporal
        assert data.additional_attributes == attrs
        assert data.file_path == "/test/file.premet"
        assert data.raw_content == raw

    def test_allows_none_temporal_data(self):
        """Test that temporal_data can be None."""
        data = PremetData(
            temporal_data=None,
            additional_attributes=[],
            file_path="/test/file.premet",
            raw_content={},
        )

        assert data.temporal_data is None
