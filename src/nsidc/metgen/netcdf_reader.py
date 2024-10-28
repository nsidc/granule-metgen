import json
import os.path
import xarray as xr
from datetime import timezone
from dateutil.parser import parse

from pyproj import CRS
from pyproj import Transformer

from nsidc.metgen import constants

def extract_metadata(netcdf_path):
    """
    Read the content at netcdf_path and return a structure with temporal coverage
    information, spatial coverage information, file size, and production datetime.
    """

    # TODO: handle errors if any needed attributes don't exist.
    netcdf = xr.open_dataset(netcdf_path, decode_coords="all")

    return { 
        'size_in_bytes': os.path.getsize(netcdf_path),
        'production_date_time': ensure_iso(netcdf.attrs['date_modified']),
        'temporal': time_range(netcdf),
        'geometry': {'points': json.dumps(spatial_values(netcdf))}
    }

def time_range(netcdf):
    """Return an array of datetime strings"""
    datetimes = []
    datetimes.append(ensure_iso(netcdf.attrs['time_coverage_start']))
    datetimes.append(ensure_iso(netcdf.attrs['time_coverage_end']))

    return datetimes

def spatial_values(netcdf):
    """
    Return an array of dicts, each dict representing one lat/lon pair like so:

        {
            "Longitude: float,
            "Latitude: float
        }
    Eventually this can/should be pulled out of the netCDF-specific code into a
    general-use module.
    """

    data_crs = CRS.from_wkt(netcdf.crs.crs_wkt)
    crs_4326 = CRS.from_epsg(4326)
    xformer = Transformer.from_crs(data_crs, crs_4326, always_xy=True)

    # Adding padding should give us values that match up to the netcdf.attrs.geospatial_bounds
    pad = abs(float(netcdf.crs.GeoTransform.split()[1]))/2
    xdata = [x - pad if x < 0 else x + pad for x in netcdf.x.data]
    ydata = [y - pad if y < 0 else y + pad for y in netcdf.y.data]

    # Extract the perimeter points and transform to lon, lat
    perimeter = [xformer.transform(x, y) for (x, y) in thinned_perimeter(xdata, ydata)]

    return [{'Longitude': round(lon, 8), 'Latitude': round(lat, 8)} for (lon, lat) in perimeter]

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
    left = [(x,y) for x in xdata[:1] for i in yindices[:ylen-1] for y in [ydata[i]]]

    # xindex[0]..xindex[-2], yindex[-1]
    bottom = [(x,y) for i in xindices[:xlen-1] for x in [xdata[i]] for y in ydata[-1:]]

    # xindex[-1], yindex[-1]..yindex[1]
    right = [(x,y) for x in xdata[-1:] for i in yindices[ylen-1:0:-1] for y in [ydata[i]]]

    # xindex[-1]..xindex[0], yindex[0]
    top = [(x,y) for i in xindices[xlen-1::-1] for x in [xdata[i]] for y in ydata[:1]]

    # The last point should already be the same as the first, given that top
    # uses all of the xindices, but just in case...
    if top[-1] != left[0]:
        top.append(left[0])

    # concatenate the "sides" and return the perimeter points
    return(left + bottom + right + top)

def index_subset(original_length):
    """
    Pluck out the values for the first and last index of an array, plus a
    somewhat arbitrary, and approximately evenly spaced, additional number
    of indices in between the beginning and end.
    """
    if(original_length > 6):
        return [round(index*count*.2) for count in range(constants.DEFAULT_SPATIAL_AXIS_SIZE) for index in [original_length - 1]]
    else:
        return list(range(original_length))

def ensure_iso(datetime_str):
    """
    Parse ISO-standard datetime strings without a timezone identifier.
    """
    iso_obj = parse(datetime_str)
    return iso_obj.replace(tzinfo=timezone.utc) \
        .isoformat(timespec='milliseconds') \
        .replace("+00:00", "Z")
