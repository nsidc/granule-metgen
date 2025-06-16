"""
Geometry extractor for reading geometry from different sources.

This module provides functional interfaces for extracting geometry data
from various sources (spo files, spatial files, data files, collections).
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from nsidc.metgen.constants import CARTESIAN
from nsidc.metgen.geometry_resolver import GeometryPoints, GeometrySource, GeometryType
from nsidc.metgen.readers import utilities

logger = logging.getLogger(__name__)


def extract_spo_geometry(filepath: Path) -> Tuple[GeometryPoints, int]:
    """
    Extract geometry from an SPO file.

    SPO files contain polygon data that needs to be reversed and closed.

    Args:
        filepath: Path to the SPO file

    Returns:
        Tuple of (points list, point count)
    """
    points = utilities.parse_spo(filepath)
    return points, len(points)


def extract_spatial_geometry(filepath: Path) -> Tuple[GeometryPoints, int]:
    """
    Extract geometry from a spatial file.

    Args:
        filepath: Path to the spatial file

    Returns:
        Tuple of (points list, point count)
    """
    points = utilities.points_from_spatial(filepath)
    return points, len(points)


def extract_data_file_geometry(
    granule: Any, gsr: str
) -> Tuple[Optional[GeometryPoints], Optional[GeometryType]]:
    """
    Extract geometry from data files using the appropriate reader.

    Args:
        granule: Granule object containing data file information
        gsr: Granule spatial representation

    Returns:
        Tuple of (points list, geometry type) or (None, None) if no geometry
    """
    try:
        # Use the data reader to extract geometry
        reader = granule.data_reader_fn(granule.data_files)

        # Check if reader provided spatial values
        if hasattr(reader, "spatial_values"):
            spatial_data = reader.spatial_values()
            if spatial_data:
                if gsr == CARTESIAN:
                    # Convert to bounding rectangle format
                    points = [
                        {
                            "Longitude": spatial_data[0],
                            "Latitude": spatial_data[1],
                        },  # SW
                        {
                            "Longitude": spatial_data[2],
                            "Latitude": spatial_data[3],
                        },  # NE
                    ]
                    return points, GeometryType.BOUNDING_RECTANGLE
                else:  # GEODETIC
                    # Could be point or polygon depending on data
                    if len(spatial_data) == 2:
                        points = [
                            {"Longitude": spatial_data[0], "Latitude": spatial_data[1]}
                        ]
                        return points, GeometryType.POINT
                    else:
                        # Would need more complex handling for polygons from data files
                        return None, None

    except Exception as e:
        logger.warning(f"Failed to extract geometry from data files: {e}")

    return None, None


def extract_collection_geometry(collection: Any) -> GeometryPoints:
    """
    Extract bounding rectangle from collection metadata.

    Args:
        collection: Collection object containing spatial extent

    Returns:
        List of two points representing the bounding rectangle
    """
    return utilities.points_from_collection(collection)


def extract_geometry(
    source: GeometrySource, granule: Any, expected_type: GeometryType
) -> Optional[GeometryPoints]:
    """
    Extract geometry from the specified source.

    This is the main extraction function that delegates to specific extractors
    based on the source type.

    Args:
        source: The geometry source to extract from
        granule: Granule object containing all necessary information
        expected_type: The expected geometry type (for validation)

    Returns:
        List of geometry points or None if extraction fails
    """
    try:
        if source == GeometrySource.SPO_FILE and granule.spatial_filename:
            points, _ = extract_spo_geometry(granule.spatial_filename)
            return points

        elif source == GeometrySource.SPATIAL_FILE and granule.spatial_filename:
            points, _ = extract_spatial_geometry(granule.spatial_filename)
            return points

        elif source == GeometrySource.DATA_FILE:
            points, geometry_type = extract_data_file_geometry(
                granule, granule.collection.granule_spatial_representation
            )
            return points

        elif source == GeometrySource.COLLECTION:
            return extract_collection_geometry(granule.collection)

    except Exception as e:
        logger.error(f"Failed to extract geometry from {source}: {e}")

    return None


def transform_to_bounding_rectangle(points: GeometryPoints) -> Dict[str, float]:
    """
    Transform a list of points to a bounding rectangle.

    Args:
        points: List of 2 points (SW and NE corners)

    Returns:
        Dictionary with bounding rectangle coordinates
    """
    if len(points) != 2:
        raise ValueError(
            f"Bounding rectangle requires exactly 2 points, got {len(points)}"
        )

    sw_point = points[0]
    ne_point = points[1]

    return {
        "WestBoundingCoordinate": sw_point["Longitude"],
        "SouthBoundingCoordinate": sw_point["Latitude"],
        "EastBoundingCoordinate": ne_point["Longitude"],
        "NorthBoundingCoordinate": ne_point["Latitude"],
    }


def transform_to_point(points: GeometryPoints) -> Dict[str, float]:
    """
    Transform a list of points to a single point.

    Args:
        points: List containing exactly one point

    Returns:
        Dictionary with point coordinates
    """
    if len(points) != 1:
        raise ValueError(f"Point geometry requires exactly 1 point, got {len(points)}")

    return points[0]


def transform_to_gpolygon(points: GeometryPoints) -> List[Dict[str, float]]:
    """
    Transform a list of points to a GPolygon.

    Args:
        points: List of points forming a polygon

    Returns:
        List of points representing the closed polygon
    """
    if len(points) < 4:
        raise ValueError(f"GPolygon requires at least 4 points, got {len(points)}")

    # Ensure polygon is closed
    if points[0] != points[-1]:
        points = points + [points[0]]

    return points


def transform_geometry(
    points: GeometryPoints, geometry_type: GeometryType
) -> Dict[str, Any]:
    """
    Transform geometry points to the appropriate output format.

    Args:
        points: Raw geometry points
        geometry_type: Target geometry type

    Returns:
        Formatted geometry data ready for template rendering
    """
    if geometry_type == GeometryType.BOUNDING_RECTANGLE:
        return {
            "type": "BoundingRectangle",
            "coordinates": transform_to_bounding_rectangle(points),
        }
    elif geometry_type == GeometryType.POINT:
        return {"type": "Point", "coordinates": transform_to_point(points)}
    elif geometry_type == GeometryType.GPOLYGON:
        return {"type": "GPolygon", "coordinates": transform_to_gpolygon(points)}
    else:
        raise ValueError(f"Unknown geometry type: {geometry_type}")
