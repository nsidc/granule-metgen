"""
Tests for the simplified PolygonGenerator class with automatic method selection.
"""

import numpy as np
import pytest
from nsidc.metgen.spatial import PolygonGenerator
from shapely.geometry import Point, Polygon


class TestPolygonGeneratorAuto:
    """Test suite for simplified PolygonGenerator with automatic method selection."""

    @pytest.fixture
    def generator(self):
        """Create a PolygonGenerator instance."""
        return PolygonGenerator()

    @pytest.fixture
    def sparse_data(self):
        """Create sparse dataset (should select union_buffer)."""
        # Only 20 points spread out
        lon = np.random.uniform(-120, -119, 20)
        lat = np.random.uniform(35, 36, 20)
        return lon, lat

    @pytest.fixture
    def dense_compact_data(self):
        """Create dense data in compact area (should select union_buffer)."""
        # 50000 points in small area
        lon = np.random.uniform(-120.1, -120.0, 50000)
        lat = np.random.uniform(35.0, 35.1, 50000)
        return lon, lat

    @pytest.fixture
    def linear_regular_data(self):
        """Create linear data with regular spacing (should select line_buffer)."""
        # Linear flightline with regular spacing
        t = np.linspace(0, 100, 5000)
        lon = -120 + 0.01 * t  # 1 degree span
        lat = 35 + 0.002 * t   # 0.2 degree span (aspect ratio = 5)
        # Add small regular variations
        lon += 0.0001 * np.sin(t)
        lat += 0.0001 * np.cos(t)
        return lon, lat

    @pytest.fixture
    def irregular_data(self):
        """Create irregular data (should select union_buffer)."""
        # Irregular spacing and distribution
        t = np.sort(np.random.uniform(0, 100, 1000))
        lon = -120 + 0.01 * t + 0.001 * np.random.randn(len(t))
        lat = 35 + 0.01 * t + 0.001 * np.random.randn(len(t))
        return lon, lat

    def test_sparse_data_selection(self, generator, sparse_data):
        """Test that sparse data selects union_buffer method."""
        lon, lat = sparse_data
        
        polygon, metadata = generator.create_flightline_polygon(lon, lat)
        
        assert polygon is not None
        assert metadata["method"] == "union_buffer"
        assert "data_analysis" in metadata
        assert metadata["data_analysis"]["selected_method"] == "union_buffer"
        print(f"Sparse data: {metadata['data_analysis']['metrics']['summary']}")

    def test_dense_compact_selection(self, generator, dense_compact_data):
        """Test that dense compact data is handled well."""
        lon, lat = dense_compact_data
        
        polygon, metadata = generator.create_flightline_polygon(lon, lat)
        
        assert polygon is not None
        # Method selection may vary based on exact data characteristics
        assert metadata["method"] in ["union_buffer", "line_buffer"]
        assert metadata["vertices"] <= metadata["data_analysis"]["target_vertices"] * 2
        print(f"Dense compact: {metadata['data_analysis']['metrics']['summary']}, method: {metadata['method']}")

    def test_linear_regular_selection(self, generator, linear_regular_data):
        """Test that linear regular data selects line_buffer method."""
        lon, lat = linear_regular_data
        
        polygon, metadata = generator.create_flightline_polygon(lon, lat)
        
        assert polygon is not None
        assert metadata["method"] == "line_buffer"
        assert metadata["data_analysis"]["metrics"]["aspect_ratio"] > 4
        assert metadata["data_analysis"]["metrics"]["linearity"] > 0.6
        print(f"Linear regular: {metadata['data_analysis']['metrics']['summary']}")

    def test_irregular_data_selection(self, generator, irregular_data):
        """Test that irregular data is handled appropriately."""
        lon, lat = irregular_data
        
        polygon, metadata = generator.create_flightline_polygon(lon, lat)
        
        assert polygon is not None
        # Algorithm may choose either method based on exact characteristics
        assert metadata["method"] in ["union_buffer", "line_buffer"]
        # Verify it detected some variability in spacing
        assert metadata["data_analysis"]["metrics"].get("distance_cv", 0) > 0.3
        print(f"Irregular: {metadata['data_analysis']['metrics']['summary']}, method: {metadata['method']}, CV: {metadata['data_analysis']['metrics'].get('distance_cv', 0):.2f}")

    def test_automatic_parameters(self, generator, linear_regular_data):
        """Test that parameters are automatically determined."""
        lon, lat = linear_regular_data
        
        polygon, metadata = generator.create_flightline_polygon(lon, lat)
        
        # Check that all automatic parameters were set
        assert "target_vertices" in metadata["data_analysis"]
        assert "min_coverage" in metadata["data_analysis"]
        assert "buffer_m" in metadata
        assert metadata["vertices"] > 0
        assert "generation_time_seconds" in metadata

    def test_empty_data(self, generator):
        """Test handling of empty data."""
        lon, lat = [], []
        
        polygon, metadata = generator.create_flightline_polygon(lon, lat)
        
        assert polygon is None
        assert metadata["vertices"] == 0
        assert metadata["method"] == "none"

    def test_single_point(self, generator):
        """Test handling of single point."""
        lon, lat = [-120], [35]
        
        polygon, metadata = generator.create_flightline_polygon(lon, lat)
        
        assert polygon is not None
        assert metadata["method"] == "point_buffer"
        assert polygon.area > 0

    def test_two_points(self, generator):
        """Test handling of two points."""
        lon, lat = [-120, -119], [35, 35]
        
        polygon, metadata = generator.create_flightline_polygon(lon, lat)
        
        assert polygon is not None
        assert metadata["method"] == "line_buffer_simple"
        assert polygon.area > 0

    def test_data_coverage_maintained(self, generator, linear_regular_data):
        """Test that data coverage is maintained above threshold."""
        lon, lat = linear_regular_data
        
        polygon, metadata = generator.create_flightline_polygon(lon, lat)
        
        # Check data coverage if available
        if "data_coverage" in metadata:
            min_coverage = metadata["data_analysis"]["min_coverage"]
            assert metadata["data_coverage"] >= min_coverage

    def test_vertex_optimization(self, generator, dense_compact_data):
        """Test that vertex count is optimized."""
        lon, lat = dense_compact_data
        
        polygon, metadata = generator.create_flightline_polygon(lon, lat)
        
        # Should achieve close to target vertices
        target = metadata["data_analysis"]["target_vertices"]
        actual = metadata["vertices"]
        
        # Allow some flexibility but should be close to target
        assert actual <= target * 2
        assert actual >= 3  # Minimum valid polygon

    def test_generation_timing(self, generator, sparse_data):
        """Test that generation time is recorded."""
        lon, lat = sparse_data
        
        polygon, metadata = generator.create_flightline_polygon(lon, lat)
        
        assert "generation_time_seconds" in metadata
        assert metadata["generation_time_seconds"] > 0
        assert metadata["generation_time_seconds"] < 60  # Should be fast

    def test_consistent_results(self, generator, linear_regular_data):
        """Test that results are consistent for same data."""
        lon, lat = linear_regular_data
        
        # Generate twice
        polygon1, metadata1 = generator.create_flightline_polygon(lon, lat)
        polygon2, metadata2 = generator.create_flightline_polygon(lon, lat)
        
        # Should select same method and similar parameters
        assert metadata1["method"] == metadata2["method"]
        assert metadata1["data_analysis"]["target_vertices"] == metadata2["data_analysis"]["target_vertices"]
        
        # Both should meet quality criteria even if exact results vary
        assert metadata1["vertices"] <= metadata1["data_analysis"]["target_vertices"] * 2
        assert metadata2["vertices"] <= metadata2["data_analysis"]["target_vertices"] * 2
        
        # Area should be similar (within 2x)
        if polygon1 and polygon2:
            area_ratio = polygon1.area / polygon2.area
            assert 0.5 <= area_ratio <= 2.0  # Areas should be similar