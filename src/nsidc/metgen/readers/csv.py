"""
Read a csv data file containing LAT, LON, and DATE columns.
"""

from datetime import timedelta, timezone

import pandas as pd
from funcy import lpluck

from nsidc.metgen.config import Config
from nsidc.metgen.readers import utilities


def extract_metadata(
    csv_path: str,
    temporal_content: list,
    spatial_content: list,
    configuration: Config,
    _,
) -> dict:
    df = pd.read_csv(csv_path)

    return {
        "temporal": data_datetime(df, temporal_content),
        "geometry": bbox(spatial_values(df, spatial_content, configuration)),
    }


def data_datetime(df, temporal_content: list) -> list:
    if temporal_content:
        return temporal_content

    def formatted(date, dt):
        return (
            (date.replace(tzinfo=timezone.utc) + timedelta(seconds=dt))
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )

    data_dates = pd.to_datetime(df["DATE"], format="%d%m%y")
    data_times = df["TIME"]

    if data_dates.size > 0 and data_times.size > 0:
        return utilities.refine_temporal(
            [
                formatted(data_dates.iat[0], data_times.iat[0]),
                formatted(data_dates.iat[-1], data_times.iat[-1]),
            ]
        )
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


def spatial_values(df, spatial_content, _):
    """Get spatial coverage from spatial file if it exists, otherwise parse from CSV"""
    if spatial_content is not None:
        return spatial_content

    return [
        {"Longitude": lon, "Latitude": lat} for (lon, lat) in zip(df["LON"], df["LAT"])
    ]
