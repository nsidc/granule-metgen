"""Tests for the geometry resolver module."""

import pytest
from pathlib import Path

from nsidc.metgen.geometry_resolver import (
    GeometryContext,
    GeometrySource,
    GeometryType,
    GeometryDecision,
    resolve_geometry,
    validate_geometry_points,
)
from nsidc.metgen.constants import CARTESIAN, GEODETIC


class TestGeometryResolver:
    """Test the geometry resolution logic."""

    def test_spo_cartesian_error(self):
        """Test that SPO files with CARTESIAN GSR produce an error."""
        context = GeometryContext(
            gsr=CARTESIAN,
            collection_geometry_override=False,
            has_spo_file=True,
            has_spatial_file=False,
            has_data_file_geometry=False,
            has_collection_geometry=False,
            point_count=5,
            spo_filename=Path("test.spo"),
        )
        
        decision = resolve_geometry(context)
        
        assert decision.source == GeometrySource.SPO_FILE
        assert decision.geometry_type == GeometryType.GPOLYGON
        assert not decision.is_valid
        assert "cannot be used with CARTESIAN" in decision.error

    def test_spo_geodetic_insufficient_points(self):
        """Test that SPO files with GEODETIC GSR and ≤2 points produce an error."""
        context = GeometryContext(
            gsr=GEODETIC,
            collection_geometry_override=False,
            has_spo_file=True,
            has_spatial_file=False,
            has_data_file_geometry=False,
            has_collection_geometry=False,
            point_count=2,
            spo_filename=Path("test.spo"),
        )
        
        decision = resolve_geometry(context)
        
        assert decision.source == GeometrySource.SPO_FILE
        assert decision.geometry_type == GeometryType.GPOLYGON
        assert not decision.is_valid
        assert "at least 3 points" in decision.error

    def test_spo_geodetic_valid(self):
        """Test that SPO files with GEODETIC GSR and >2 points produce GPolygon."""
        context = GeometryContext(
            gsr=GEODETIC,
            collection_geometry_override=False,
            has_spo_file=True,
            has_spatial_file=False,
            has_data_file_geometry=False,
            has_collection_geometry=False,
            point_count=5,
            spo_filename=Path("test.spo"),
        )
        
        decision = resolve_geometry(context)
        
        assert decision.source == GeometrySource.SPO_FILE
        assert decision.geometry_type == GeometryType.GPOLYGON
        assert decision.is_valid

    def test_spatial_cartesian_valid(self):
        """Test that spatial files with CARTESIAN GSR produce bounding rectangle."""
        context = GeometryContext(
            gsr=CARTESIAN,
            collection_geometry_override=False,
            has_spo_file=False,
            has_spatial_file=True,
            has_data_file_geometry=False,
            has_collection_geometry=False,
            point_count=2,
            spatial_filename=Path("test.spatial"),
        )
        
        decision = resolve_geometry(context)
        
        assert decision.source == GeometrySource.SPATIAL_FILE
        assert decision.geometry_type == GeometryType.BOUNDING_RECTANGLE
        assert decision.is_valid

    def test_spatial_cartesian_wrong_points(self):
        """Test that spatial files with CARTESIAN GSR and wrong point count error."""
        context = GeometryContext(
            gsr=CARTESIAN,
            collection_geometry_override=False,
            has_spo_file=False,
            has_spatial_file=True,
            has_data_file_geometry=False,
            has_collection_geometry=False,
            point_count=3,
            spatial_filename=Path("test.spatial"),
        )
        
        decision = resolve_geometry(context)
        
        assert decision.source == GeometrySource.SPATIAL_FILE
        assert decision.geometry_type == GeometryType.BOUNDING_RECTANGLE
        assert not decision.is_valid
        assert "exactly 2 points" in decision.error

    def test_spatial_geodetic_single_point(self):
        """Test that spatial files with GEODETIC GSR and 1 point produce Point."""
        context = GeometryContext(
            gsr=GEODETIC,
            collection_geometry_override=False,
            has_spo_file=False,
            has_spatial_file=True,
            has_data_file_geometry=False,
            has_collection_geometry=False,
            point_count=1,
            spatial_filename=Path("test.spatial"),
        )
        
        decision = resolve_geometry(context)
        
        assert decision.source == GeometrySource.SPATIAL_FILE
        assert decision.geometry_type == GeometryType.POINT
        assert decision.is_valid

    def test_spatial_geodetic_multiple_points(self):
        """Test that spatial files with GEODETIC GSR and >1 point produce GPolygon."""
        context = GeometryContext(
            gsr=GEODETIC,
            collection_geometry_override=False,
            has_spo_file=False,
            has_spatial_file=True,
            has_data_file_geometry=False,
            has_collection_geometry=False,
            point_count=4,
            spatial_filename=Path("test.spatial"),
        )
        
        decision = resolve_geometry(context)
        
        assert decision.source == GeometrySource.SPATIAL_FILE
        assert decision.geometry_type == GeometryType.GPOLYGON
        assert decision.is_valid

    def test_collection_override_priority(self):
        """Test that collection override takes priority over other sources."""
        context = GeometryContext(
            gsr=CARTESIAN,
            collection_geometry_override=True,
            has_spo_file=True,  # This would normally be used
            has_spatial_file=True,  # This would normally be used
            has_data_file_geometry=True,
            has_collection_geometry=True,
            point_count=5,
        )
        
        decision = resolve_geometry(context)
        
        assert decision.source == GeometrySource.COLLECTION
        assert decision.geometry_type == GeometryType.BOUNDING_RECTANGLE
        assert decision.is_valid

    def test_collection_override_geodetic_error(self):
        """Test that collection override with GEODETIC GSR produces error."""
        context = GeometryContext(
            gsr=GEODETIC,
            collection_geometry_override=True,
            has_spo_file=False,
            has_spatial_file=False,
            has_data_file_geometry=False,
            has_collection_geometry=True,
        )
        
        decision = resolve_geometry(context)
        
        assert decision.source == GeometrySource.COLLECTION
        assert decision.geometry_type == GeometryType.BOUNDING_RECTANGLE
        assert not decision.is_valid
        assert "only supports CARTESIAN" in decision.error

    def test_data_file_fallback(self):
        """Test that data files are used when no sidecar files exist."""
        context = GeometryContext(
            gsr=CARTESIAN,
            collection_geometry_override=False,
            has_spo_file=False,
            has_spatial_file=False,
            has_data_file_geometry=True,
            has_collection_geometry=False,
        )
        
        decision = resolve_geometry(context)
        
        assert decision.source == GeometrySource.DATA_FILE
        assert decision.geometry_type == GeometryType.BOUNDING_RECTANGLE
        assert decision.is_valid

    def test_collection_final_fallback(self):
        """Test that collection is used as final fallback for CARTESIAN."""
        context = GeometryContext(
            gsr=CARTESIAN,
            collection_geometry_override=False,
            has_spo_file=False,
            has_spatial_file=False,
            has_data_file_geometry=False,
            has_collection_geometry=True,
        )
        
        decision = resolve_geometry(context)
        
        assert decision.source == GeometrySource.COLLECTION
        assert decision.geometry_type == GeometryType.BOUNDING_RECTANGLE
        assert decision.is_valid

    def test_no_geometry_available(self):
        """Test error when no geometry source is available."""
        context = GeometryContext(
            gsr=GEODETIC,
            collection_geometry_override=False,
            has_spo_file=False,
            has_spatial_file=False,
            has_data_file_geometry=False,
            has_collection_geometry=False,
        )
        
        decision = resolve_geometry(context)
        
        assert decision.source == GeometrySource.NONE
        assert not decision.is_valid
        assert "No valid geometry source" in decision.error


class TestGeometryValidation:
    """Test the geometry validation logic."""

    def test_validate_point_valid(self):
        """Test valid point geometry."""
        points = [{"Longitude": -105.0, "Latitude": 40.0}]
        is_valid, error = validate_geometry_points(points, GeometryType.POINT, GEODETIC)
        
        assert is_valid
        assert error is None

    def test_validate_point_wrong_count(self):
        """Test point with wrong number of points."""
        points = [
            {"Longitude": -105.0, "Latitude": 40.0},
            {"Longitude": -104.0, "Latitude": 41.0}
        ]
        is_valid, error = validate_geometry_points(points, GeometryType.POINT, GEODETIC)
        
        assert not is_valid
        assert "exactly 1 point" in error

    def test_validate_point_wrong_gsr(self):
        """Test point with wrong GSR."""
        points = [{"Longitude": -105.0, "Latitude": 40.0}]
        is_valid, error = validate_geometry_points(points, GeometryType.POINT, CARTESIAN)
        
        assert not is_valid
        assert "only valid for GEODETIC" in error

    def test_validate_bounding_rectangle_valid(self):
        """Test valid bounding rectangle."""
        points = [
            {"Longitude": -105.0, "Latitude": 40.0},
            {"Longitude": -104.0, "Latitude": 41.0}
        ]
        is_valid, error = validate_geometry_points(points, GeometryType.BOUNDING_RECTANGLE, CARTESIAN)
        
        assert is_valid
        assert error is None

    def test_validate_bounding_rectangle_wrong_count(self):
        """Test bounding rectangle with wrong number of points."""
        points = [{"Longitude": -105.0, "Latitude": 40.0}]
        is_valid, error = validate_geometry_points(points, GeometryType.BOUNDING_RECTANGLE, CARTESIAN)
        
        assert not is_valid
        assert "exactly 2 points" in error

    def test_validate_gpolygon_valid(self):
        """Test valid GPolygon."""
        points = [
            {"Longitude": -105.0, "Latitude": 40.0},
            {"Longitude": -104.0, "Latitude": 40.0},
            {"Longitude": -104.0, "Latitude": 41.0},
            {"Longitude": -105.0, "Latitude": 41.0},
            {"Longitude": -105.0, "Latitude": 40.0},  # Closed
        ]
        is_valid, error = validate_geometry_points(points, GeometryType.GPOLYGON, GEODETIC)
        
        assert is_valid
        assert error is None

    def test_validate_gpolygon_too_few_points(self):
        """Test GPolygon with too few points."""
        points = [
            {"Longitude": -105.0, "Latitude": 40.0},
            {"Longitude": -104.0, "Latitude": 40.0},
            {"Longitude": -104.0, "Latitude": 41.0},
        ]
        is_valid, error = validate_geometry_points(points, GeometryType.GPOLYGON, GEODETIC)
        
        assert not is_valid
        assert "at least 4 points" in error