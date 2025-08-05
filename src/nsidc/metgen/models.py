"""
Data models for the metgen package.

This module contains dataclasses used throughout the metgen pipeline.
"""

import dataclasses
from enum import Enum
from typing import Optional


@dataclasses.dataclass
class Collection:
    """
    Collection metadata relevant to generating UMM-G content.

    This dataclass contains all the metadata fields needed for granule
    metadata generation, retrieved from CMR or other sources.
    """

    # Collection identifiers
    short_name: str  # Previously called auth_id
    version: str  # Changed from int to str for consistency with CMR
    entry_title: str

    # Spatial information
    granule_spatial_representation: Optional[str] = None
    spatial_extent: Optional[list] = None

    # Temporal information
    temporal_extent: Optional[list] = None
    temporal_extent_error: Optional[str] = None

    # Additional metadata
    processing_level_id: Optional[str] = None
    collection_data_type: Optional[str] = None

    # Raw UMM-C record for future extensibility
    raw_ummc: Optional[dict] = None


class GeometrySource(Enum):
    """Specifies where geometry data should be extracted from."""

    GRANULE_METADATA = "granule_metadata"  # From science file metadata
    SPATIAL_FILE = "spatial_file"  # From .spatial ancillary file
    COLLECTION = "collection"  # From collection metadata
    NOT_PROVIDED = "not_provided"  # No geometry to be created


class GeometryType(Enum):
    """Specifies what type of geometry to create in UMM-G."""

    POINT = "point"  # Single point
    POLYGON = "polygon"  # GPolygon
    BOUNDING_BOX = "bounding_box"  # Bounding rectangle
    NONE = "none"  # No geometry


@dataclasses.dataclass
class GeometrySpec:
    """
    Specification for geometry extraction and creation.

    This captures the decisions about WHERE to get geometry data from
    and WHAT type of geometry to create, but not HOW to do it.
    """

    # Where to get the geometry data
    source: GeometrySource

    # What type of geometry to create
    geometry_type: GeometryType

    # Coordinate system (if applicable)
    representation: Optional[str] = None  # "GEODETIC" or "CARTESIAN"

    # Additional context needed for execution
    spatial_filename: Optional[str] = None  # If source is SPATIAL_FILE
    metadata_fields: Optional[list] = None  # Which fields to extract from


class TemporalSource(Enum):
    """Specifies where temporal data should be extracted from."""

    GRANULE_METADATA = "granule_metadata"  # From science file metadata
    PREMET_FILE = "premet_file"  # From .premet ancillary file
    COLLECTION = "collection"  # From collection metadata
    NOT_PROVIDED = "not_provided"  # No temporal to be created


class TemporalType(Enum):
    """Specifies what type of temporal to create in UMM-G."""

    SINGLE_DATETIME = "single_datetime"  # Single point in time
    RANGE_DATETIME = "range_datetime"  # Time range with begin/end
    NONE = "none"  # No temporal


@dataclasses.dataclass
class TemporalSpec:
    """
    Specification for temporal extraction and creation.

    This captures the decisions about WHERE to get temporal data from
    and WHAT type of temporal to create, but not HOW to do it.
    """

    # Where to get the temporal data
    source: TemporalSource

    # What type of temporal to create
    temporal_type: TemporalType

    # Additional context needed for execution
    premet_filename: Optional[str] = None  # If source is PREMET_FILE
    metadata_fields: Optional[list] = None  # Which fields to extract from
    collection_override: Optional[bool] = False  # Using collection temporal override
