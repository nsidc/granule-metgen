from collections.abc import Callable

from nsidc.metgen import netcdf_reader
from nsidc.metgen.config import Config
from nsidc.metgen.readers import csv, snowex_csv


def lookup(auth_id: str, extension: str) -> Callable[[str, Config], dict]:
    """
    Determine which file reader to use for the given collection auth_id and
    data file extension.
    """
    special_readers = {"snex23": snowex_csv.extract_metadata}

    for key, function in special_readers.items():
        if auth_id.lower().startswith(key):
            return function

    readers = {
        ".nc": netcdf_reader.extract_metadata,
        ".csv": csv.extract_metadata,
    }

    return readers[extension]
