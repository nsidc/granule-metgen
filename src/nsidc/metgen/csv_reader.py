import csv
import os.path
import re
from datetime import timezone

from dateutil.parser import parse
from pyproj import CRS, Transformer


def extract_metadata(csv_path, configuration):
    with open(csv_path, newline="") as csvfile:
        csvreader = csv.reader(csvfile, delimiter=",")

        return {
            "size_in_bytes": os.path.getsize(csv_path),
            "production_date_time": configuration.date_modified,
            "temporal": data_datetime(csvreader, configuration),
            "geometry": {"points": spatial_values(csvreader, configuration)},
        }


# Add new data_datetime strategy that gets DATE and TIME columns and finds range


def data_datetime(csvreader, configuration):
    """Get "# Date ..." """
    pattern = re.compile("^.*Date")

    val = get_key_value(csvreader, pattern)
    if val is not None:
        dt = parse(val)
        return [
            (
                dt.replace(tzinfo=timezone.utc)
                .isoformat(timespec="milliseconds")
                .replace("+00:00", "Z")
            )
        ]
    else:
        return None


# Add new spatial_values strategy that gets LAT & LON columns


def spatial_values(csvreader, configuration):
    zone = get_key_value(csvreader, "^.*UTM_Zone")
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
