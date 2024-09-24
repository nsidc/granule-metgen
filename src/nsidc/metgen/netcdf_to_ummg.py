import os.path
from cftime import num2date
from datetime import datetime
from netCDF4 import Dataset

# file: full path to netcdf file
# take an input netcdf file and return a structure with temporal coverage
# information, spatial coverage information, file size, and production datetime.
def netcdf_to_ummg(file):
    # Assumptions (may need to make these configurable):
    # - production_date_time is represented by global attribute :date_created
    #   and/or :date_modified
    # - only one coordinate system used by all variables (i.e. only one grid_mapping)
    summary = {}
    summary['size_in_bytes'] = os.path.getsize(file)

    nc = Dataset(file)

    # TODO: handle "AttributeError: NetCDF: Attribute not found" error if attribute
    # doesn't exist.
    summary['production_date_time'] = nc.getncattr('date_modified')

    # TODO: handle error if more than one attribute with the standard name of 'time'
    var = nc.get_variables_by_attributes(standard_name = 'time')[0]

    # If one value, set date_time
    # If multiple time values, first is begin_date_time, last is end_date_time
    d = num2date(var[:], units=var.units, calendar=var.calendar)
    if var.size > 1:
        summary['begin_date_time'] = d[0].isoformat()
        summary['end_date_time'] = d[-1].isoformat()
    else:
        summary['date_time'] = d[0].isoformat()

    # TODO: handle error if more than one grid_mapping
    grid_mapping= nc.get_variables_by_attributes(grid_mapping_name=lambda v: v is not None)
    if len(grid_mapping) > 1:
        summary['geometry'] = {}
    else:
        summary['geometry'] = {'west': 0, 'north': 0, 'east': 0, 'south': 0}

    return summary
