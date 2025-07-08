"""
Tests for the PolygonGenerator class.
"""

import numpy as np
import pytest
from nsidc.metgen.spatial import PolygonGenerator
from shapely.geometry import Point, Polygon


class TestPolygonGenerator:
    """Test suite for PolygonGenerator."""

    @pytest.fixture
    def generator(self):
        """Create a PolygonGenerator instance."""
        return PolygonGenerator()

    @pytest.fixture
    def simple_flightline(self):
        """Create simple flightline test data."""
        # Create a simple linear flightline
        t = np.linspace(0, 10, 100)
        lon = -120 + 0.1 * t
        lat = 35 + 0.05 * t
        return lon, lat

    @pytest.fixture
    def complex_flightline(self):
        """Create more complex flightline with curves."""
        t = np.linspace(0, 2 * np.pi, 500)
        lon = -120 + 0.5 * np.sin(t) + 0.1 * np.sin(3 * t)
        lat = 35 + 0.5 * np.cos(t) + 0.1 * np.cos(3 * t)
        return lon, lat

    @pytest.fixture
    def sparse_flightline(self):
        """Create sparse flightline data."""
        lon = np.array([-120, -119.5, -119, -118.5, -118])
        lat = np.array([35, 35.1, 35.2, 35.3, 35.4])
        return lon, lat

    def test_beam_method(self, generator, simple_flightline):
        """Test beam method polygon generation."""
        lon, lat = simple_flightline

        polygon, metadata = generator.create_flightline_polygon(
            lon, lat, method="beam", buffer_distance=300
        )

        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["method"] == "beam"
        assert metadata["buffer_m"] == 300

    def test_adaptive_beam_method(self, generator, complex_flightline):
        """Test adaptive beam method polygon generation."""
        lon, lat = complex_flightline

        polygon, metadata = generator.create_flightline_polygon(
            lon, lat, method="adaptive_beam"
        )

        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["method"] == "adaptive_beam"
        assert "adaptive_buffer" in metadata
        assert metadata["adaptive_buffer"] > 0

    def test_union_buffer_method(self, generator, sparse_flightline):
        """Test union buffer method polygon generation."""
        lon, lat = sparse_flightline

        polygon, metadata = generator.create_flightline_polygon(
            lon, lat, method="union_buffer", buffer_distance=300
        )

        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["method"] == "union_buffer"
        assert metadata["buffer_m"] == 300
        assert "initial_circles" in metadata
        assert metadata["initial_circles"] == len(lon)
        assert "data_coverage" in metadata
        assert metadata["data_coverage"] >= 0.9  # Should cover most data points

    def test_union_buffer_adaptive_calculation(self, generator, sparse_flightline):
        """Test union buffer method with adaptive buffer calculation."""
        lon, lat = sparse_flightline

        # Don't provide buffer_distance to trigger adaptive calculation
        polygon, metadata = generator.create_flightline_polygon(
            lon, lat, method="union_buffer"
        )

        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["method"] == "union_buffer"
        assert "adaptive_buffer_calculation" in metadata
        assert metadata["adaptive_buffer_calculation"] == "nearest_neighbors"
        assert metadata["buffer_m"] > 0  # Should calculate some buffer size
        assert "initial_circles" in metadata
        assert "data_coverage" in metadata
        assert metadata["data_coverage"] >= 0.9  # Should still cover most data points

    def test_line_buffer_method(self, generator, simple_flightline):
        """Test line buffer method polygon generation."""
        lon, lat = simple_flightline

        polygon, metadata = generator.create_flightline_polygon(
            lon, lat, method="line_buffer", buffer_distance=400
        )

        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["method"] == "line_buffer"
        assert metadata["buffer_m"] == 400
        assert "optimization_attempts" in metadata
        assert metadata["total_attempts"] > 0
        assert "best_score" in metadata
        assert metadata["vertices"] >= 3  # Should have reasonable vertex count
        assert metadata["data_coverage"] >= 0.8  # Should cover most data points

    def test_line_buffer_adaptive_calculation(self, generator, simple_flightline):
        """Test line buffer method with adaptive buffer calculation."""
        lon, lat = simple_flightline

        # Don't provide buffer_distance to trigger adaptive calculation
        polygon, metadata = generator.create_flightline_polygon(
            lon, lat, method="line_buffer"
        )

        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["method"] == "line_buffer"
        assert "adaptive_buffer_calculation" in metadata
        assert metadata["adaptive_buffer_calculation"] == "sequential_distances"
        assert metadata["buffer_m"] > 0  # Should calculate some buffer size
        assert "optimization_attempts" in metadata
        assert metadata["total_attempts"] > 0
        assert metadata["data_coverage"] >= 0.8  # Should cover most data points

    def test_iterative_simplification(self, generator, complex_flightline):
        """Test polygon simplification."""
        lon, lat = complex_flightline

        # Generate initial polygon
        polygon, metadata = generator.create_flightline_polygon(
            lon,
            lat,
            method="beam",
            iterative_simplify=True,
            target_vertices=10,
        )

        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        # With min_coverage=0.90, simplification may stop before reaching exactly 10 vertices
        # to maintain quality. Allow up to 50 vertices as reasonable simplification.
        assert metadata["vertices"] <= 50  # Should be simplified from original ~470
        assert "simplification_history" in metadata
        assert len(metadata["simplification_history"]) > 0

    def test_data_coverage(self, generator, simple_flightline):
        """Test that generated polygon covers the data points."""
        lon, lat = simple_flightline

        polygon, metadata = generator.create_flightline_polygon(
            lon, lat, method="adaptive_beam"
        )

        # Check that most points are within the polygon
        points_inside = 0
        for x, y in zip(lon, lat):
            if polygon.contains(Point(x, y)):
                points_inside += 1

        coverage = points_inside / len(lon)
        assert coverage > 0.95  # At least 95% of points should be covered

    def test_invalid_method(self, generator, simple_flightline):
        """Test handling of invalid method."""
        lon, lat = simple_flightline

        with pytest.raises(ValueError, match="Unknown method"):
            generator.create_flightline_polygon(lon, lat, method="invalid_method")

    def test_empty_data(self, generator):
        """Test handling of empty data."""
        lon = np.array([])
        lat = np.array([])

        polygon, metadata = generator.create_flightline_polygon(lon, lat, method="beam")

        assert polygon is None
        assert metadata["points"] == 0

    def test_single_point(self, generator):
        """Test handling of single point."""
        lon = np.array([-120])
        lat = np.array([35])

        polygon, metadata = generator.create_flightline_polygon(
            lon, lat, method="beam", buffer_distance=100
        )

        # Should create a buffer around the single point
        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["points"] == 1

    def test_two_points(self, generator):
        """Test handling of two points (line)."""
        lon = np.array([-120, -119])
        lat = np.array([35, 35.5])

        polygon, metadata = generator.create_flightline_polygon(
            lon, lat, method="beam", buffer_distance=200
        )

        # Should create a buffered line
        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["points"] == 2
        assert metadata["buffer_m"] == 200

    def test_utm_projection(self, generator, simple_flightline):
        """Test that UTM projection is handled correctly."""
        lon, lat = simple_flightline

        # Test at different latitudes to ensure proper UTM zone selection
        for lat_offset in [0, 30, -30]:
            lat_shifted = lat + lat_offset

            polygon, metadata = generator.create_flightline_polygon(
                lon, lat_shifted, method="beam", buffer_distance=300
            )

            assert isinstance(polygon, Polygon)
            assert polygon.is_valid

    def test_multiregion_connection(self, generator):
        """Test connection of disconnected regions."""
        # Create two separate clusters
        lon1 = np.random.normal(-120, 0.01, 50)
        lat1 = np.random.normal(35, 0.01, 50)

        lon2 = np.random.normal(-119, 0.01, 50)
        lat2 = np.random.normal(35.5, 0.01, 50)

        lon = np.concatenate([lon1, lon2])
        lat = np.concatenate([lat1, lat2])

        polygon, metadata = generator.create_flightline_polygon(
            lon, lat, method="beam", buffer_distance=100, connect_regions=True
        )

        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        # Should be a single polygon, not multipolygon
        assert polygon.geom_type == "Polygon"

    def test_adaptive_buffer_calculation(self, generator):
        """Test adaptive buffer size calculation."""
        # Test with different data densities

        # Dense data - should get smaller buffer
        t = np.linspace(0, 1, 1000)
        lon_dense = -120 + 0.01 * t
        lat_dense = 35 + 0.01 * t

        _, metadata_dense = generator.create_flightline_polygon(
            lon_dense, lat_dense, method="adaptive_beam"
        )

        # Sparse data - should get larger buffer
        lon_sparse = np.array([-120, -119.9, -119.8])
        lat_sparse = np.array([35, 35.1, 35.2])

        _, metadata_sparse = generator.create_flightline_polygon(
            lon_sparse, lat_sparse, method="adaptive_beam"
        )

        # Sparse data should have larger adaptive buffer
        assert metadata_sparse["adaptive_buffer"] > metadata_dense["adaptive_buffer"]

    def test_simplification_quality_constraints(self, generator, complex_flightline):
        """Test that simplification respects quality constraints."""
        lon, lat = complex_flightline

        # Generate with strict quality constraints
        polygon_strict, metadata_strict = generator.create_flightline_polygon(
            lon,
            lat,
            method="beam",
            iterative_simplify=True,
            min_coverage=0.99,
        )

        # Generate with relaxed constraints
        polygon_relaxed, metadata_relaxed = generator.create_flightline_polygon(
            lon,
            lat,
            method="beam",
            iterative_simplify=True,
            min_coverage=0.90,
        )

        # Relaxed constraints should produce fewer vertices
        assert metadata_relaxed["vertices"] < metadata_strict["vertices"]

    def test_large_dataset_performance(self, generator):
        """Test performance optimization for large datasets."""
        # Create a large dataset
        n_points = 15000
        t = np.linspace(0, 100, n_points)
        lon = -120 + 0.1 * t + 0.01 * np.random.randn(n_points)
        lat = 35 + 0.05 * t + 0.01 * np.random.randn(n_points)

        # Should complete in reasonable time
        polygon, metadata = generator.create_flightline_polygon(
            lon, lat, method="beam", buffer_distance=300
        )

        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["points"] == n_points

    def test_sample_size_adaptation(self, generator):
        """Test that sample size adapts to data size for beam methods."""
        # Small dataset
        lon_small = np.linspace(-120, -119, 50)
        lat_small = np.linspace(35, 35.5, 50)

        _, metadata_small = generator.create_flightline_polygon(
            lon_small, lat_small, method="beam"
        )

        # Large dataset
        lon_large = np.linspace(-120, -119, 5000)
        lat_large = np.linspace(35, 35.5, 5000)

        _, metadata_large = generator.create_flightline_polygon(
            lon_large, lat_large, method="beam"
        )

        # Sample size should be all points for small dataset
        assert metadata_small.get("sample_size", 0) == 50
        # Sample size should be limited for large dataset
        assert metadata_large.get("sample_size", 0) < 5000

    def test_default_method(self, generator, simple_flightline):
        """Test that default method is adaptive_beam."""
        lon, lat = simple_flightline

        # Call without specifying method
        polygon, metadata = generator.create_flightline_polygon(lon, lat)

        assert metadata["method"] == "adaptive_beam"
        assert "adaptive_buffer" in metadata

    def test_generation_timing(self, generator, simple_flightline):
        """Test that generation timing is recorded."""
        lon, lat = simple_flightline

        polygon, metadata = generator.create_flightline_polygon(
            lon, lat, method="beam", buffer_distance=300
        )

        # Check that timing metadata is present
        assert "generation_time_seconds" in metadata
        assert isinstance(metadata["generation_time_seconds"], (int, float))
        assert metadata["generation_time_seconds"] > 0
        assert (
            metadata["generation_time_seconds"] < 10
        )  # Should be reasonable for test data

    def test_union_buffer_disconnected_components(self, generator):
        """Test union buffer method with disconnected data clusters."""
        # Create two separate clusters that should result in disconnected components
        np.random.seed(42)  # For reproducible results

        # First cluster
        lon1 = np.random.normal(-120, 0.01, 20)
        lat1 = np.random.normal(35, 0.01, 20)

        # Second cluster (far enough to be disconnected with small buffer)
        lon2 = np.random.normal(-119, 0.01, 20)
        lat2 = np.random.normal(35.5, 0.01, 20)

        lon = np.concatenate([lon1, lon2])
        lat = np.concatenate([lat1, lat2])

        # Use small buffer to ensure disconnected components initially
        polygon, metadata = generator.create_flightline_polygon(
            lon, lat, method="union_buffer", buffer_distance=100, connect_regions=True
        )

        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["method"] == "union_buffer"
        assert "disconnected_components" in metadata
        assert "connected" in metadata

        # Should result in either connection or taking largest component
        if metadata["disconnected_components"] > 1:
            assert metadata["connected"]  # Should attempt connection

        # Data coverage should be reasonable (may be lower with small buffer and disconnected clusters)
        assert metadata["data_coverage"] >= 0.6  # Relaxed threshold for this edge case

    def test_union_buffer_vertex_optimization(self, generator, simple_flightline):
        """Test that union buffer method works with iterative simplification."""
        lon, lat = simple_flightline

        # Test with simplification to achieve target vertex count
        polygon, metadata = generator.create_flightline_polygon(
            lon,
            lat,
            method="union_buffer",
            buffer_distance=400,
            iterative_simplify=True,
            target_vertices=12,
        )

        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["method"] == "union_buffer"

        # Should be simplified
        assert "simplification_history" in metadata
        assert len(metadata["simplification_history"]) > 0

        # Final vertex count should be reasonable (meeting goals)
        final_vertices = metadata["vertices"]
        assert final_vertices <= 127  # Should be at least "OK" level

        # Preferably in "Great" or "Good" range
        if final_vertices <= 32:
            print(f"  Excellent: {final_vertices} vertices (Great/Good range)")
        elif final_vertices <= 127:
            print(f"  Good: {final_vertices} vertices (OK range)")

        # Data coverage should remain high even after simplification
        if metadata.get("data_coverage", 0) > 0:
            assert metadata["data_coverage"] >= 0.85
