"""SnowEx CSV Science Reader Module.

This module provides functionality to read and parse metadata from SnowEx CSV files.
SnowEx files have a specific format with metadata in header comments.
"""

from typing import Dict, List, Optional, Any, Tuple

from nsidc.metgen.config import Config
from nsidc.metgen.readers.science_reader import (
    BaseScienceReader,
    ScienceMetadata,
    extract_metadata as base_extract_metadata,
)


class SnowExCSVScienceReader(BaseScienceReader):
    """Reader for SnowEx mission CSV data files."""

    def read_file(self, file_path: str) -> Any:
        """Read SnowEx CSV file including header metadata.

        SnowEx files contain metadata in comment lines at the top.

        Args:
            file_path: Path to the SnowEx CSV file

        Returns:
            Tuple of (metadata_dict, data_rows)

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file cannot be read
        """
        # Implementation will be added later
        raise NotImplementedError("read_file not yet implemented")

    def parse_metadata(
        self,
        raw_data: Any,  # Tuple[Dict, List]
        configuration: Config,
        gsr: str,
        temporal_override: Optional[List[Dict[str, str]]] = None,
        spatial_override: Optional[List[Dict[str, float]]] = None,
    ) -> ScienceMetadata:
        """Parse metadata from SnowEx CSV data.

        Extracts:
        - Temporal data from header metadata
        - Spatial data from UTM coordinates converted to lat/lon

        Args:
            raw_data: Tuple of (metadata_dict, data_rows)
            configuration: Configuration object
            gsr: Granule Spatial Representation
            temporal_override: Temporal data from premet file (if any)
            spatial_override: Spatial data from spatial/spo file (if any)

        Returns:
            Parsed science metadata

        Raises:
            ValueError: If required metadata is missing
        """
        # Implementation will be added later
        raise NotImplementedError("parse_metadata not yet implemented")


def parse_snowex_header(lines: List[str]) -> Dict[str, str]:
    """Parse metadata from SnowEx CSV header comments.

    SnowEx files have key-value pairs in comment lines like:
    # key: value

    Args:
        lines: Header lines from the CSV file

    Returns:
        Dictionary of metadata key-value pairs
    """
    # Implementation will be added later
    raise NotImplementedError("parse_snowex_header not yet implemented")


def extract_temporal_from_snowex(metadata: Dict[str, str]) -> List[Dict[str, str]]:
    """Extract temporal information from SnowEx metadata.

    Looks for date fields in the metadata dictionary.

    Args:
        metadata: Parsed header metadata

    Returns:
        List containing single temporal range

    Raises:
        ValueError: If no date information found
    """
    # Implementation will be added later
    raise NotImplementedError("extract_temporal_from_snowex not yet implemented")


def extract_spatial_from_snowex(metadata: Dict[str, str]) -> List[Dict[str, float]]:
    """Extract spatial information from SnowEx metadata.

    Converts UTM coordinates to lat/lon for single point coverage.

    Args:
        metadata: Parsed header metadata

    Returns:
        List containing single point

    Raises:
        ValueError: If coordinate information is missing
    """
    # Implementation will be added later
    raise NotImplementedError("extract_spatial_from_snowex not yet implemented")


def convert_utm_to_latlon(
    easting: float, northing: float, zone: int, hemisphere: str = "N"
) -> Tuple[float, float]:
    """Convert UTM coordinates to latitude/longitude.

    Args:
        easting: UTM easting coordinate
        northing: UTM northing coordinate
        zone: UTM zone number
        hemisphere: 'N' for northern, 'S' for southern

    Returns:
        Tuple of (latitude, longitude)
    """
    # Implementation will be added later
    raise NotImplementedError("convert_utm_to_latlon not yet implemented")


# Backward compatibility function
def extract_metadata(
    data_file: str,
    temporal_content: list,
    spatial_content: list,
    configuration: Config,
    gsr: str,
) -> dict:
    """Extract metadata from a SnowEx CSV file.

    This function maintains backward compatibility with the existing interface.

    Args:
        data_file: Path to the SnowEx CSV file
        temporal_content: Temporal data from premet file (if any)
        spatial_content: Spatial data from spatial/spo file (if any)
        configuration: Configuration object
        gsr: Granule Spatial Representation

    Returns:
        Dictionary with temporal and geometry
    """
    # Implementation will be added later
    raise NotImplementedError("extract_metadata not yet implemented")
