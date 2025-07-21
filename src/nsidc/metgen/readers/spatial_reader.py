"""Spatial File Reader.

This module provides functionality to read and parse spatial data files
(.spatial and .spo formats) used for granule geographic extent metadata.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class SpatialData:
    """Immutable spatial data extracted from spatial files.

    This dataclass contains geographic point data that defines
    the spatial extent of a granule.
    """

    points: List[dict]  # List of {"Longitude": float, "Latitude": float}
    file_path: str
    file_type: str  # "spatial" or "spo"
    is_closed_polygon: bool = False


def read_spatial_file(file_path: str) -> List[dict]:
    """Read raw longitude/latitude pairs from a spatial file.

    This function reads the file content and extracts coordinate pairs.
    Each line should contain "longitude latitude" separated by whitespace.

    Args:
        file_path: Path to the spatial file

    Returns:
        List of raw point tuples [(lon, lat), ...]

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If file content is malformed
    """
    # Implementation will be added later
    raise NotImplementedError("read_spatial_file not yet implemented")


def parse_spatial_points(
    raw_points: List[tuple], file_type: str, gsr: str
) -> List[dict]:
    """Parse raw coordinate data into formatted point dictionaries.

    This function processes raw coordinate pairs based on file type:
    - .spatial files: Points are used as-is
    - .spo files: Points are reversed and polygon is closed (if geodetic)

    Args:
        raw_points: List of (longitude, latitude) tuples
        file_type: Type of spatial file ("spatial" or "spo")
        gsr: Granule Spatial Representation ("GEODETIC" or "CARTESIAN")

    Returns:
        List of point dictionaries with Longitude/Latitude keys

    Raises:
        ValueError: If processing rules are violated
    """
    # Implementation will be added later
    raise NotImplementedError("parse_spatial_points not yet implemented")


def ensure_polygon_closure(points: List[dict]) -> List[dict]:
    """Ensure polygon is properly closed by adding first point at end if needed.

    Args:
        points: List of point dictionaries

    Returns:
        List of points with closure ensured
    """
    # Implementation will be added later
    raise NotImplementedError("ensure_polygon_closure not yet implemented")


def read_spatial_data(file_path: str, gsr: str) -> SpatialData:
    """Read and parse spatial data from a file.

    This is the main entry point that combines reading and parsing.

    Args:
        file_path: Path to the spatial file (.spatial or .spo)
        gsr: Granule Spatial Representation

    Returns:
        Parsed spatial data

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file content or format is invalid
    """
    # Determine file type from extension
    file_type = "spo" if file_path.endswith(".spo") else "spatial"

    # Read raw points
    raw_points = read_spatial_file(file_path)

    # Parse based on type and GSR
    points = parse_spatial_points(raw_points, file_type, gsr)

    # Check if polygon is closed
    is_closed = (
        len(points) > 2
        and points[0]["Longitude"] == points[-1]["Longitude"]
        and points[0]["Latitude"] == points[-1]["Latitude"]
    )

    return SpatialData(
        points=points,
        file_path=file_path,
        file_type=file_type,
        is_closed_polygon=is_closed,
    )


def extract_collection_spatial_points(collection_spatial_extent: dict) -> List[dict]:
    """Extract spatial points from collection metadata.

    This function processes spatial extent data from UMM-C collection metadata
    to create point data for granules using collection-level geometry.

    Args:
        collection_spatial_extent: Spatial extent from collection metadata

    Returns:
        List of point dictionaries defining the spatial extent

    Raises:
        ValueError: If spatial extent format is invalid
    """
    # Implementation will be added later
    raise NotImplementedError("extract_collection_spatial_points not yet implemented")
