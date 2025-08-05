"""
Data models for the metgen package.

This module contains dataclasses used throughout the metgen pipeline.
"""

import dataclasses
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
