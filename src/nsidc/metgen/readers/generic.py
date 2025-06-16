"""
Generic reader for handling data file types not supported by specific readers.
Extracts metadata from spatial/spo files when available.
"""

import os.path

from nsidc.metgen.readers import utilities


def extract_metadata(
    data_file: str,
    premet_content: dict,
    spatial_content: list,
    configuration,
    gsr: str,
) -> dict:
    """
    Extract metadata for generic data files.

    This reader is used when no specific reader exists for the data file type.
    It relies on spatial/spo files for geometry information and premet files
    for temporal information.
    """
    metadata = {
        "size_in_bytes": os.path.getsize(data_file),
        "production_date_time": configuration.date_modified,
    }

    # Get temporal information from premet if available
    if premet_content:
        temporal = utilities.temporal_from_premet(premet_content)
        if temporal:
            metadata["temporal"] = temporal
        else:
            # Default to a single point in time using production date
            metadata["temporal"] = [configuration.date_modified]
    else:
        # Default to a single point in time using production date
        metadata["temporal"] = [configuration.date_modified]

    # Use the spatial content passed in (which comes from external_spatial_values)
    if spatial_content:
        metadata["geometry"] = spatial_content
    else:
        # If no spatial content provided, return empty geometry
        # This will cause an error in UMM-G generation, which is appropriate
        metadata["geometry"] = []

    return metadata
