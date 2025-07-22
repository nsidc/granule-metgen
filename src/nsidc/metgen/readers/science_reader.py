"""Base Science Reader Module.

This module provides the base dataclass and interface for all science data readers.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod

from nsidc.metgen.config import Config


@dataclass(frozen=True)
class ScienceMetadata:
    """Immutable science metadata extracted from data files.
    
    This dataclass contains all metadata extracted from science data files
    including temporal coverage, spatial extent, and optional attributes.
    """
    temporal: List[Dict[str, str]]  # List of temporal ranges with start/end
    geometry: List[Dict[str, float]]  # List of {"Longitude": float, "Latitude": float}
    production_date_time: Optional[str] = None  # ISO 8601 timestamp with Z suffix
    file_path: Optional[str] = None
    file_type: Optional[str] = None  # "netcdf", "csv", "snowex_csv", etc.
    additional_attributes: Optional[Dict[str, Any]] = None  # File-specific metadata


class ScienceReaderError(Exception):
    """Raised when science data reading operations fail."""
    pass


# This is the interface that all existing readers implement
def extract_metadata(
    data_file: str,
    temporal_content: list,
    spatial_content: list,
    configuration: Config,
    gsr: str,
) -> dict:
    """Extract metadata from a science data file.
    
    This is the standard interface that all science readers must implement.
    It maintains backward compatibility with the existing reader system.
    
    Args:
        data_file: Path to the science data file
        temporal_content: Temporal data from premet file (if any)
        spatial_content: Spatial data from spatial/spo file (if any)
        configuration: Configuration object
        gsr: Granule Spatial Representation (GEODETIC or CARTESIAN)
        
    Returns:
        Dictionary with 'temporal' and 'geometry' keys, optionally 'production_date_time'
        
    Raises:
        ScienceReaderError: If reading or parsing fails
    """
    # This function signature is kept for backward compatibility
    # Each reader module will implement this
    raise NotImplementedError("This is an interface definition")


class BaseScienceReader(ABC):
    """Abstract base class for science data readers.
    
    This class defines the new interface for science readers that separates
    I/O from parsing and returns immutable data structures.
    """
    
    @abstractmethod
    def read_file(self, file_path: str) -> Any:
        """Read raw data from a science file.
        
        Args:
            file_path: Path to the science data file
            
        Returns:
            Raw file data (format depends on file type)
            
        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file cannot be read
        """
        pass
    
    @abstractmethod
    def parse_metadata(
        self, 
        raw_data: Any,
        configuration: Config,
        gsr: str,
        temporal_override: Optional[List[Dict[str, str]]] = None,
        spatial_override: Optional[List[Dict[str, float]]] = None
    ) -> ScienceMetadata:
        """Parse metadata from raw file data.
        
        Args:
            raw_data: Raw data from read_file
            configuration: Configuration object
            gsr: Granule Spatial Representation
            temporal_override: Temporal data from premet file (if any)
            spatial_override: Spatial data from spatial/spo file (if any)
            
        Returns:
            Parsed science metadata
            
        Raises:
            ValueError: If parsing fails
        """
        pass
    
    def read_science_data(
        self,
        file_path: str,
        configuration: Config,
        gsr: str,
        temporal_override: Optional[List[Dict[str, str]]] = None,
        spatial_override: Optional[List[Dict[str, float]]] = None
    ) -> ScienceMetadata:
        """Read and parse science data from a file.
        
        This is the main entry point that combines reading and parsing.
        
        Args:
            file_path: Path to the science data file
            configuration: Configuration object
            gsr: Granule Spatial Representation
            temporal_override: Temporal data from premet file (if any)
            spatial_override: Spatial data from spatial/spo file (if any)
            
        Returns:
            Parsed science metadata
            
        Raises:
            ScienceReaderError: If reading or parsing fails
        """
        try:
            raw_data = self.read_file(file_path)
            return self.parse_metadata(
                raw_data, 
                configuration, 
                gsr,
                temporal_override,
                spatial_override
            )
        except Exception as e:
            raise ScienceReaderError(f"Failed to read science data from {file_path}: {e}")


# Adapter function to bridge old and new interfaces
def create_extract_metadata_adapter(reader_class: type[BaseScienceReader]):
    """Create an extract_metadata function using a BaseScienceReader class.
    
    This adapter allows new reader classes to work with the existing system.
    
    Args:
        reader_class: A BaseScienceReader subclass
        
    Returns:
        An extract_metadata function with the standard signature
    """
    def extract_metadata(
        data_file: str,
        temporal_content: list,
        spatial_content: list,
        configuration: Config,
        gsr: str,
    ) -> dict:
        reader = reader_class()
        metadata = reader.read_science_data(
            data_file,
            configuration,
            gsr,
            temporal_content or None,
            spatial_content or None
        )
        
        # Convert ScienceMetadata to the expected dictionary format
        result = {
            "temporal": metadata.temporal,
            "geometry": metadata.geometry,
        }
        if metadata.production_date_time:
            result["production_date_time"] = metadata.production_date_time
            
        return result
    
    return extract_metadata