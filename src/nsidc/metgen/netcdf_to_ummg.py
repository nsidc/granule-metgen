import json
import os.path
import xarray as xr

from nsidc.metgen import constants

# Read the content at netcdf_path and return a structure with temporal coverage
# information, spatial coverage information, file size, and production datetime.
def extract_metadata(netcdf_path):
    # Assumptions (may need to make these configurable):
    # - production_date_time is represented by global attribute date_modified
    # - only one coordinate system used by all variables (i.e. only one grid_mapping)
    # - only one time dimension

    # TODO: handle "AttributeError: NetCDF: Attribute not found" error if any
    # needed attributes don't exist.
    netcdf = xr.open_dataset(netcdf_path, use_cftime=True, decode_coords="all")

    summary = { 'size_in_bytes': os.path.getsize(netcdf_path) }
    summary['production_date_time'] = netcdf.attrs['date_modified']

    # Time coverage for data
    summary |= time_range(netcdf)

    # spatial coverage
    summary['geometry'] = {'points': json.dumps(spatial_values(netcdf))}

    return summary

# TODO: handle error if more than one attribute with the standard name of 'time'
def time_range(netcdf):
    summary = {}

    # If one value, set date_time
    # If multiple time values, first is begin_date_time, last is end_date_time
    d = netcdf['time'].data
    if len(d) > 1:
        summary['begin_date_time'] = d[0].isoformat()
        summary['end_date_time'] = d[-1].isoformat()
    else:
        summary['date_time'] = d[0].isoformat()

    return summary

def spatial_values(netcdf):
    # Reproject (x,y) meter values to EPSG 4326
    netcdf_lonlat = netcdf.rio.reproject("EPSG:4326")
    londata = netcdf_lonlat['x'].data
    latdata = netcdf_lonlat['y'].data

    # Pull out just the perimeter of the grid, counter-clockwise direction,
    # starting at top left.
    # first x, all y
    left = [(lon,lat) for lon in londata[:1] for lat in latdata[::40]]

    # all x, last y
    bottom = [(lon,lat) for lon in londata[::40] for lat in latdata[-1:]]

    # last x, all reverse y
    right = [(lon,lat) for lon in londata[-1:] for lat in latdata[::-40]]

    # all reverse x, first y
    top = [(lon,lat) for lon in londata[::-40] for lat in latdata[:1]]

    # concatenate and add first element again at end
    perimeter = left + bottom + right + top + left[0:1]

    return [{'Longitude': lon, 'Latitude': lat} for (lon, lat) in perimeter]
