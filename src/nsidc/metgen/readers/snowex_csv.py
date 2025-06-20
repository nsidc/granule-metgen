"""
Read a csv data file specific to SNOWEX.
"""

import csv
import re

from pyproj import CRS, Transformer

from nsidc.metgen.config import Config
from nsidc.metgen.readers import utilities


def extract_metadata(
    csv_path: str,
    temporal_content: list,
    spatial_content: list,
    configuration: Config,
    _,
) -> dict:
    with open(csv_path, newline="") as csvfile:
        csvreader = csv.reader(csvfile, delimiter=",")

        return {
            "temporal": data_datetime(csvreader, temporal_content),
            "geometry": spatial_values(csvreader, spatial_content, configuration),
        }


# Add new data_datetime strategy that gets DATE and TIME columns and finds range


def data_datetime(csvreader, temporal_content: list) -> list:
    """Get temporal extent from premet file if it exists, otherwise parse from CSV"""
    if temporal_content:
        return temporal_content

    pattern = re.compile("^.*Date")

    val = get_key_value(csvreader, pattern)
    if val is not None:
        return [utilities.ensure_iso_datetime(val)]
    else:
        return None


def spatial_values(csvreader, spatial_content, _):
    """Get spatial coverage from spatial file if it exists, otherwise parse from CSV"""
    if spatial_content is not None:
        return spatial_content

    zone_string = get_key_value(csvreader, "^.*UTM_Zone")
    zone = int(re.sub(r"\D", "", zone_string)) if zone_string else 0
    easting = get_key_value(csvreader, "^.*Easting")
    northing = get_key_value(csvreader, "^.*Northing")
    utm_crs = CRS(proj="utm", zone=zone, ellps="WGS84")
    transformer = Transformer.from_crs(utm_crs, "EPSG:4326")

    lat, lon = transformer.transform(easting, northing)

    return [{"Latitude": lat, "Longitude": lon}]


def get_key_value(csvreader, key_pattern):
    pattern = re.compile(key_pattern)
    for row in csvreader:
        if re.match(pattern, row[0]):
            return row[1]

    return None
