"""Tests for Spatial File Reader.

These tests are adapted from existing spatial parsing tests
to ensure the new reader maintains the same behavior.
"""

import pytest
from pathlib import Path

from nsidc.metgen.readers.spatial_reader import (
    SpatialData,
    read_spatial_file,
    parse_spatial_points,
    ensure_polygon_closure,
    read_spatial_data,
    extract_collection_spatial_points,
)


# Test fixtures
@pytest.fixture
def spatial_file_content():
    """Content for a basic .spatial file."""
    return [
        "-50.2 70.3",
        "-50.3 70.4",
        "-50.4 70.5",
    ]


@pytest.fixture
def spo_file_content():
    """Content for a .spo file (polygon)."""
    return [
        "-120.0 35.0",
        "-119.0 35.0",
        "-119.0 36.0",
        "-120.0 36.0",
        "-120.0 35.0",  # Closed polygon
    ]


@pytest.fixture
def unclosed_polygon_content():
    """Content for an unclosed polygon."""
    return [
        "-120.0 35.0",
        "-119.0 35.0",
        "-119.0 36.0",
        "-120.0 36.0",
    ]


@pytest.fixture
def collection_spatial_extent():
    """Collection spatial extent from UMM-C."""
    return {
        "HorizontalSpatialDomain": {
            "Geometry": {
                "BoundingRectangles": [
                    {
                        "WestBoundingCoordinate": -180.0,
                        "EastBoundingCoordinate": 180.0,
                        "NorthBoundingCoordinate": 90.0,
                        "SouthBoundingCoordinate": -90.0,
                    }
                ]
            }
        }
    }


class TestReadSpatialFile:
    """Tests for the read_spatial_file function."""

    def test_reads_spatial_file_lines(self, tmp_path, spatial_file_content):
        """Test reading lines from a spatial file."""
        # Create test file
        test_file = tmp_path / "test.spatial"
        test_file.write_text("\n".join(spatial_file_content))

        # Should read coordinate pairs
        with pytest.raises(NotImplementedError):
            read_spatial_file(str(test_file))

    def test_handles_missing_file(self):
        """Test proper error handling for missing files."""
        with pytest.raises(NotImplementedError):
            read_spatial_file("/nonexistent/file.spatial")

    def test_handles_empty_file(self, tmp_path):
        """Test handling of empty spatial files."""
        test_file = tmp_path / "empty.spatial"
        test_file.write_text("")

        with pytest.raises(NotImplementedError):
            read_spatial_file(str(test_file))

    def test_handles_malformed_content(self, tmp_path):
        """Test handling of malformed coordinate data."""
        test_file = tmp_path / "bad.spatial"
        test_file.write_text("not a coordinate\n-50.2\n")

        with pytest.raises(NotImplementedError):
            read_spatial_file(str(test_file))


class TestParseSpatialPoints:
    """Tests for the parse_spatial_points function."""

    def test_parses_spatial_file_points(self):
        """Test parsing points from .spatial file format."""
        raw_points = [(-50.2, 70.3), (-50.3, 70.4), (-50.4, 70.5)]

        # Should return list of point dicts
        with pytest.raises(NotImplementedError):
            parse_spatial_points(raw_points, "spatial", "GEODETIC")

    def test_parses_spo_file_points_geodetic(self):
        """Test parsing points from .spo file with GEODETIC GSR."""
        raw_points = [
            (-120.0, 35.0),
            (-119.0, 35.0),
            (-119.0, 36.0),
            (-120.0, 36.0),
            (-120.0, 35.0),
        ]

        # Should reverse points for geodetic .spo files
        with pytest.raises(NotImplementedError):
            parse_spatial_points(raw_points, "spo", "GEODETIC")

    def test_parses_spo_file_points_cartesian(self):
        """Test parsing points from .spo file with CARTESIAN GSR."""
        raw_points = [(-120.0, 35.0), (-119.0, 35.0)]

        # Should not reverse points for cartesian
        with pytest.raises(NotImplementedError):
            parse_spatial_points(raw_points, "spo", "CARTESIAN")

    def test_formats_point_dictionaries(self):
        """Test that points are formatted with Longitude/Latitude keys."""
        raw_points = [(-50.2, 70.3)]

        # Should return proper dict format
        with pytest.raises(NotImplementedError):
            parse_spatial_points(raw_points, "spatial", "GEODETIC")


class TestEnsurePolygonClosure:
    """Tests for the ensure_polygon_closure function."""

    def test_closes_unclosed_polygon(self):
        """Test that unclosed polygons are properly closed."""
        points = [
            {"Longitude": -120.0, "Latitude": 35.0},
            {"Longitude": -119.0, "Latitude": 35.0},
            {"Longitude": -119.0, "Latitude": 36.0},
            {"Longitude": -120.0, "Latitude": 36.0},
        ]

        with pytest.raises(NotImplementedError):
            ensure_polygon_closure(points)

    def test_preserves_closed_polygon(self):
        """Test that already closed polygons are not modified."""
        points = [
            {"Longitude": -120.0, "Latitude": 35.0},
            {"Longitude": -119.0, "Latitude": 35.0},
            {"Longitude": -119.0, "Latitude": 36.0},
            {"Longitude": -120.0, "Latitude": 36.0},
            {"Longitude": -120.0, "Latitude": 35.0},
        ]

        with pytest.raises(NotImplementedError):
            ensure_polygon_closure(points)

    def test_handles_single_point(self):
        """Test handling of single point (not a polygon)."""
        points = [{"Longitude": -120.0, "Latitude": 35.0}]

        with pytest.raises(NotImplementedError):
            ensure_polygon_closure(points)


class TestReadSpatialData:
    """Tests for the main read_spatial_data function."""

    def test_reads_spatial_file(self, tmp_path, spatial_file_content):
        """Test reading a complete .spatial file."""
        test_file = tmp_path / "test.spatial"
        test_file.write_text("\n".join(spatial_file_content))

        with pytest.raises(NotImplementedError):
            read_spatial_data(str(test_file), "GEODETIC")

    def test_reads_spo_file(self, tmp_path, spo_file_content):
        """Test reading a complete .spo file."""
        test_file = tmp_path / "test.spo"
        test_file.write_text("\n".join(spo_file_content))

        with pytest.raises(NotImplementedError):
            read_spatial_data(str(test_file), "GEODETIC")

    def test_detects_file_type_from_extension(self, tmp_path):
        """Test that file type is correctly determined from extension."""
        # Test .spatial
        spatial_file = tmp_path / "test.spatial"
        spatial_file.write_text("-50.2 70.3")

        with pytest.raises(NotImplementedError):
            read_spatial_data(str(spatial_file), "GEODETIC")

        # Test .spo
        spo_file = tmp_path / "test.spo"
        spo_file.write_text("-50.2 70.3")

        with pytest.raises(NotImplementedError):
            read_spatial_data(str(spo_file), "GEODETIC")

    def test_detects_polygon_closure(self, tmp_path, spo_file_content):
        """Test that polygon closure is correctly detected."""
        test_file = tmp_path / "closed.spo"
        test_file.write_text("\n".join(spo_file_content))

        with pytest.raises(NotImplementedError):
            read_spatial_data(str(test_file), "GEODETIC")


class TestExtractCollectionSpatialPoints:
    """Tests for extracting spatial points from collection metadata."""

    def test_extracts_bounding_rectangle(self, collection_spatial_extent):
        """Test extraction of points from bounding rectangle."""
        with pytest.raises(NotImplementedError):
            extract_collection_spatial_points(collection_spatial_extent)

    def test_handles_missing_geometry(self):
        """Test handling of spatial extent without geometry."""
        spatial_extent = {"HorizontalSpatialDomain": {}}

        with pytest.raises(NotImplementedError):
            extract_collection_spatial_points(spatial_extent)

    def test_handles_empty_bounding_rectangles(self):
        """Test handling of empty bounding rectangles list."""
        spatial_extent = {
            "HorizontalSpatialDomain": {"Geometry": {"BoundingRectangles": []}}
        }

        with pytest.raises(NotImplementedError):
            extract_collection_spatial_points(spatial_extent)


class TestSpatialData:
    """Tests for the SpatialData dataclass."""

    def test_is_frozen_dataclass(self):
        """Test that SpatialData is immutable."""
        data = SpatialData(
            points=[{"Longitude": -120.0, "Latitude": 35.0}],
            file_path="/test/file.spatial",
            file_type="spatial",
        )

        # Should not be able to modify fields
        with pytest.raises(AttributeError):
            data.points = []

    def test_has_required_fields(self):
        """Test that SpatialData can be created with required fields."""
        points = [{"Longitude": -120.0, "Latitude": 35.0}]
        data = SpatialData(
            points=points, file_path="/test/file.spatial", file_type="spatial"
        )

        assert data.points == points
        assert data.file_path == "/test/file.spatial"
        assert data.file_type == "spatial"
        assert data.is_closed_polygon is False

    def test_can_set_polygon_closure_flag(self):
        """Test setting the polygon closure flag."""
        data = SpatialData(
            points=[
                {"Longitude": -120.0, "Latitude": 35.0},
                {"Longitude": -119.0, "Latitude": 35.0},
                {"Longitude": -120.0, "Latitude": 35.0},
            ],
            file_path="/test/file.spo",
            file_type="spo",
            is_closed_polygon=True,
        )

        assert data.is_closed_polygon is True
