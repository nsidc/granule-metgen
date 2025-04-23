from unittest.mock import mock_open, patch

import pytest
from nsidc.metgen.readers import utilities

# Unit tests for the 'utilities' module functions.
#
# The test boundary is the utilities module's interface with the filesystem
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
    result = utilities.ensure_iso_datetime(input)
    assert result == expected


@pytest.mark.parametrize(
    "input,expected",
    [
        (
            {
                "RangeBeginningDate": "2020-01-01",
                "RangeBeginningTime": "00:00:00",
                "RangeEndingDate": "2020-12-31",
                "RangeEndingTime": "23:59:59",
            },
            ["2020-01-01T00:00:00.000Z", "2020-12-31T23:59:59.000Z"],
        ),
        (
            {
                "RangeBeginningDate": "2020-01-01",
                "RangeBeginningTime": "00:00:00",
            },
            ["2020-01-01T00:00:00.000Z"],
        ),
        (
            {"Begin_date": "2000-01-01", "End_date": "2000-12-31"},
            ["2000-01-01T00:00:00.000Z", "2000-12-31T00:00:00.000Z"],
        ),
        (
            {"Begin_date": "2000-01-01", "Begin_time": "01:00:30"},
            ["2000-01-01T01:00:30.000Z"],
        ),
        (
            {"Begin_date": "2000-01-01"},
            ["2000-01-01T00:00:00.000Z"],
        ),
    ],
)
def test_datetime_from_premet(input, expected):
    with patch("nsidc.metgen.readers.utilities.premet_values", return_value=input):
        vals = utilities.temporal_from_premet("fake_premet_path")
        assert vals == expected


@patch("builtins.open", new_callable=mock_open, read_data="-105.253 40.0126")
def test_reads_points_from_spatial_file(mo):
    assert utilities.points_from_spatial("a_spatial_path") == [
        {"Longitude": -105.253, "Latitude": 40.0126}
    ]
