"""Tests for the geometry extractor module."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from nsidc.metgen.geometry_extractor import (
    transform_to_bounding_rectangle,
    transform_to_point,
    transform_to_gpolygon,
    transform_geometry,
)
from nsidc.metgen.geometry_resolver import GeometryType


class TestGeometryTransformations:
    """Test the geometry transformation functions."""

    def test_transform_to_bounding_rectangle(self):
        """Test transforming points to bounding rectangle format."""
        points = [
            {"Longitude": -105.0, "Latitude": 40.0},  # SW corner
            {"Longitude": -104.0, "Latitude": 41.0}   # NE corner
        ]
        
        result = transform_to_bounding_rectangle(points)
        
        assert result["WestBoundingCoordinate"] == -105.0
        assert result["SouthBoundingCoordinate"] == 40.0
        assert result["EastBoundingCoordinate"] == -104.0
        assert result["NorthBoundingCoordinate"] == 41.0

    def test_transform_to_bounding_rectangle_wrong_count(self):
        """Test error when wrong number of points for bounding rectangle."""
        points = [{"Longitude": -105.0, "Latitude": 40.0}]
        
        with pytest.raises(ValueError, match="exactly 2 points"):
            transform_to_bounding_rectangle(points)

    def test_transform_to_point(self):
        """Test transforming to point format."""
        points = [{"Longitude": -105.0, "Latitude": 40.0}]
        
        result = transform_to_point(points)
        
        assert result["Longitude"] == -105.0
        assert result["Latitude"] == 40.0

    def test_transform_to_point_wrong_count(self):
        """Test error when wrong number of points for point."""
        points = [
            {"Longitude": -105.0, "Latitude": 40.0},
            {"Longitude": -104.0, "Latitude": 41.0}
        ]
        
        with pytest.raises(ValueError, match="exactly 1 point"):
            transform_to_point(points)

    def test_transform_to_gpolygon_open(self):
        """Test transforming to GPolygon with open polygon."""
        points = [
            {"Longitude": -105.0, "Latitude": 40.0},
            {"Longitude": -104.0, "Latitude": 40.0},
            {"Longitude": -104.0, "Latitude": 41.0},
            {"Longitude": -105.0, "Latitude": 41.0},
        ]
        
        result = transform_to_gpolygon(points)
        
        # Should close the polygon
        assert len(result) == 5
        assert result[0] == result[-1]
        assert result[0]["Longitude"] == -105.0
        assert result[0]["Latitude"] == 40.0

    def test_transform_to_gpolygon_already_closed(self):
        """Test transforming to GPolygon with already closed polygon."""
        points = [
            {"Longitude": -105.0, "Latitude": 40.0},
            {"Longitude": -104.0, "Latitude": 40.0},
            {"Longitude": -104.0, "Latitude": 41.0},
            {"Longitude": -105.0, "Latitude": 41.0},
            {"Longitude": -105.0, "Latitude": 40.0},  # Already closed
        ]
        
        result = transform_to_gpolygon(points)
        
        # Should not add another closing point
        assert len(result) == 5
        assert result[0] == result[-1]

    def test_transform_to_gpolygon_insufficient_points(self):
        """Test error when insufficient points for GPolygon."""
        points = [
            {"Longitude": -105.0, "Latitude": 40.0},
            {"Longitude": -104.0, "Latitude": 40.0},
            {"Longitude": -104.0, "Latitude": 41.0},
        ]
        
        with pytest.raises(ValueError, match="at least 4 points"):
            transform_to_gpolygon(points)

    def test_transform_geometry_bounding_rectangle(self):
        """Test complete geometry transformation for bounding rectangle."""
        points = [
            {"Longitude": -105.0, "Latitude": 40.0},
            {"Longitude": -104.0, "Latitude": 41.0}
        ]
        
        result = transform_geometry(points, GeometryType.BOUNDING_RECTANGLE)
        
        assert result["type"] == "BoundingRectangle"
        assert "coordinates" in result
        assert result["coordinates"]["WestBoundingCoordinate"] == -105.0

    def test_transform_geometry_point(self):
        """Test complete geometry transformation for point."""
        points = [{"Longitude": -105.0, "Latitude": 40.0}]
        
        result = transform_geometry(points, GeometryType.POINT)
        
        assert result["type"] == "Point"
        assert "coordinates" in result
        assert result["coordinates"]["Longitude"] == -105.0

    def test_transform_geometry_gpolygon(self):
        """Test complete geometry transformation for GPolygon."""
        points = [
            {"Longitude": -105.0, "Latitude": 40.0},
            {"Longitude": -104.0, "Latitude": 40.0},
            {"Longitude": -104.0, "Latitude": 41.0},
            {"Longitude": -105.0, "Latitude": 41.0},
        ]
        
        result = transform_geometry(points, GeometryType.GPOLYGON)
        
        assert result["type"] == "GPolygon"
        assert "coordinates" in result
        assert len(result["coordinates"]) == 5  # Closed polygon