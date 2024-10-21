import json
import os.path
import xarray as xr
from pyproj import CRS
from pyproj import Transformer


def extract_metadata(netcdf_path):
    """
    Read the content at netcdf_path and return a structure with temporal coverage
    information, spatial coverage information, file size, and production datetime.

    Current assumptions (these may eventually need to be configured in the .ini file):
    - The global attribute "date_modified" exists and will be used to represent
      the production date and time.
    - Global attributes "time_coverage_start" and "time_coverage_end" exist and
      will be used for the time range metadata values.
    - Only one coordinate system is used by all variables (i.e. only one grid_mapping)
    - x,y coordinates represent the center of the pixel. The pixel size in the
      GeoTransform attribute is used to determine the padding added to x and y values.
    """

    # TODO: handle errors if any needed attributes don't exist.
    netcdf = xr.open_dataset(netcdf_path, decode_coords="all")

    return { 
        'size_in_bytes': os.path.getsize(netcdf_path),
        # time needs to be iso string
        'production_date_time': netcdf.attrs['date_modified'],
        'temporal': time_range(netcdf),
        'geometry': {'points': json.dumps(spatial_values(netcdf))}
    }

def time_range(netcdf):
    """Returns array of datetime strings"""
    datetimes = []
    datetimes.append(netcdf.attrs['time_coverage_start'])
    datetimes.append(netcdf.attrs['time_coverage_end'])

    # show in isoformat

    return datetimes

def spatial_values(netcdf):
    """
    Returns an array of dicts, each dict representing one lat/lon pair:

        {
            "Longitude: float,
            "Latitude: float
        }
    """

    data_crs = CRS.from_wkt(netcdf.crs.crs_wkt)
    crs_4326 = CRS.from_epsg(4326)
    xformer = Transformer.from_crs(data_crs,crs_4326, always_xy=True)

    # Adding padding should give us values that match up to the netcdf.attrs.geospatial_bounds
    pad = abs(float(netcdf.crs.GeoTransform.split()[1]))/2
    xdata = list(map(lambda x: x - pad if x < 0 else x + pad, netcdf.x.data))
    ydata = list(map(lambda y: y - pad if y < 0 else y + pad, netcdf.y.data))

    # Generate a gap between values that will give us four points per side of
    # the polygon.
    xgap = round(len(xdata)/5)
    ygap = round(len(ydata)/5)

    # Pull out just the perimeter of the grid, counter-clockwise direction,
    # starting at top left.
    # x0, y0..yn-gap
    left = [(x,y) for x in xdata[:1] for y in ydata[:-5:ygap]]

    # x0..xn-gap, yn
    bottom = [(x,y) for x in xdata[:-5:xgap] for y in ydata[-1:]]

    # xn, yn..y0
    right = [(x,y) for x in xdata[-1:] for y in ydata[:5:-ygap]]

    # xn..x0, first y
    top = [(x,y) for x in xdata[:5:-xgap] for y in ydata[:1]]

    if top[-1] != left[0]:
        top.append(left[0])

    # concatenate the "sides" and transform to lon, lat
    perimeter = list(map(lambda xy: xformer.transform(xy[0], xy[1]), left + bottom + right + top))

    return [{'Longitude': round(lon, 8), 'Latitude': round(lat, 8)} for (lon, lat) in perimeter]
