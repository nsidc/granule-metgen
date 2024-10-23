import json
import os.path
import xarray as xr
import re
from datetime import datetime, timezone

from pyproj import CRS
from pyproj import Transformer


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
    xdata = list(map(lambda x: x - pad if x < 0 else x + pad, netcdf.x.data))
    ydata = list(map(lambda y: y - pad if y < 0 else y + pad, netcdf.y.data))

    # Generate a gap between points that will give us four points per side of
    # the polygon (plus the corners).
    xgap = round(len(xdata)/5)
    ygap = round(len(ydata)/5)

    # Pull out just the perimeter of the grid, counter-clockwise direction,
    # starting at top left.
    # x0, y0..yn-ygap
    left = [(x,y) for x in xdata[:1] for y in ydata[:-5:ygap]]

    # x0..xn-xgap, yn
    bottom = [(x,y) for x in xdata[:-5:xgap] for y in ydata[-1:]]

    # xn, yn..y0-ygap
    right = [(x,y) for x in xdata[-1:] for y in ydata[:5:-ygap]]

    # xn..x0, first y
    top = [(x,y) for x in xdata[:5:-xgap] for y in ydata[:1]]

    if top[-1] != left[0]:
        top.append(left[0])

    # concatenate the "sides" and transform to lon, lat
    perimeter = list(map(lambda xy: xformer.transform(xy[0], xy[1]), left + bottom + right + top))

    return [{'Longitude': round(lon, 8), 'Latitude': round(lat, 8)} for (lon, lat) in perimeter]

def ensure_iso(datetime_str):
    """
    Reformat time values like "23:59.99" to "23:59:59.99". Fractional minutes are
    valid ISO, but not handled by Python's built-in datetime.fromisoformat() class
    method. We could also use datetime.strptime() but that approach also requires
    some assumptions.
    """
    iso_obj = datetime.fromisoformat(datetime_str)
    fractional_minutes = re.match(r'[^\s]* (?P<hour>\d{2}):(?P<min>\d*)\.(?P<fraction>\d*)', datetime_str)
    sec = 59 if fractional_minutes and \
        fractional_minutes.group('min') == '59' and \
        fractional_minutes.group('fraction') >= '99' \
        else iso_obj.second

    return(iso_obj.replace(second=sec, tzinfo=timezone.utc).isoformat())
