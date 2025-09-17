import re
from datetime import timezone

from dateutil.parser import parse
from funcy import distinct, first, last, lkeep, partial

from nsidc.metgen import config, constants
from nsidc.metgen.spatial import create_flightline_polygon


def temporal_from_premet(pdict: dict) -> list:
    """
    Extract temporal information from premet file contents.
    """
    begin_date_keys = ["RangeBeginningDate", "Begin_date"]
    begin_time_keys = ["RangeBeginningTime", "Begin_time"]
    end_date_keys = [
        "RangeEndingDate",
        "End_date",
    ]
    end_time_keys = ["RangeEndingTime", "End_time"]

    begin = lkeep(
        [
            find_key_aliases(begin_date_keys, pdict),
            find_key_aliases(begin_time_keys, pdict),
        ]
    )
    end = lkeep(
        [
            find_key_aliases(end_date_keys, pdict),
            find_key_aliases(end_time_keys, pdict),
        ]
    )

    datetimes = lkeep([" ".join(begin), " ".join(end)])

    return [ensure_iso_datetime(dt) for dt in distinct(datetimes)]


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
    any included additional attributes and/or platform information.
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
    platform_details = []
    with open(premet_path) as premet_file:
        for line in premet_file:
            key, val = parse_premet_entry(line)
            if re.match("Container", key):
                match val:
                    case constants.PREMET_ADDITIONAL_ATTRIBUTES:
                        additional_atts.append(parse_additional_attributes(premet_file))

                    case constants.PREMET_ASSOCIATED_PLATFORM:
                        platform_details.append(parse_platform_details(premet_file))

            else:
                pdict[key] = val

    # Include any additional attributes
    if additional_atts:
        pdict[constants.UMMG_ADDITIONAL_ATTRIBUTES] = additional_atts

    # Include any platform information
    if platform_details:
        pdict[constants.UMMG_PLATFORM] = platform_details

    return pdict


def parse_additional_attributes(premet_file):
    # next two lines in the premet file represent the attribute name and value
    attribute_keys = constants.PREMET_KEYS[constants.PREMET_ADDITIONAL_ATTRIBUTES]

    namekey, namevalue = parse_premet_entry(next(premet_file))
    attkey, attvalue = parse_premet_entry(next(premet_file))

    check_premet_keys(
        constants.PREMET_ADDITIONAL_ATTRIBUTES, [namekey, attkey], attribute_keys
    )

    return {"Name": namevalue, "Values": [attvalue]}


def parse_platform_details(premet_file):
    # next three lines in the premet file represent platform, instrument, and sensor
    platform_keys = constants.PREMET_KEYS[constants.PREMET_ASSOCIATED_PLATFORM]

    pkey, platform = parse_premet_entry(next(premet_file))
    ikey, instrument = parse_premet_entry(next(premet_file))
    skey, sensor = parse_premet_entry(next(premet_file))
    check_premet_keys(
        constants.PREMET_ASSOCIATED_PLATFORM, [pkey, ikey, skey], platform_keys
    )

    return {
        "ShortName": platform,
        "Instruments": [
            {"ShortName": instrument, "ComposedOf": [{"ShortName": sensor}]}
        ],
    }


def check_premet_keys(entry_type, parsed, expected):
    if set(parsed) != set(expected):
        raise Exception(
            f"{entry_type} keys in the premet file are invalid. Expected {expected}."
        )


def parse_premet_entry(pline: str):
    """
    Break up a "key = value" pair, removing any beginning/trailing whitespace from the string parts.
    """
    parts = pline.split("=")
    return [p.strip() for p in parts]


def ensure_iso_datetime(datetime_str):
    """
    Parse ISO-standard datetime strings without a timezone identifier.
    """
    if datetime_str:
        iso_obj = parse(datetime_str)
        return format_timezone(iso_obj)

    return None


def format_timezone(iso_obj):
    return (
        iso_obj.replace(tzinfo=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def external_temporal_values(collection_temporal_override, premet_content, granule):
    """
    Extract temporal information from collection metadata or premet files according to .ini file settings.
    """
    if collection_temporal_override:
        return granule.collection.temporal_extent

    if premet_content:
        return refine_temporal(temporal_from_premet(premet_content))

    return []


def refine_temporal(tvals: list):
    """
    Reformat a list of temporal values to match the format from UMM-C metadata
    """
    keys = ["BeginningDateTime", "EndingDateTime"]
    if len(tvals) > 1:
        return [dict(zip(keys, tvals))]

    return tvals


def external_spatial_values(configuration, gsr, granule) -> list:
    """
    Retrieve spatial information from a granule-specific spatial or spo file, or
    the collection metadata.
    """
    if configuration.collection_geometry_override:
        # Get spatial coverage from collection
        return points_from_collection(granule.collection.spatial_extent)

    return points_from_spatial(granule.spatial_filename, gsr, configuration)


# TODO: Rename methods and parameters as needed to reduce overloading of the term "spatial."
# Clarify whether we're talking about a spatial file, a spo file, or "spatial content" more
# generically.
def points_from_spatial(
    spatial_path: str, gsr: str, configuration: config.Config = None
) -> list:
    """
    Read (lon, lat) points from a .spatial or .spo file.
    """

    if spatial_path == "":
        raise Exception(
            "spatial_dir is specified but no .spatial or .spo file exists for granule."
        )

    # If spatial_path doesn't exist, then spatial information is assumed to be available
    # in the granule data file or via collection metadata.
    if spatial_path is None:
        return None

    points = raw_points(spatial_path)
    if not points:
        raise Exception(f"No spatial values found in {spatial_path}.")

    # TODO: We really only need to do the "spo vs spatial" check once, since the same
    # file type will (should) be used for all granules.
    if re.search(constants.SPO_SUFFIX, spatial_path):
        return parse_spo(gsr, points)

    else:
        points = parse_spatial(points, configuration)

    # confirm the number of points makes sense for this granule spatial representation
    if not valid_spatial_config(gsr, len(points)):
        raise Exception(
            f"Unsupported combination of {gsr} and point count of {len(points)}."
        )

    return points


def parse_spatial(spatial_values: list, configuration: config.Config = None):
    # If only a single point, or two points (assumed to identify a bounding rectangle),
    # return spatial values without further processing
    if len(spatial_values) <= 2:
        return spatial_values

    # Generate polygon from spatial file data
    if configuration is not None and configuration.spatial_polygon_enabled:
        try:
            # Create configured polygon generator using partial application
            generate_polygon = partial(
                create_flightline_polygon,
                target_coverage=configuration.spatial_polygon_target_coverage,
                max_vertices=configuration.spatial_polygon_max_vertices,
                cartesian_tolerance=configuration.spatial_polygon_cartesian_tolerance,
            )

            # Extract lon/lat arrays from spatial_values
            lons = [point["Longitude"] for point in spatial_values]
            lats = [point["Latitude"] for point in spatial_values]

            # Generate polygon using our configured spatial module
            polygon, metadata = generate_polygon(lons, lats)

            if polygon is not None:
                coords = list(polygon.exterior.coords)
                polygon_points = [
                    {"Longitude": float(lon), "Latitude": float(lat)}
                    for lon, lat in coords
                ]
                return polygon_points

        except Exception as e:
            import logging

            logger = logging.getLogger(constants.ROOT_LOGGER)
            logger.error(f"Polygon generation failed: {e}")

    # Configuration does not exist, or polygon processing is not enabled.
    # Return values without further processing
    return spatial_values


def valid_spatial_config(gsr: str, point_count: int) -> str:
    if not point_count:
        return False

    if point_count == 2:
        if gsr == constants.CARTESIAN:
            return True

        else:
            return False

    if gsr == constants.GEODETIC:
        return True

    return False


def parse_spo(gsr: str, points: list) -> list:
    """
    Reverse the order of the points to comply with the Cumulus requirement for a
    clockwise order to polygon points, and ensure the polygon is closed. Raise an
    exception if either the granule spatial representation or the number of
    points don't support a gpolygon.
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
