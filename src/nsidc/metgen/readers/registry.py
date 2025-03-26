from collections.abc import Callable

from nsidc.metgen import netcdf_reader
from nsidc.metgen.config import Config
from nsidc.metgen.readers import csv, snowex_csv


def lookup(collection: str, extension: str) -> Callable[[str, Config], dict]:
    """
    Determine which file reader to use for the given collection and data
    file extension. This currently is limited to handling one data file
    type, and one reader. In a future issue, we may handle granules with
    multiple data file types per granule. In that future work this needs
    to be refactored to handle this case.
    """
    special_readers = {"snex23": snowex_csv.extract_metadata}

    for key, function in special_readers.items():
        if collection.lower().startswith(key):
            return function

    readers = {
        ".nc": netcdf_reader.extract_metadata,
        ".csv": csv.extract_metadata,
    }

    return readers[extension]
