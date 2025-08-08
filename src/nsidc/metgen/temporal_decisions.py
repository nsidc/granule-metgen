"""
Temporal specification decision logic.

This module contains functions for determining how temporal data should be
extracted and created for granules, based on configuration, collection
metadata, and available files.
"""

import logging
from pathlib import Path
from typing import List, Optional, Set

from nsidc.metgen.config import Config
from nsidc.metgen.models import (
    CollectionMetadata,
    TemporalSource,
    TemporalSpec,
    TemporalType,
)

logger = logging.getLogger(__name__)


def determine_temporal_spec(
    configuration: Config,
    collection: CollectionMetadata,
    granule_name: str,
    data_files: Set[Path],
    premet_files: Optional[List[Path]] = None,
) -> TemporalSpec:
    """
    Determine the temporal specification based on configuration and available data.

    This function encapsulates all the business rules for deciding:
    - WHERE to get temporal data from (source)
    - WHAT type of temporal to create (type)

    Args:
        configuration: Processing configuration
        collection: Collection metadata from CMR
        granule_name: Name of the granule being processed
        data_files: Set of science data files
        premet_files: Optional list of .premet ancillary files

    Returns:
        TemporalSpec describing the temporal decisions
    """
    # Check for collection temporal override
    if configuration.collection_temporal_override:
        logger.debug(f"Using collection temporal override for {granule_name}")
        return _collection_temporal_spec(collection)

    # Check for premet file
    premet_file = _find_matching_premet_file(granule_name, premet_files)
    if premet_file:
        logger.debug(f"Found premet file {premet_file} for {granule_name}")
        return TemporalSpec(
            source=TemporalSource.PREMET_FILE,
            temporal_type=_determine_temporal_type_from_premet(),
            premet_filename=str(premet_file),
        )

    # Default: extract from granule metadata
    logger.debug(f"Will extract temporal from granule metadata for {granule_name}")

    return TemporalSpec(
        source=TemporalSource.GRANULE_METADATA,
        temporal_type=_determine_temporal_type_from_metadata(configuration),
        metadata_fields=_get_temporal_fields(configuration),
    )


def _collection_temporal_spec(collection: CollectionMetadata) -> TemporalSpec:
    """Create temporal spec for collection-based temporal."""
    # Check if collection has temporal extent error
    if collection.temporal_extent_error:
        logger.warning(
            f"Collection temporal extent has error: {collection.temporal_extent_error}"
        )
        return TemporalSpec(
            source=TemporalSource.NOT_PROVIDED,
            temporal_type=TemporalType.NONE,
            collection_override=True,
        )

    # Determine type based on collection temporal extent
    temporal_type = TemporalType.SINGLE_DATETIME
    if collection.temporal_extent and isinstance(collection.temporal_extent[0], dict):
        # If temporal extent is a dict with BeginningDateTime/EndingDateTime, it's a range
        temporal_type = TemporalType.RANGE_DATETIME

    return TemporalSpec(
        source=TemporalSource.COLLECTION,
        temporal_type=temporal_type,
        collection_override=True,
    )


def _find_matching_premet_file(
    granule_name: str, premet_files: Optional[List[Path]]
) -> Optional[Path]:
    """
    Find a premet file that matches the granule.

    Looks for files where the premet filename starts with the granule name
    followed by a period (to ensure exact match, not partial).
    """
    if not premet_files:
        return None

    for premet_file in premet_files:
        # Get just the filename without path
        filename = premet_file.name
        # Check if filename starts with granule_name followed by a period
        # This ensures "test_granule" matches "test_granule.nc.premet"
        # but not "test_granule_v2.nc.premet" or "test.nc.premet"
        if filename.startswith(f"{granule_name}."):
            return premet_file

    return None


def _determine_temporal_type_from_premet() -> TemporalType:
    """
    Determine temporal type when using premet file.

    Premet files typically contain range datetime information.
    """
    # Premet files usually contain temporal ranges
    return TemporalType.RANGE_DATETIME


def _determine_temporal_type_from_metadata(configuration: Config) -> TemporalType:
    """
    Determine temporal type based on configuration and metadata.

    This could be enhanced in the future to support configuration options
    for single vs range datetime preferences.
    """
    # Check if time coverage duration is specified (indicates range)
    if configuration.time_coverage_duration:
        return TemporalType.RANGE_DATETIME

    # Default to single datetime for granule metadata
    return TemporalType.SINGLE_DATETIME


def _get_temporal_fields(configuration: Config) -> Optional[List[str]]:
    """
    Get the metadata field names to extract for temporal data.

    Returns None if fields should be determined by the reader.
    """
    # If time_start_regex is configured, it will be used to extract temporal
    # The actual field extraction is handled by the reader using the regex
    if configuration.time_start_regex:
        return None  # Reader will use the regex

    # Default temporal fields depend on the file format and reader
    return None  # Let the reader determine the appropriate fields
