"""
Generic reader for handling data file types not supported by specific readers.
Extracts metadata from spatial/spo files when available.
"""


def extract_metadata(
    data_file: str,
    temporal_content: list,
    spatial_content: list,
    configuration,
    _,
) -> dict:
    """
    Extract metadata for generic data files.

    This reader is used when no specific reader exists for the data file type.
    It relies on spatial/spo files or collection metadata for geometry information,
    and premet files or collection metadata for temporal information.
    """
    metadata = {}

    if temporal_content:
        metadata["temporal"] = temporal_content
    else:
        metadata["temporal"] = []

    if spatial_content:
        metadata["geometry"] = spatial_content
    else:
        # If no spatial content provided, return empty geometry
        # This will cause an error in UMM-G generation
        metadata["geometry"] = []

    return metadata
