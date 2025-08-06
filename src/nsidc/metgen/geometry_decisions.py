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
from nsidc.metgen.models import (
    CollectionMetadata,
    GeometrySource,
    GeometrySpec,
    GeometryType,
)

logger = logging.getLogger(__name__)


def determine_geometry_spec(
    configuration: Config,
    collection: CollectionMetadata,
    granule_name: str,
    data_files: Set[Path],
    spatial_files: Optional[List[Path]] = None,
) -> GeometrySpec:
    """
    Determine the geometry specification based on configuration and available data.

    This function encapsulates all the business rules for deciding:
    - WHERE to get geometry data from (source)
    - Rules for WHAT type of geometry to create based on point count
    - HOW it should be represented (coordinate system)

    Args:
        configuration: Processing configuration
        collection: Collection metadata from CMR
        granule_name: Name of the granule being processed
        data_files: Set of science data files
        spatial_files: Optional list of .spatial and .spo ancillary files

    Returns:
        GeometrySpec describing the geometry decisions
    """
    # Check if spatial representation is available
    if not collection.granule_spatial_representation:
        logger.debug(f"No granule spatial representation for {granule_name}")
        return GeometrySpec(
            source=GeometrySource.NOT_PROVIDED,
            get_geometry_type=lambda _: GeometryType.NONE,
            representation="NONE",
        )

    # Check for collection geometry override
    if configuration.collection_geometry_override:
        logger.debug(f"Using collection geometry override for {granule_name}")
        return _collection_geometry_spec(collection)

    # Check for .spo or .spatial files
    if spatial_files:
        # Check if any .spo files exist (not granule-specific)
        has_spo_files = any(f.suffix == ".spo" for f in spatial_files)
        if has_spo_files:
            logger.debug(f"Processing with .spo file rules for {granule_name}")
            return _spo_geometry_spec(collection)

        # Check if any .spatial files exist
        has_spatial_files = any(f.suffix == ".spatial" for f in spatial_files)
        if has_spatial_files:
            logger.debug(f"Processing with .spatial file rules for {granule_name}")
            return _spatial_geometry_spec(collection)

    # Default: extract from granule metadata
    logger.debug(f"Will extract geometry from granule metadata for {granule_name}")
    return _granule_metadata_geometry_spec(collection)


def _collection_geometry_spec(collection: CollectionMetadata) -> GeometrySpec:
    """Create geometry spec for collection-based geometry."""
    # Collection geometry is always a bounding box in CARTESIAN representation
    return GeometrySpec(
        source=GeometrySource.COLLECTION,
        get_geometry_type=lambda _: GeometryType.BOUNDING_BOX,
        representation="CARTESIAN",  # Collection override requires CARTESIAN
    )


def _spo_geometry_spec(collection: CollectionMetadata) -> GeometrySpec:
    """
    Create geometry spec for .spo file based geometry.

    According to README:
    - .spo files inherently define GPoly vertices
    - GPolys must be geodetic, not cartesian
    - Requires at least 3 points to define a polygon
    """
    # Validate that collection uses geodetic representation
    if collection.granule_spatial_representation != "GEODETIC":
        logger.error(
            f"Invalid: .spo files require GEODETIC representation, "
            f"but collection has {collection.granule_spatial_representation}"
        )
        # Return error state
        return GeometrySpec(
            source=GeometrySource.NOT_PROVIDED,
            get_geometry_type=lambda _: GeometryType.NONE,
            representation=collection.granule_spatial_representation,
        )

    def spo_geometry_type(point_count: int) -> GeometryType:
        """Determine geometry type for .spo files based on point count."""
        if point_count <= 2:
            raise ValueError(
                f"Invalid .spo file: has {point_count} points, "
                f"but at least 3 points are required to define a polygon"
            )
        return GeometryType.POLYGON

    return GeometrySpec(
        source=GeometrySource.SPATIAL_FILE,
        get_geometry_type=spo_geometry_type,
        representation="GEODETIC",
    )


def _spatial_geometry_spec(collection: CollectionMetadata) -> GeometrySpec:
    """
    Create geometry spec for .spatial file based geometry.

    According to README, the geometry type depends on:
    - Number of points in the file
    - Coordinate system (geodetic vs cartesian)
    """
    representation = collection.granule_spatial_representation

    if representation == "CARTESIAN":

        def cartesian_geometry_type(point_count: int) -> GeometryType:
            """Determine geometry type for cartesian .spatial files."""
            if point_count == 1:
                raise ValueError(
                    "Invalid .spatial file: single point with CARTESIAN representation. "
                    "Points must use GEODETIC representation."
                )
            elif point_count == 2:
                return GeometryType.BOUNDING_BOX
            else:  # point_count > 2
                raise ValueError(
                    f"Invalid .spatial file: has {point_count} points with CARTESIAN representation. "
                    "Only 2 points (bounding box) are valid for CARTESIAN."
                )

        return GeometrySpec(
            source=GeometrySource.SPATIAL_FILE,
            get_geometry_type=cartesian_geometry_type,
            representation="CARTESIAN",
        )
    else:  # GEODETIC

        def geodetic_geometry_type(point_count: int) -> GeometryType:
            """Determine geometry type for geodetic .spatial files."""
            if point_count == 0:
                raise ValueError("Invalid .spatial file: no points found")
            elif point_count == 1:
                return GeometryType.POINT
            else:  # point_count >= 2
                return GeometryType.POLYGON

        return GeometrySpec(
            source=GeometrySource.SPATIAL_FILE,
            get_geometry_type=geodetic_geometry_type,
            representation="GEODETIC",
        )


def _granule_metadata_geometry_spec(collection: CollectionMetadata) -> GeometrySpec:
    """
    Create geometry spec for granule metadata based geometry.

    For science files (NetCDF), the geometry type is determined by
    the coordinate system.
    """
    representation = collection.granule_spatial_representation

    if representation == "CARTESIAN":
        # Science files with cartesian create bounding rectangles
        return GeometrySpec(
            source=GeometrySource.GRANULE_METADATA,
            get_geometry_type=lambda _: GeometryType.BOUNDING_BOX,
            representation="CARTESIAN",
        )
    else:  # GEODETIC
        # Science files with geodetic create polygons from grid perimeter
        return GeometrySpec(
            source=GeometrySource.GRANULE_METADATA,
            get_geometry_type=lambda _: GeometryType.POLYGON,
            representation="GEODETIC",
        )
