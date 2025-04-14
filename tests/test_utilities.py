import pytest
from nsidc.metgen.readers import utilities

# Unit tests for the 'utilities' module functions.
#
# The test boundary is the netcdf_reader module's interface with the filesystem
# so in addition to testing the netcdf_reader module's behavior, the tests
# should mock those module's functions and assert that netcdf_reader functions
# call them with the correct parameters, correctly handle their return values,
# and handle any exceptions they may throw.


@pytest.mark.parametrize(
    "input,expected",
    [
        pytest.param("2001-01-01", "2001-01-01T00:00:00.000Z", id="Date and no time"),
        pytest.param(
            "2001-01-01 18:59:59", "2001-01-01T18:59:59.000Z", id="Date with time"
        ),
        pytest.param(
            "2001-01-01 18:59.5",
            "2001-01-01T18:59:30.000Z",
            id="Datetime and fractional minutes",
        ),
        pytest.param(
            "2001-01-01 18:59.500",
            "2001-01-01T18:59:30.000Z",
            id="Datetime and zero padded fractional minutes",
        ),
        pytest.param(
            "2001-01-01 18:59.34",
            "2001-01-01T18:59:20.000Z",
            id="Datetime and other fractional minutes value",
        ),
        pytest.param(
            "2001-01-01 18:59.999",
            "2001-01-01T18:59:59.000Z",
            id="Datetime and other fractional minutes value",
        ),
        pytest.param(
            "2001-01-01 18:59:20.666",
            "2001-01-01T18:59:20.666Z",
            id="Datetime and fractional seconds",
        ),
        pytest.param(
            "2001-01-01 18:59",
            "2001-01-01T18:59:00.000Z",
            id="Datetime and hours/minutes",
        ),
    ],
)
def test_correctly_reads_date_time_strings(input, expected):
    result = utilities.ensure_iso(input)
    assert result == expected
