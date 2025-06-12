import re
from datetime import timezone

from dateutil.parser import parse
from funcy import first, keep, last

from nsidc.metgen import constants


def temporal_from_premet(pdict: dict) -> list:
    """
    Extract temporal information from premet file contents.
    """
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
    """
    Read premet file and return a dict containing temporal information and
    any included additional attributes.
    """
    pdict = {}

    # TODO: Relying on an empty string to indicate a missing premet or spatial/spo
    # file name feels fragile. Figure out a more robust means of ensuring an ancillary
    # file exists if the .ini file includes a premet and/or spatial directory location.
    if premet_path == "":
        raise Exception(
            "premet_dir is specified but no premet file exists for granule."
        )

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


def external_spatial_values(collection_geometry_override, gsr, granule) -> list:
    """
    Retrieve spatial information from a granule-specific spatial (or spo) file, or
    the collection metadata.
    """
    if collection_geometry_override:
        # Get spatial coverage from collection
        return points_from_collection(granule.collection.spatial_extent)

    return points_from_spatial(granule.spatial_filename, gsr)


def points_from_spatial(spatial_path: str, gsr: str) -> list:
    """
    Read (lon, lat) points from a .spatial or .spo file.
    """

    if spatial_path == "":
        raise Exception(
            "spatial_dir is specified but no .spatial or .spo file exists for granule."
        )

    if spatial_path is None:
        return None

    points = raw_points(spatial_path)

    # TODO: We really only need to do the "spo vs spatial" check once, since the same
    # file type will (should) be used for all granules.
    if re.search(constants.SPO_SUFFIX, spatial_path):
        return parse_spo(gsr, points)

    # confirm the number of points makes sense for this granule spatial representation
    if not valid_spatial_config(gsr, len(points)):
        raise Exception(
            f"Unsupported combination of {gsr} and point count of {len(points)}."
        )

    # TODO: Handle point cloud creation here if point count is greater than 1 and gsr
    # is geodetic. Note! Flight line files can be huge!
    return points


def valid_spatial_config(gsr: str, point_count: int) -> str:
    if (gsr == constants.CARTESIAN) and (point_count == 2):
        return True

    if gsr == constants.GEODETIC:
        return True

    return False


def parse_spo(gsr: str, points: list) -> list:
    """
    Read points from a .spo file, reverse the order of the points to comply with
    the Cumulus requirement for a clockwise order to polygon points, and ensure
    the polygon is closed. Raise an exception if either the granule spatial representation
    or the number of points don't support a gpolygon.
    """
    if gsr == constants.CARTESIAN:
        raise Exception(
            f"Granule spatial representation {gsr} cannot be applied to spo content."
        )

    if len(points) <= 2:
        raise Exception("spo file must contain at least three points.")

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


def points_from_collection(collection_spatial):
    """
    Parse spatial information from collection metadata. Annoyingly, this process
    will be reversed when we apply the template to populate UMM-G output. The
    current approach allows for consistent template population steps regardless
    of whether points were retrieved from a spatial file or the collection
    metadata, though.
    """
    return [
        {
            "Longitude": collection_spatial[0]["WestBoundingCoordinate"],
            "Latitude": collection_spatial[0]["NorthBoundingCoordinate"],
        },
        {
            "Longitude": collection_spatial[0]["EastBoundingCoordinate"],
            "Latitude": collection_spatial[0]["SouthBoundingCoordinate"],
        },
    ]
