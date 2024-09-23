import os.path
from cftime import num2date
from datetime import datetime
from netCDF4 import Dataset

# file: full path to netcdf file
# take an input netcdf file and return a structure with temporal, spatial, size,
# and production time
def netcdf_to_ummg(file):
    # assumptions (may need to make these configurable):
    # production_date_time is represented by global attribute :date_created
    # and/or :date_modified
    # only one coordinate system used by all variables (only one grid_mapping)
    summary = {}
    summary['size_in_bytes'] = os.path.getsize(file)
    print(f'file size is {summary['size_in_bytes']}')

    nc = Dataset(file)

    # returns AttributeError: NetCDF: Attribute not found if attribute doesn't
    # exist. handle this!
    summary['production_date_time'] = nc.getncattr('date_modified')

    # attrs = nc.ncattrs()
    # returns a list! Use the first one
    # show error if more than one
    var = nc.get_variables_by_attributes(standard_name = 'time')[0]

    print(f'found {var.size} time values')

    # if one value, set date_time
    # if multiple, first is begin_date_time, last is end_date_time
    d = num2date(var[:], units=var.units, calendar=var.calendar)
    if var.size > 1:
        summary['begin_date_time'] = d[0].isoformat()
        summary['end_date_time'] = d[-1].isoformat()
    else:
        summary['date_time'] = d[0].isoformat()

    # returns an array! Expect to be of length 1
    grid_mapping= nc.get_variables_by_attributes(grid_mapping_name=lambda v: v is not None)
    if len(grid_mapping) > 1:
        summary['geometry'] = {}
    else:
        summary['geometry'] = {'west': '', 'north': '', 'east': '', 'south': ''}

    # can also get dimension with:
    # nc.dimensions['time']
    #nc.dimensions['time'].size

    # get all values
    #vals = var[:].data
    #val = var[0].data

    return summary

    # d[0] => cftime.DatetimeGregorian(2022, 4, 15, 0, 0, 0, 0, has_year_zero=False)
    # d[0].isoformat() => '2022-04-15T00:00:00'
    # from cftime import to_tuple
    # >>> to_tuple(d[0])
    # (2022, 4, 15, 0, 0, 0, 0)
