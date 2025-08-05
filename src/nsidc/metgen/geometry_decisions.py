"""
Geometry specification decision logic.

This module contains functions for determining how geometry should be
extracted and created for granules, based on configuration, collection
metadata, and available files.
"""

import logging
from pathlib import Path
from typing import List, Optional, Set

from nsidc.metgen.config import Config
from nsidc.metgen.models import Collection, GeometrySource, GeometrySpec, GeometryType

logger = logging.getLogger(__name__)


def determine_geometry_spec(
    configuration: Config,
    collection: Collection,
    granule_name: str,
    data_files: Set[Path],
    spatial_files: Optional[List[Path]] = None,
) -> GeometrySpec:
    """
    Determine the geometry specification based on configuration and available data.

    This function encapsulates all the business rules for deciding:
    - WHERE to get geometry data from (source)
    - WHAT type of geometry to create (type)
    - HOW it should be represented (coordinate system)

    Args:
        configuration: Processing configuration
        collection: Collection metadata from CMR
        granule_name: Name of the granule being processed
        data_files: Set of science data files
        spatial_files: Optional list of .spatial ancillary files

    Returns:
        GeometrySpec describing the geometry decisions
    """
    # Check if spatial representation is available
    if not collection.granule_spatial_representation:
        logger.debug(f"No granule spatial representation for {granule_name}")
        return GeometrySpec(
            source=GeometrySource.NOT_PROVIDED,
            geometry_type=GeometryType.NONE,
        )

    # Check for collection geometry override
    if configuration.collection_geometry_override:
        logger.debug(f"Using collection geometry override for {granule_name}")
        return _collection_geometry_spec(collection)

    # Check for spatial file
    spatial_file = _find_matching_spatial_file(granule_name, spatial_files)
    if spatial_file:
        logger.debug(f"Found spatial file {spatial_file} for {granule_name}")
        return GeometrySpec(
            source=GeometrySource.SPATIAL_FILE,
            geometry_type=GeometryType.POLYGON,  # Spatial files contain polygons
            representation=collection.granule_spatial_representation,
            spatial_filename=str(spatial_file),
        )

    # Default: extract from granule metadata
    logger.debug(f"Will extract geometry from granule metadata for {granule_name}")
    geometry_type = _determine_geometry_type_from_config(configuration)

    return GeometrySpec(
        source=GeometrySource.GRANULE_METADATA,
        geometry_type=geometry_type,
        representation=collection.granule_spatial_representation,
        metadata_fields=_get_geometry_fields(configuration, geometry_type),
    )


def _collection_geometry_spec(collection: Collection) -> GeometrySpec:
    """Create geometry spec for collection-based geometry."""
    # Collection geometry is always a bounding box in CARTESIAN representation
    return GeometrySpec(
        source=GeometrySource.COLLECTION,
        geometry_type=GeometryType.BOUNDING_BOX,
        representation="CARTESIAN",  # Collection override requires CARTESIAN
    )


def _find_matching_spatial_file(
    granule_name: str, spatial_files: Optional[List[Path]]
) -> Optional[Path]:
    """
    Find a spatial file that matches the granule.

    Looks for files where the spatial filename starts with the granule name
    followed by a period (to ensure exact match, not partial).
    """
    if not spatial_files:
        return None

    for spatial_file in spatial_files:
        # Get just the filename without path
        filename = spatial_file.name
        # Check if filename starts with granule_name followed by a period
        # This ensures "test_granule" matches "test_granule.nc.spatial"
        # but not "test_granule_v2.nc.spatial" or "test.nc.spatial"
        if filename.startswith(f"{granule_name}."):
            return spatial_file

    return None


def _determine_geometry_type_from_config(configuration: Config) -> GeometryType:
    """
    Determine geometry type based on configuration settings.

    Currently, MetGenC doesn't have a write_points configuration option,
    so we determine based on other factors. In the future, this could be
    enhanced to support point-only output.
    """
    # Default is polygon for geodetic, bounding box for cartesian
    # This logic may be enhanced in the future with explicit configuration
    return GeometryType.POLYGON


def _get_geometry_fields(
    configuration: Config, geometry_type: GeometryType
) -> Optional[List[str]]:
    """
    Get the metadata field names to extract based on geometry type.

    Returns None if fields should be determined by the reader.
    """
    if geometry_type == GeometryType.POINT:
        # For points, we need lat/lon fields
        # The actual field names depend on the file format and reader
        return None  # Let the reader determine the appropriate fields
    elif geometry_type == GeometryType.POLYGON:
        # For polygons, we need coordinate arrays
        # The actual field names depend on the file format and reader
        return None  # Let the reader determine the appropriate fields
    else:
        return None
