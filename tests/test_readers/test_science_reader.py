"""Tests for Base Science Reader Module."""

import pytest
from unittest.mock import Mock

from nsidc.metgen.config import Config
from nsidc.metgen.readers.science_reader import (
    ScienceMetadata,
    ScienceReaderError,
    BaseScienceReader,
    create_extract_metadata_adapter,
)


class TestScienceMetadata:
    """Tests for the ScienceMetadata dataclass."""
    
    def test_is_frozen_dataclass(self):
        """Test that ScienceMetadata is immutable."""
        metadata = ScienceMetadata(
            temporal=[{"start": "2021-01-01T00:00:00Z", "end": "2021-01-01T23:59:59Z"}],
            geometry=[{"Longitude": -105.0, "Latitude": 40.0}]
        )
        
        # Should not be able to modify fields
        with pytest.raises(AttributeError):
            metadata.temporal = []
    
    def test_has_required_fields(self):
        """Test that ScienceMetadata can be created with required fields."""
        temporal = [{"start": "2021-01-01T00:00:00Z", "end": "2021-01-01T23:59:59Z"}]
        geometry = [{"Longitude": -105.0, "Latitude": 40.0}]
        
        metadata = ScienceMetadata(
            temporal=temporal,
            geometry=geometry
        )
        
        assert metadata.temporal == temporal
        assert metadata.geometry == geometry
    
    def test_optional_fields_default_to_none(self):
        """Test that optional fields default to None."""
        metadata = ScienceMetadata(
            temporal=[],
            geometry=[]
        )
        
        assert metadata.production_date_time is None
        assert metadata.file_path is None
        assert metadata.file_type is None
        assert metadata.additional_attributes is None
    
    def test_can_set_all_fields(self):
        """Test that all fields can be set during creation."""
        metadata = ScienceMetadata(
            temporal=[{"start": "2021-01-01T00:00:00Z", "end": "2021-01-01T23:59:59Z"}],
            geometry=[{"Longitude": -105.0, "Latitude": 40.0}],
            production_date_time="2021-01-02T12:00:00Z",
            file_path="/path/to/file.nc",
            file_type="netcdf",
            additional_attributes={"sensor": "test_sensor"}
        )
        
        assert metadata.production_date_time == "2021-01-02T12:00:00Z"
        assert metadata.file_path == "/path/to/file.nc"
        assert metadata.file_type == "netcdf"
        assert metadata.additional_attributes == {"sensor": "test_sensor"}


class TestScienceReaderError:
    """Tests for the ScienceReaderError exception."""
    
    def test_is_exception_subclass(self):
        """Test that ScienceReaderError is a proper Exception subclass."""
        assert issubclass(ScienceReaderError, Exception)
    
    def test_can_be_raised_with_message(self):
        """Test that ScienceReaderError can be raised with a message."""
        with pytest.raises(ScienceReaderError) as exc_info:
            raise ScienceReaderError("Test error message")
        assert str(exc_info.value) == "Test error message"


class TestBaseScienceReader:
    """Tests for the BaseScienceReader abstract base class."""
    
    def test_cannot_instantiate_directly(self):
        """Test that BaseScienceReader cannot be instantiated."""
        with pytest.raises(TypeError):
            BaseScienceReader()
    
    def test_read_science_data_calls_subclass_methods(self):
        """Test that read_science_data properly orchestrates reading and parsing."""
        # Create a concrete implementation for testing
        class TestReader(BaseScienceReader):
            def read_file(self, file_path):
                return {"test": "data"}
            
            def parse_metadata(self, raw_data, configuration, gsr, temporal_override, spatial_override):
                return ScienceMetadata(
                    temporal=[{"start": "2021-01-01T00:00:00Z"}],
                    geometry=[{"Longitude": -105.0, "Latitude": 40.0}],
                    file_path="/test/file.nc"
                )
        
        reader = TestReader()
        config = Mock(spec=Config)
        
        result = reader.read_science_data(
            "/test/file.nc",
            config,
            "GEODETIC"
        )
        
        assert isinstance(result, ScienceMetadata)
        assert result.temporal == [{"start": "2021-01-01T00:00:00Z"}]
        assert result.file_path == "/test/file.nc"
    
    def test_read_science_data_handles_errors(self):
        """Test that read_science_data wraps exceptions properly."""
        class FailingReader(BaseScienceReader):
            def read_file(self, file_path):
                raise IOError("Cannot read file")
            
            def parse_metadata(self, raw_data, configuration, gsr, temporal_override, spatial_override):
                pass
        
        reader = FailingReader()
        config = Mock(spec=Config)
        
        with pytest.raises(ScienceReaderError) as exc_info:
            reader.read_science_data("/test/file.nc", config, "GEODETIC")
        
        assert "Failed to read science data" in str(exc_info.value)
        assert "/test/file.nc" in str(exc_info.value)


class TestCreateExtractMetadataAdapter:
    """Tests for the adapter function."""
    
    def test_adapter_creates_valid_extract_metadata_function(self):
        """Test that the adapter creates a function with the correct signature."""
        class TestReader(BaseScienceReader):
            def read_file(self, file_path):
                return "data"
            
            def parse_metadata(self, raw_data, configuration, gsr, temporal_override, spatial_override):
                return ScienceMetadata(
                    temporal=[{"start": "2021-01-01T00:00:00Z"}],
                    geometry=[{"Longitude": -105.0, "Latitude": 40.0}],
                    production_date_time="2021-01-02T00:00:00Z"
                )
        
        extract_metadata = create_extract_metadata_adapter(TestReader)
        config = Mock(spec=Config)
        
        result = extract_metadata(
            "/test/file.nc",
            [],  # temporal_content
            [],  # spatial_content
            config,
            "GEODETIC"
        )
        
        assert isinstance(result, dict)
        assert "temporal" in result
        assert "geometry" in result
        assert "production_date_time" in result
        assert result["temporal"] == [{"start": "2021-01-01T00:00:00Z"}]
    
    def test_adapter_passes_overrides_correctly(self):
        """Test that temporal and spatial overrides are passed through."""
        class TestReader(BaseScienceReader):
            def read_file(self, file_path):
                return "data"
            
            def parse_metadata(self, raw_data, configuration, gsr, temporal_override, spatial_override):
                # Return the overrides to verify they were passed
                return ScienceMetadata(
                    temporal=temporal_override or [{"default": "temporal"}],
                    geometry=spatial_override or [{"default": "spatial"}]
                )
        
        extract_metadata = create_extract_metadata_adapter(TestReader)
        config = Mock(spec=Config)
        
        temporal_override = [{"start": "override"}]
        spatial_override = [{"Longitude": -100.0, "Latitude": 35.0}]
        
        result = extract_metadata(
            "/test/file.nc",
            temporal_override,
            spatial_override,
            config,
            "GEODETIC"
        )
        
        assert result["temporal"] == temporal_override
        assert result["geometry"] == spatial_override
    
    def test_adapter_excludes_none_production_date(self):
        """Test that production_date_time is excluded if None."""
        class TestReader(BaseScienceReader):
            def read_file(self, file_path):
                return "data"
            
            def parse_metadata(self, raw_data, configuration, gsr, temporal_override, spatial_override):
                return ScienceMetadata(
                    temporal=[],
                    geometry=[],
                    production_date_time=None
                )
        
        extract_metadata = create_extract_metadata_adapter(TestReader)
        config = Mock(spec=Config)
        
        result = extract_metadata("/test/file.nc", [], [], config, "GEODETIC")
        
        assert "production_date_time" not in result