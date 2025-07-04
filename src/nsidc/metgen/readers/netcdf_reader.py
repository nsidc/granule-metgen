"""
Interface functions that read various metadata attribute values
from source science data files.
"""

import logging
import os.path
import re

import xarray as xr
from dateutil.parser import parse
from isoduration import parse_duration
from pyproj import CRS, Transformer
from shapely import LineString

from nsidc.metgen import constants
from nsidc.metgen.config import Config
from nsidc.metgen.readers import utilities


def extract_metadata(
    netcdf_path: str,
    temporal_content: list,
    spatial_content: list,
    configuration: Config,
    gsr: str,
) -> dict:
    """
    Read the content at netcdf_path and return a structure with temporal coverage
    information, spatial coverage information, file size, and production datetime.
    """

    # TODO: handle errors if any needed attributes don't exist.
    try:
        # TODO: We are telling xarray not to decode times here in order to get around
        #       what appears to be a bug affecting some datasets. Without this
        #       (defaults to True), xarrray is unable to open impacted files and
        #       throws an exception, indicating it is unable to apply the scale
        #       and offset to the time. If this bug is fixed in xarray, remove
        #       the decode_times parameter so that xarray will correctly apply
        #       the scale and offset in those cases. Although we don't need
        #       decoded time values at the moment, it seems the safer option for
        #       our future selves & other devs.
        # NOTE: We know this occurs with the NSIDC-0630 v2 collection, and it may
        #       occur on others.
        netcdf = xr.open_dataset(netcdf_path, decode_coords="all", decode_times=False)
    except Exception:
        raise Exception(f"Could not open netCDF file {netcdf_path}")

    # Use temporal coverage from premet file if it exists
    if temporal_content:
        temporal = temporal_content
    else:
        temporal = time_range(os.path.basename(netcdf_path), netcdf, configuration)

    # Use spatial coverage from spatial (or spo) file if it exists
    if spatial_content is not None:
        geom = spatial_content
    else:
        geom = spatial_values(netcdf, configuration, gsr)

    return {
        "production_date_time": date_modified(netcdf, configuration),
        "temporal": temporal,
        "geometry": geom,
    }


def time_range(netcdf_filename, netcdf, configuration):
    """Return an array of datetime strings"""

    coverage_start = time_coverage_start(netcdf_filename, netcdf, configuration)
    coverage_end = time_coverage_end(netcdf, configuration, coverage_start)

    if coverage_start and coverage_end:
        return utilities.refine_temporal([coverage_start, coverage_end])
    else:
        # In theory, we should never get here.
        log_and_raise_error(
            "Could not determine time coverage from NetCDF attributes. Ensure \
time_start_regex and time_coverage_duration are set in the configuration file."
        )


def time_coverage_start(netcdf_filename, netcdf, configuration):
    if "time_coverage_start" in netcdf.attrs:
        coverage_start = netcdf.attrs["time_coverage_start"]

    elif configuration.time_start_regex:
        m = re.match(configuration.time_start_regex, netcdf_filename)
        coverage_start = m.group("time_coverage_start")

    if coverage_start is not None:
        return utilities.ensure_iso_datetime(coverage_start)
    else:
        log_and_raise_error(
            "NetCDF file does not have `time_coverage_start` global attribute. \
Set `time_start_regex` in the configuration file."
        )


def time_coverage_end(netcdf, configuration, time_coverage_start):
    """
    Use time_coverage_end attribute if it exists, otherwise use a duration
    value from the ini file to calculate the time_coverage_end.

    TODO: Look for time_coverage_duration attribute in the netCDF file before
    using a value from the ini file.
    """
    if "time_coverage_end" in netcdf.attrs:
        return utilities.ensure_iso_datetime(netcdf.attrs["time_coverage_end"])

    if configuration.time_coverage_duration and time_coverage_start:
        try:
            duration = parse_duration(configuration.time_coverage_duration)
            coverage_end = parse(time_coverage_start) + duration
            return utilities.ensure_iso_datetime(coverage_end.isoformat())
        except Exception:
            log_and_raise_error(
                "NetCDF file does not have `time_coverage_end` global attribute. \
Set `time_coverage_duration` in the configuration file."
            )


def spatial_values(netcdf, configuration, gsr) -> list[dict]:
    """
    Return an array of dicts, each dict representing one lat/lon pair like so:
        {
            "Longitude": float,
            "Latitude": float
        }
    Eventually this should be pulled out of the netCDF-specific code into a
    general-use module.
    """

    grid_mapping_name = find_grid_mapping(netcdf)
    xformer = crs_transformer(netcdf[grid_mapping_name])
    pad = pixel_padding(netcdf[grid_mapping_name], configuration)
    xdata = find_coordinate_data_by_standard_name(netcdf, "projection_x_coordinate")
    ydata = find_coordinate_data_by_standard_name(netcdf, "projection_y_coordinate")

    # if cartesian, look for bounding rectangle attributes and return upper
    # left and lower right points
    if gsr == constants.CARTESIAN:
        return bounding_rectangle_from_attrs(netcdf)

    if len(xdata) * len(ydata) == 2:
        raise Exception("Don't know how to create polygon around two points")

    # Extract a subset of points (or the single point) and transform to lon, lat
    points = [xformer.transform(x, y) for (x, y) in distill_points(xdata, ydata, pad)]

    return [
        {"Longitude": round(lon, 8), "Latitude": round(lat, 8)} for (lon, lat) in points
    ]


# TODO: If no bounding attributes, add fallback options?
# - look for geospatial_bounds global attribute and parse points from its polygon
# - pull points from spatial coordinate values (but this might only be appropriate for
#   some projections, for example EASE-GRID2)
# Also TODO: Find a more elegant way to handle these attributes.
def bounding_rectangle_from_attrs(netcdf):
    global_attrs = set(netcdf.attrs.keys())
    bounding_attrs = [
        "geospatial_lon_max",
        "geospatial_lat_max",
        "geospatial_lon_min",
        "geospatial_lat_min",
    ]
    LON_MAX = 0
    LAT_MAX = 1
    LON_MIN = 2
    LAT_MIN = 3

    def latlon_attr(index):
        return float(round(netcdf.attrs[bounding_attrs[index]], 8))

    if set(bounding_attrs).issubset(global_attrs):
        return [
            {"Longitude": latlon_attr(LON_MIN), "Latitude": latlon_attr(LAT_MAX)},
            {"Longitude": latlon_attr(LON_MAX), "Latitude": latlon_attr(LAT_MIN)},
        ]

    # Global attributes not available, show error
    log_and_raise_error("Global attributes for bounding rectangle not available")


def distill_points(xdata, ydata, pad):
    # check for single point
    if len(xdata) * len(ydata) == 1:
        return [(xdata[0], ydata[0])]

    return thinned_perimeter(xdata, ydata, pad)


def find_grid_mapping(netcdf):
    # We currently assume only one grid mapping variable exists, it's a
    # data variable, and it has a grid_mapping_name attribute.
    # Possible TODO: filter_by_attrs isn't really all that helpful since it doesn't
    # return *just* the variable (coordinate or data variable) of interest. The
    # subsequent "for" loop ensures the correct variable is actually identified.
    # We could just stick with the "for" loop (or whatever would be python better
    # practice).
    grid_mapping_var = netcdf.filter_by_attrs(grid_mapping_name=lambda v: v is not None)

    if grid_mapping_var is None or grid_mapping_var.variables is None:
        log_and_raise_error("No grid mapping exists to transform coordinates.")

    for var in grid_mapping_var.variables:
        if "crs_wkt" in netcdf[var].attrs:
            return var

    return None


def crs_transformer(grid_mapping_var):
    data_crs = CRS.from_wkt(grid_mapping_var.attrs["crs_wkt"])
    return Transformer.from_crs(data_crs, CRS.from_epsg(4326), always_xy=True)


def find_coordinate_data_by_standard_name(netcdf, standard_name_value):
    # TODO: See comments in find_grid_mapping re: use of filter_by_attrs
    matched = netcdf.filter_by_attrs(standard_name=standard_name_value)
    data = []

    if matched is not None and matched.coords is not None:
        for coord in matched.coords:
            if "standard_name" in netcdf[coord].attrs:
                data = netcdf[coord].data
                break

    return data


def pixel_padding(netcdf_var, configuration):
    if "GeoTransform" in netcdf_var.attrs:
        geotransform = netcdf_var.attrs["GeoTransform"]
        pixel_size = abs(float(geotransform.split()[1]))
    elif configuration.pixel_size is not None:
        pixel_size = configuration.pixel_size
    else:
        log_and_raise_error(
            "NetCDF grid mapping variable does not have `GeoTransform` attribute. \
Set `pixel_size` in the configuration file."
        )

    return pixel_size / 2


def thinned_perimeter(rawx, rawy, pad=0):
    """
    Generate the thinned perimeter of a grid.
    """

    # Breaking this out into excruciating detail so someone can check my logic.
    # Padding approach assumes upper left of grid is represented at array
    # elements[0, 0]. Points are ordered in a counter-clockwise direction.
    # left: all x at x[0]-pad, prepend y[0] + pad, append y[-1] - pad
    # bottom: prepend x[0] - pad, append x[-1] + pad, all y at y[-1] - pad
    # right: all x at x[-1] + pad, prepend y[-1] - pad, append y[0] + pad
    # top: prepend x[-1] + pad, append x[0] - pad, all y at y[0] + pad
    leftx = rawx[0] - pad
    rightx = rawx[-1] + pad
    uppery = rawy[0] + pad
    lowery = rawy[-1] - pad

    ul = [leftx, uppery]
    ll = [leftx, lowery]
    lr = [rightx, lowery]
    ur = [rightx, uppery]

    left = LineString([ul, ll])
    bottom = LineString([ll, lr])
    right = LineString([lr, ur])
    top = LineString([ur, ul])

    # Previous code used actual values from xdata and ydata, but only selected a
    # subset of the array entries. The current code takes advantage of LineString's
    # ability to interpolate points, but I'm not convinced it's a better approach.
    # Discuss!
    leftpts = [
        left.interpolate(fract, normalized=True) for fract in [0, 0.2, 0.4, 0.6, 0.8]
    ]
    bottompts = [
        bottom.interpolate(fract, normalized=True) for fract in [0, 0.2, 0.4, 0.6, 0.8]
    ]
    rightpts = [
        right.interpolate(fract, normalized=True) for fract in [0, 0.2, 0.4, 0.6, 0.8]
    ]

    # Interpolate all the way to "1" so first and last points in the perimeter are the
    # same for Polygon creation purposes.
    toppts = [
        top.interpolate(fract, normalized=True) for fract in [0, 0.2, 0.4, 0.6, 0.8, 1]
    ]

    # TODO: ensure points are some minimum distance from each other (need CMR requirements)
    # need tests:
    # leftpts[0] should be upper left point
    # bottompts[0] should be lower left point
    # rightpts[0] should be lower right point
    # toppts[0] should be upper right point
    # toppts[-1] should equal leftpts[0]
    return (
        [(pt.x, pt.y) for pt in leftpts]
        + [(pt.x, pt.y) for pt in bottompts]
        + [(pt.x, pt.y) for pt in rightpts]
        + [(pt.x, pt.y) for pt in toppts]
    )


# if no date modified in netcdf global attributes, then retrieve from configuration
# should errors be added to ledger for summary purposes, or simply plopped into log?
def date_modified(netcdf, configuration):
    if "date_modified" in netcdf.attrs.keys():
        datetime_str = netcdf.attrs["date_modified"]
    else:
        datetime_str = configuration.date_modified

    if datetime_str:
        return utilities.ensure_iso_datetime(datetime_str)
    else:
        log_and_raise_error(
            "NetCDF file does not have `date_modified` global attribute. \
Set `date_modified` in the configuration file."
        )


def log_and_raise_error(err):
    logger = logging.getLogger(constants.ROOT_LOGGER)
    logger.error(err)

    raise Exception(err)
