"""
Generic reader for handling data file types not supported by specific readers.
Extracts metadata from spatial/spo files when available.
"""

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
    metadata = {}

    # Get temporal information from premet if available
    if premet_content:
        metadata["temporal"] = utilities.temporal_from_premet(premet_content)
    else:
        metadata["temporal"] = []

    if spatial_content:
        metadata["geometry"] = spatial_content
    else:
        # If no spatial content provided, return empty geometry
        # This will cause an error in UMM-G generation
        metadata["geometry"] = []

    return metadata
