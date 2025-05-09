import re
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


@pytest.fixture
def open_polygon():
    return [{"lat": 40, "lon": 100}, {"lat": 45, "lon": 105}, {"lat": 50, "lon": 110}]


@pytest.fixture
def closed_polygon():
    return [
        {"lat": 40, "lon": 100},
        {"lat": 45, "lon": 105},
        {"lat": 50, "lon": 110},
        {"lat": 40, "lon": 100},
    ]


@pytest.fixture
def not_a_polygon():
    return [{"lat": 40, "lon": 100}, {"lat": 45, "lon": 105}]


@pytest.mark.parametrize(
    "input,expected",
    [
        ("akey = somevalue", ["akey", "somevalue"]),
        ("adate =   2020-01-01", ["adate", "2020-01-01"]),
        ("alat=74.5", ["alat", "74.5"]),
        ("alon  =100", ["alon", "100"]),
    ],
)
def test_parse_premet_ignores_whitespace(input, expected):
    assert utilities.parse_premet_entry(input) == expected


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
    assert utilities.temporal_from_premet(input) == expected


def test_one_additional_attribute():
    premet_content = utilities.premet_values("./fixtures/premet/one_attribute.premet")
    assert premet_content["AdditionalAttributes"] == [
        {"Name": "first_attribute", "Values": ["first_value"]}
    ]


def test_two_additional_attributes():
    premet_content = utilities.premet_values("./fixtures/premet/two_attributes.premet")
    assert {"Name": "first_attribute", "Values": ["first_value"]} in premet_content[
        "AdditionalAttributes"
    ]
    assert {"Name": "second_attribute", "Values": ["second_value"]} in premet_content[
        "AdditionalAttributes"
    ]
    assert len(premet_content["AdditionalAttributes"]) == 2


@patch("builtins.open", new_callable=mock_open, read_data="-105.253 40.0126")
def test_reads_raw_points(mock):
    assert utilities.raw_points("a_spatial_path") == [
        {"Longitude": -105.253, "Latitude": 40.0126}
    ]


def test_empty_lonlat_file():
    assert utilities.raw_points("./fixtures/spatial/empty.spatial") == []


def test_error_if_no_filename():
    with pytest.raises(Exception) as exc_info:
        utilities.points_from_spatial("")
    assert re.search("spatial_dir is specified but no", exc_info.value.args[0])


def test_reverses_closed_spo_points():
    lonlats = utilities.raw_points("./fixtures/spatial/closed.spo")
    spo_lonlats = utilities.parse_spo("./fixtures/spatial/closed.spo")
    assert lonlats[1] == spo_lonlats[-2]


def test_reverses_open_spo_points():
    lonlats = utilities.raw_points("./fixtures/spatial/open.spo")
    spo_lonlats = utilities.parse_spo("./fixtures/spatial/open.spo")
    assert lonlats[1] == spo_lonlats[-2]
    assert len(lonlats) == len(spo_lonlats) - 1


def test_closes_open_polygon(open_polygon):
    closed_lonlats = utilities.closed_polygon(open_polygon)
    assert (len(closed_lonlats)) == len(open_polygon) + 1


def test_accepts_closed_polygon(closed_polygon):
    closed_lonlats = utilities.closed_polygon(closed_polygon)
    assert (len(closed_lonlats)) == len(closed_polygon)


def test_ignores_tiny_spo(not_a_polygon):
    assert utilities.closed_polygon(not_a_polygon) == not_a_polygon
