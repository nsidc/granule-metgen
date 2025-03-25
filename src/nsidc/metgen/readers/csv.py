import os.path
from datetime import timezone

import pandas as pd
from funcy import lpluck


def extract_metadata(csv_path, configuration):
    df = pd.read_csv(csv_path)

    return {
        "size_in_bytes": os.path.getsize(csv_path),
        "production_date_time": configuration.date_modified,
        "temporal": data_datetime(df, configuration),
        "geometry": {"points": bbox(spatial_values(df, configuration))},
    }


def data_datetime(df, _):
    data_dates = pd.to_datetime(df["DATE"], format="%d%m%y")

    # TODO: Read and parse the TIME and include in first & last

    if data_dates.size > 0:
        first = data_dates.iat[0] \
            .replace(tzinfo=timezone.utc) \
            .isoformat(timespec="milliseconds") \
            .replace("+00:00", "Z")
        last = data_dates.iat[-1] \
            .replace(tzinfo=timezone.utc) \
            .isoformat(timespec="milliseconds") \
            .replace("+00:00", "Z")

        return [first, last]
    else:
        return []


def bbox(points):
    minlon = min(lpluck("Longitude", points))
    minlat = min(lpluck("Latitude", points))
    maxlon = max(lpluck("Longitude", points))
    maxlat = max(lpluck("Latitude", points))

    def point(lon, lat): 
        return { "Longitude": lon, "Latitude": lat }

    return [
        point(maxlat, minlon),
        point(minlat, minlon),
        point(minlat, maxlon),
        point(maxlat, maxlon),
        point(maxlat, minlon),
    ]


def spatial_values(df, _):
    lats = df["LAT"]
    lons = df["LON"]

    return [{"Longitude": lon, "Latitude": lat} for (lon, lat) in zip(lons, lats)]
