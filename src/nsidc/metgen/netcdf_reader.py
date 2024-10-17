import json
import os.path
import rioxarray
import xarray as xr


def extract_metadata(netcdf_path):
    """
    Read the content at netcdf_path and return a structure with temporal coverage
    information, spatial coverage information, file size, and production datetime.
    """

    # Assumptions (may need to make these configurable):
    # - production_date_time is represented by global attribute date_modified
    # - only one coordinate system used by all variables (i.e. only one grid_mapping)
    # - only one time dimension

    # TODO: handle errors if any needed attributes don't exist.
    netcdf = xr.open_dataset(netcdf_path, use_cftime=True, decode_coords="all")

    return { 
        'size_in_bytes': os.path.getsize(netcdf_path),
        'production_date_time': netcdf.attrs['date_modified'],
        'temporal': time_range(netcdf),
        'geometry': {'points': json.dumps(spatial_values(netcdf))}
    }

def time_range(netcdf):
    """Returns array of datetime strings"""
    datetimes = []

    d = netcdf['time'].data
    datetimes.append(d[0].isoformat())

    if len(d) > 1:
        datetimes.append(d[-1].isoformat())

    return datetimes

def spatial_values(netcdf):
    """
    Returns an array of dicts, each dict representing one lat/lon pair:

        {
            "Longitude: float,
            "Latitude: float
        }
    """

    # Reproject (x,y) meter values to EPSG 4326
    netcdf_lonlat = netcdf.rio.reproject("EPSG:4326")
    londata = netcdf_lonlat['x'].data
    latdata = netcdf_lonlat['y'].data

    # Pull out just the perimeter of the grid, counter-clockwise direction,
    # starting at top left.
    # first x, all y
    left = [(lon,lat) for lon in londata[:1] for lat in latdata[::40]]

    # all x starting at x1, last y
    bottom = [(lon,lat) for lon in londata[::40] for lat in latdata[-1:]]

    # last x, all reverse y starting at yn-1
    right = [(lon,lat) for lon in londata[-1:] for lat in latdata[::-40]]

    # all reverse x starting at xn-1, first y
    # this includes first value again
    top = [(lon,lat) for lon in londata[::-40] for lat in latdata[:1]]

    # concatenate the "sides"
    perimeter = left + bottom + right + top

    return [{'Longitude': round(lon, 8), 'Latitude': round(lat, 8)} for (lon, lat) in perimeter]
