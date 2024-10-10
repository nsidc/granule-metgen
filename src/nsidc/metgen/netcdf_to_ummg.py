import os.path
import netCDF4
import numpy as np
import pandas as pd
import xarray as xr

# file: full path to netcdf file
# take an input netcdf file and return a structure with temporal coverage
# information, spatial coverage information, file size, and production datetime.
def extract_metadata(file):
    # Assumptions (may need to make these configurable):
    # - production_date_time is represented by global attribute date_modified
    # - only one coordinate system used by all variables (i.e. only one grid_mapping)
    # - only one time dimension
    summary = { 'size_in_bytes': os.path.getsize(file) }

    nc = xr.open_dataset(file, use_cftime=True)

    # TODO: handle error if more than one attribute with the standard name of 'time'
    # or more than one grid_mapping
    # TODO: handle "AttributeError: NetCDF: Attribute not found" error if any
    # needed attributes don't exist.
    summary['production_date_time'] = nc.attrs('date_modified')

    # If one value, set date_time
    # If multiple time values, first is begin_date_time, last is end_date_time
    d = nc['time'].data[0].isoformat()
    if len(nc['time']) > 1:
        summary['begin_date_time'] = d[0].isoformat()
        summary['end_date_time'] = d[-1].isoformat()
    else:
        summary['date_time'] = d[0].isoformat()

    geo = geometry(nc)



def geometry(nc_filehandle):
    #if len(grid_mapping) > 1:
    #    return {}
    #else:
    #    return({'west': 0, 'north': 0, 'east': 0, 'south': 0})

    # TODO: handle error if more than one grid_mapping
    grid_mapping= filehandle.get_variables_by_attributes(grid_mapping_name=lambda v: v is not None)
    xdata = nc_filehandle['x'].data
    ydata = nc_filehandle['y'].data
    # all x, first y
    top = [(x,y) for x in xdata[::20] for y in ydata[:1]]
    # right x, all y
    right = [(x,y) for x in xdata[-1:] for y in ydata[::20]]
    # all reverse x, last y
    bottom = [(x,y) for x in xdata[::-20] for y in ydata[-1:]]
    # first x, all reverse y
    left = [(x,y) for x in xdata[:1] for y in ydata[::-20]]
    # concatenate and add first element again at end
    #total length is len(top) + len(right) + len(bottom) + len(left) + 1
    perimeter = top + right + bottom + left + top[0:1]
