import re
from datetime import timezone

from dateutil.parser import parse
from funcy import first, keep, last

from nsidc.metgen import constants


def temporal_from_premet(pdict: dict) -> list:
    # Show error if no date/time information is in file
    begin_date_keys = ["RangeBeginningDate", "Begin_date"]
    begin_time_keys = ["RangeBeginningTime", "Begin_time"]
    end_date_keys = [
        "RangeEndingDate",
        "End_date",
    ]
    end_time_keys = ["RangeEndingTime", "End_time"]

    begin = list(
        keep(
            [
                find_key_aliases(begin_date_keys, pdict),
                find_key_aliases(begin_time_keys, pdict),
            ]
        )
    )
    end = list(
        keep(
            [
                find_key_aliases(end_date_keys, pdict),
                find_key_aliases(end_time_keys, pdict),
            ]
        )
    )

    return [
        ensure_iso_datetime(td) for td in list(keep([" ".join(begin), " ".join(end)]))
    ]


def find_key_aliases(aliases: list, datetime_parts: dict) -> str:
    val = None

    for key in aliases:
        if key in datetime_parts:
            val = datetime_parts[key]
            break

    return val


def premet_values(premet_path: str) -> dict:
    pdict = {}

    if premet_path is None:
        return None

    additional_atts = []
    with open(premet_path) as premet_file:
        for line in premet_file:
            key, val = parse_premet_entry(line)
            if re.match("Container", key):
                _, namevalue = parse_premet_entry(next(premet_file))
                _, attvalue = parse_premet_entry(next(premet_file))
                additional_atts.append({"Name": namevalue, "Values": [attvalue]})
            else:
                pdict[key] = val

    # Include any additional attributes
    if additional_atts:
        pdict[constants.UMMG_ADDITIONAL_ATTRIBUTES] = additional_atts

    return pdict


def parse_premet_entry(pline: str):
    return re.sub(r"\s+", "", pline).split("=")


def ensure_iso_datetime(datetime_str):
    """
    Parse ISO-standard datetime strings without a timezone identifier.
    """
    iso_obj = parse(datetime_str)
    return format_timezone(iso_obj)


def format_timezone(iso_obj):
    return (
        iso_obj.replace(tzinfo=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def points_from_spatial(spatial_path: str, gsr: str) -> list:
    """
    Read (lon, lat) points from a .spatial or .spo file.
    """

    if spatial_path is None:
        return None

    points = raw_points(spatial_path)

    # TODO: We only need to do the "spo vs spatial" check once, since the same file
    # type will be used for all granules.
    if re.search(constants.SPO_SUFFIX, spatial_path):
        return parse_spo(gsr, points)

    # confirm the number of points makes sense for this granule spatial representation
    if not valid_spatial_config(gsr, len(points)):
        raise Exception(
            "Unsupported combination of granule spatial representation and point count"
        )

    # TODO: If point count is greater than 1, we need to create or one or more polygons
    # around a point cloud (could be a flight line, or only a few points).
    # Flight line files can be huge so might need another approach to handling the content!
    return points


def valid_spatial_config(gsr: str, point_count: int) -> str:
    if (gsr == constants.CARTESIAN) and (point_count == 2):
        return True

    if gsr == constants.GEODETIC:
        return True

    return None


def parse_spo(gsr: str, points: list) -> list:
    """
    Read points from a .spo file, reverse the order of the points to comply with
    the Cumulus requirement for a clockwise order to polygon points, and ensure
    the polygon is closed. Raise an exception if either the granule spatial representation
    or the number of points don't support a gpolygon.
    """
    if (gsr == constants.CARTESIAN) or (len(points) <= 2):
        raise Exception("spo content invalid")

    return [p for p in reversed(closed_polygon(points))]


def raw_points(spatial_path: str) -> list:
    with open(spatial_path) as file:
        return [
            {"Longitude": float(lon), "Latitude": float(lat)}
            for line in file
            for lon, lat in [line.split()]
        ]


def closed_polygon(raw_points: list[dict]) -> list[dict]:
    """
    Return a copy of the input list, extended if necessary to ensure the first
    and last points of the list have the same value. The original list is not
    modified.
    """
    points = raw_points.copy()
    if len(points) > 2 and (first(points) != last(points)):
        points.append(first(points))

    return points
