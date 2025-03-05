import csv
import os.path
import re
from datetime import timezone

from dateutil.parser import parse


def extract_metadata(csv_path, configuration):
    with open(csv_path, newline="") as csvfile:
        csvreader = csv.reader(csvfile, delimiter=",")

        return {
            "size_in_bytes": os.path.getsize(csv_path),
            "production_date_time": configuration.date_modified,
            "temporal": data_datetime(csvreader, configuration),
            "geometry": {"point": spatial_values(csvreader, configuration)},
        }


def data_datetime(csvreader, configuration):
    """Get "# Date ..." """
    pattern = re.compile("^.*Date")
    for row in csvreader:
        if re.match(pattern, row[0]):
            dt = parse(row[1])
            return (
                dt.replace(tzinfo=timezone.utc)
                .isoformat(timespec="milliseconds")
                .replace("+00:00", "Z")
            )
    return None


def spatial_values(csv, configuration):
    # Get: UTM_Zone
    # Get: Easting
    # Get: Northing
    return "TODO: point"
