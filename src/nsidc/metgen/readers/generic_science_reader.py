"""Generic Science Reader Module.

This module provides a fallback reader for files that don't have
specific readers. It relies entirely on premet and spatial files.
"""

from typing import Dict, List, Optional, Any

from nsidc.metgen.config import Config
from nsidc.metgen.readers.science_reader import (
    BaseScienceReader,
    ScienceMetadata,
    ScienceReaderError,
    extract_metadata as base_extract_metadata,
)


class GenericScienceReader(BaseScienceReader):
    """Generic reader for unsupported science data files.
    
    This reader doesn't actually read the science file - it only
    uses temporal and spatial data from auxiliary files.
    """
    
    def read_file(self, file_path: str) -> Any:
        """Verify file exists but don't read content.
        
        Args:
            file_path: Path to the science file
            
        Returns:
            The file path (no actual reading done)
            
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        # Implementation will be added later
        raise NotImplementedError("read_file not yet implemented")
    
    def parse_metadata(
        self, 
        raw_data: Any,  # Just the file path
        configuration: Config,
        gsr: str,
        temporal_override: Optional[List[Dict[str, str]]] = None,
        spatial_override: Optional[List[Dict[str, float]]] = None
    ) -> ScienceMetadata:
        """Return metadata from auxiliary files only.
        
        The generic reader requires premet and spatial files to be provided.
        
        Args:
            raw_data: The file path (unused)
            configuration: Configuration object
            gsr: Granule Spatial Representation
            temporal_override: Temporal data from premet file (required)
            spatial_override: Spatial data from spatial/spo file (required)
            
        Returns:
            Science metadata from auxiliary files
            
        Raises:
            ValueError: If temporal or spatial overrides are not provided
        """
        # Implementation will be added later
        raise NotImplementedError("parse_metadata not yet implemented")


def validate_auxiliary_data(
    temporal_content: Optional[List[Dict[str, str]]],
    spatial_content: Optional[List[Dict[str, float]]]
) -> None:
    """Validate that required auxiliary data is provided.
    
    The generic reader requires both temporal and spatial data
    from auxiliary files.
    
    Args:
        temporal_content: Temporal data from premet file
        spatial_content: Spatial data from spatial/spo file
        
    Raises:
        ValueError: If either is missing or empty
    """
    # Implementation will be added later
    raise NotImplementedError("validate_auxiliary_data not yet implemented")


# Backward compatibility function
def extract_metadata(
    data_file: str,
    temporal_content: list,
    spatial_content: list,
    configuration: Config,
    gsr: str,
) -> dict:
    """Extract metadata using auxiliary files only.
    
    This function maintains backward compatibility with the existing interface.
    The generic reader is used when no specific reader exists for a file type.
    
    Args:
        data_file: Path to the science file (verified but not read)
        temporal_content: Temporal data from premet file (required)
        spatial_content: Spatial data from spatial/spo file (required)
        configuration: Configuration object
        gsr: Granule Spatial Representation
        
    Returns:
        Dictionary with temporal and geometry from auxiliary files
        
    Raises:
        ScienceReaderError: If auxiliary files are not provided
    """
    # Implementation will be added later
    raise NotImplementedError("extract_metadata not yet implemented")