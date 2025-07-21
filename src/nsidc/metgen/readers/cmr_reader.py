"""CMR Collection Metadata Reader.

This module provides functionality to query and parse collection metadata
from NASA's Common Metadata Repository (CMR).
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class CollectionMetadata:
    """Immutable collection metadata extracted from CMR.
    
    This dataclass contains all collection-level metadata required
    for granule metadata generation.
    """
    auth_id: str
    version: int
    granule_spatial_representation: Optional[str] = None
    spatial_extent: Optional[List] = None
    temporal_extent: Optional[List] = None
    temporal_extent_error: Optional[str] = None
    # Additional fields that might be needed from UMM-C
    dataset_id: Optional[str] = None
    processing_level_id: Optional[str] = None
    short_name: Optional[str] = None


def query_cmr_collection(auth_id: str, version: int, environment: str) -> dict:
    """Query CMR for collection metadata.
    
    This function handles the network interaction with CMR to retrieve
    the UMM-C metadata for a specific collection.
    
    Args:
        auth_id: Collection authority ID (e.g., "NSIDC-0001")
        version: Collection version number
        environment: Target environment (prod, uat, sit)
        
    Returns:
        Raw UMM-C metadata as a dictionary
        
    Raises:
        CMRError: If CMR query fails or returns invalid data
    """
    # Implementation will be added later
    raise NotImplementedError("query_cmr_collection not yet implemented")


def parse_collection_metadata(ummc_data: dict) -> CollectionMetadata:
    """Parse UMM-C data into CollectionMetadata.
    
    This function extracts relevant fields from the raw UMM-C response
    and creates an immutable CollectionMetadata object.
    
    Args:
        ummc_data: Raw UMM-C metadata dictionary from CMR
        
    Returns:
        Parsed collection metadata
        
    Raises:
        ValueError: If required fields are missing or invalid
    """
    # Implementation will be added later
    raise NotImplementedError("parse_collection_metadata not yet implemented")


def read_collection_metadata(auth_id: str, version: int, environment: str) -> CollectionMetadata:
    """Read collection metadata from CMR.
    
    This is the main entry point that combines querying and parsing.
    
    Args:
        auth_id: Collection authority ID (e.g., "NSIDC-0001")
        version: Collection version number
        environment: Target environment (prod, uat, sit)
        
    Returns:
        Parsed collection metadata
        
    Raises:
        CMRError: If CMR query fails
        ValueError: If parsing fails
    """
    ummc_data = query_cmr_collection(auth_id, version, environment)
    return parse_collection_metadata(ummc_data)


class CMRError(Exception):
    """Raised when CMR operations fail."""
    pass