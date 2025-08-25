"""
Manage reader selection based on data file type.
"""

from collections.abc import Callable

from nsidc.metgen import constants
from nsidc.metgen.config import Config
from nsidc.metgen.readers import generic, netcdf_reader


def lookup(extension: str) -> Callable[[str, Config], dict]:
    """
    Determine which file reader to use for the given data file extension.
    """
    readers = {
        constants.NETCDF_SUFFIX: netcdf_reader.extract_metadata,
    }

    return readers.get(extension, generic.extract_metadata)
