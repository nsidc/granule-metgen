"""
Read a csv data file containing LAT, LON, and DATE columns.
"""

import os.path
from datetime import timedelta, timezone

import pandas as pd
from funcy import lpluck

from nsidc.metgen.config import Config
from nsidc.metgen.readers import utilities


def extract_metadata(
    csv_path: str, premet_path: str, spatial_path: str, configuration: Config
) -> dict:
    df = pd.read_csv(csv_path)

    return {
        "size_in_bytes": os.path.getsize(csv_path),
        "production_date_time": configuration.date_modified,
        "temporal": data_datetime(df, premet_path),
        "geometry": {"points": bbox(spatial_values(df, spatial_path, configuration))},
    }


def data_datetime(df, premet_path) -> list:
    if premet_path is not None:
        return utilities.temporal_from_premet(premet_path)

    def formatted(date, dt):
        return (
            (date.replace(tzinfo=timezone.utc) + timedelta(seconds=dt))
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )

    data_dates = pd.to_datetime(df["DATE"], format="%d%m%y")
    data_times = df["TIME"]

    if data_dates.size > 0 and data_times.size > 0:
        return [
            formatted(data_dates.iat[0], data_times.iat[0]),
            formatted(data_dates.iat[-1], data_times.iat[-1]),
        ]
    else:
        return None


def bbox(points):
    minlon = min(lpluck("Longitude", points))
    minlat = min(lpluck("Latitude", points))
    maxlon = max(lpluck("Longitude", points))
    maxlat = max(lpluck("Latitude", points))

    def point(lon, lat):
        return {"Longitude": lon, "Latitude": lat}

    return [
        point(minlon, maxlat),
        point(minlon, minlat),
        point(maxlon, minlat),
        point(maxlon, maxlat),
        point(minlon, maxlat),
    ]


def spatial_values(df, spatial_path, _):
    """Get spatial coverage from spatial file if it exists, otherwise parse from CSV"""
    if spatial_path is not None:
        return utilities.points_from_spatial(spatial_path)

    return [
        {"Longitude": lon, "Latitude": lat} for (lon, lat) in zip(df["LON"], df["LAT"])
    ]
