import json
import logging
import os.path
import re
from datetime import timezone
from isoduration import parse_duration

import xarray as xr
from dateutil.parser import parse
from pyproj import CRS, Transformer

from nsidc.metgen import constants


def extract_metadata(netcdf_path, configuration):
    """
    Read the content at netcdf_path and return a structure with temporal coverage
    information, spatial coverage information, file size, and production datetime.
    """

    # TODO: handle errors if any needed attributes don't exist.
    netcdf = xr.open_dataset(netcdf_path, decode_coords="all")

    return {
        "size_in_bytes": os.path.getsize(netcdf_path),
        "production_date_time": date_modified(netcdf, configuration),
        "temporal": time_range(os.path.basename(netcdf_path), netcdf, configuration),
        "geometry": {"points": json.dumps(spatial_values(netcdf, configuration))},
    }


def time_range(netcdf_filename, netcdf, configuration):
    """Return an array of datetime strings"""
    # datetimes.append(time_coverage_start(netcdf_filename, netcdf, configuration))
    coverage_start = time_coverage_start(netcdf_filename, netcdf, configuration)
    # datetimes.append(ensure_iso(netcdf.attrs["time_coverage_end"]))
    coverage_end = time_coverage_end(netcdf, configuration, coverage_start)

    if (coverage_start and coverage_end):
        return [coverage_start, coverage_end]

    return []

def time_coverage_start(netcdf_filename, netcdf, configuration):
    if netcdf.attrs["time_coverage_start"]:
        return ensure_iso(netcdf.attrs["time_coverage_start"])

    if configuration.filename_regex:
        m = re.match(configuration.filename_regex, netcdf_filename)
        return ensure_iso(m.group('time_coverage_start'))

    return None

def time_coverage_end(netcdf, configuration, time_coverage_start):
    if netcdf.attrs["time_coverage_end"]:
        return ensure_iso(netcdf.attrs["time_coverage_end"])

    if (configuration.time_coverage_duration and time_coverage_start):
        duration = parse_duration(configuration.time_coverage_duration)
        return(ensure_iso(parse(time_coverage_start) + duration))
    
    return None

def spatial_values(netcdf, configuration):
    """
    Return an array of dicts, each dict representing one lat/lon pair like so:

        {
            "Longitude: float,
            "Latitude: float
        }
    Eventually this can/should be pulled out of the netCDF-specific code into a
    general-use module.
    """

    # We currently assume only one grid mapping coordinate variable exists.
    grid_mapping_name = lambda v: v is not None
    grid_mapping_var = netcdf.filter_by_attrs(grid_mapping_name=grid_mapping_name)
    grid_mapping_var_name = list(grid_mapping_var.coords)[0]
    wkt = netcdf.variables[grid_mapping_var_name].attrs['crs_wkt']

    data_crs = CRS.from_wkt(wkt)
    crs_4326 = CRS.from_epsg(4326)
    xformer = Transformer.from_crs(data_crs, crs_4326, always_xy=True)

    pad = pixel_padding(netcdf.variables[grid_mapping_var_name], configuration)
    xdata = [x - pad if x < 0 else x + pad for x in netcdf.x.data]
    ydata = [y - pad if y < 0 else y + pad for y in netcdf.y.data]

    # Extract the perimeter points and transform to lon, lat
    perimeter = [xformer.transform(x, y) for (x, y) in thinned_perimeter(xdata, ydata)]

    return [
        {"Longitude": round(lon, 8), "Latitude": round(lat, 8)}
        for (lon, lat) in perimeter
    ]


def pixel_padding(netcdf_var, configuration):
    # Adding padding should give us values that match up to the
    # netcdf.attrs.geospatial_bounds
    # instead of using Geotransform:
    # if x and y have attributes valid_range then difference between
    # valid range and first x value for example should be padding
    # if no valid range attribute then look for pixel size value in ini
    if netcdf_var.attrs['GeoTransform'] is None:
        geotransform = configuration.geotransform
    else:
        geotransform = netcdf_var.attrs['GeoTransform']

    # in ini file: geospatial_x_resolution, geospatial_y_resolution
    return abs(float(geotransform.split()[1])) / 2


def thinned_perimeter(xdata, ydata):
    """
    Extract the thinned perimeter of a grid.
    """
    xindices = index_subset(len(xdata))
    yindices = index_subset(len(ydata))
    xlen = len(xindices)
    ylen = len(yindices)

    # Pull out just the perimeter of the grid, counter-clockwise direction,
    # starting at top left.
    # xindex[0], yindex[0]..yindex[-2]
    left = [(x, y) for x in xdata[:1] for i in yindices[: ylen - 1] for y in [ydata[i]]]

    # xindex[0]..xindex[-2], yindex[-1]
    bottom = [
        (x, y) for i in xindices[: xlen - 1] for x in [xdata[i]] for y in ydata[-1:]
    ]

    # xindex[-1], yindex[-1]..yindex[1]
    right = [
        (x, y)
        for x in xdata[-1:]
        for i in yindices[ylen - 1 : 0 : -1]
        for y in [ydata[i]]
    ]

    # xindex[-1]..xindex[0], yindex[0]
    top = [
        (x, y) for i in xindices[xlen - 1 :: -1] for x in [xdata[i]] for y in ydata[:1]
    ]

    # The last point should already be the same as the first, given that top
    # uses all of the xindices, but just in case...
    if top[-1] != left[0]:
        top.append(left[0])

    # concatenate the "sides" and return the perimeter points
    return left + bottom + right + top


def index_subset(original_length):
    """
    Pluck out the values for the first and last index of an array, plus a
    somewhat arbitrary, and approximately evenly spaced, additional number
    of indices in between the beginning and end.
    """
    if original_length > 6:
        return [
            round(index * count * 0.2)
            for count in range(constants.DEFAULT_SPATIAL_AXIS_SIZE)
            for index in [original_length - 1]
        ]
    else:
        return list(range(original_length))

# if no date modified in netcdf global attributes, then retrieve from configuration
# should errors be added to ledger for summary purposes, or simply plopped into log?
def date_modified(netcdf, configuration):
    datetime_str = netcdf.attrs['date_modified'] if 'date_modified' in netcdf.attrs else configuration.date_modified
    if datetime_str:
        return ensure_iso(datetime_str)

    log_error('No date modified value exists.')

def log_error(err):
    logger = logging.getLogger(constants.ROOT_LOGGER)
    logger.error(err)
    exit(1)

def ensure_iso(datetime_str):
    """
    Parse ISO-standard datetime strings without a timezone identifier.
    """
    iso_obj = parse(datetime_str)
    return (
        iso_obj.replace(tzinfo=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )
