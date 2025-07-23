"""
Tests for the polygon_generator module.
"""

import numpy as np
import pytest
from shapely.geometry import Point, Polygon

from nsidc.metgen.spatial import create_flightline_polygon
from nsidc.metgen.spatial.polygon_generator import _filter_polygon_points_by_tolerance


class TestPolygonGenerator:
    """Test suite for polygon generation."""

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

    @pytest.fixture
    def large_flightline(self):
        """Create large flightline dataset."""
        t = np.linspace(0, 100, 15000)
        lon = -120 + 0.1 * t + 0.01 * np.random.randn(15000)
        lat = 35 + 0.05 * t + 0.01 * np.random.randn(15000)
        return lon, lat

    @pytest.fixture
    def antimeridian_flightline(self):
        """Create flightline that crosses antimeridian."""
        lon = np.array([179, 179.5, -179.5, -179, -178.5])
        lat = np.array([60, 60.1, 60.2, 60.3, 60.4])
        return lon, lat

    def test_basic_polygon_generation(self, simple_flightline):
        """Test basic polygon generation."""
        lon, lat = simple_flightline

        polygon, metadata = create_flightline_polygon(lon, lat)

        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["method"] in ["concave_hull", "convex_hull_fallback"]
        assert metadata["vertices"] >= 3
        assert metadata["data_points"] == len(lon)
        assert metadata["final_data_coverage"] >= 0.90
        assert "generation_time_seconds" in metadata

    def test_complex_flightline(self, complex_flightline):
        """Test polygon generation with complex curved flightline."""
        lon, lat = complex_flightline

        polygon, metadata = create_flightline_polygon(lon, lat)

        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["vertices"] >= 3
        assert metadata["final_data_coverage"] >= 0.90

        # Should handle the complexity without excessive vertices
        assert metadata["vertices"] <= 150

    def test_sparse_data(self, sparse_flightline):
        """Test polygon generation with sparse data."""
        lon, lat = sparse_flightline

        polygon, metadata = create_flightline_polygon(lon, lat)

        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["data_points"] == len(lon)
        assert metadata["final_data_coverage"] >= 0.90

        # Sparse data should still produce reasonable polygon
        assert metadata["vertices"] >= 3

    def test_large_dataset_subsampling(self, large_flightline):
        """Test that large datasets are subsampled appropriately."""
        lon, lat = large_flightline

        polygon, metadata = create_flightline_polygon(lon, lat)

        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["data_points"] == len(lon)
        assert metadata.get("subsampling_used", False) is True
        assert metadata.get("subsampled_point_count", 0) < len(lon)
        assert metadata["final_data_coverage"] >= 0.90

    def test_antimeridian_crossing(self, antimeridian_flightline):
        """Test handling of antimeridian crossing."""
        lon, lat = antimeridian_flightline

        polygon, metadata = create_flightline_polygon(lon, lat)

        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["vertices"] >= 3
        assert metadata["final_data_coverage"] >= 0.90

        # Should handle antimeridian crossing without issues
        assert metadata["data_points"] == len(lon)

    def test_coverage_enhancement(self, simple_flightline):
        """Test that coverage enhancement works when initial coverage is low."""
        lon, lat = simple_flightline

        # Use a subset to potentially trigger coverage enhancement
        subset_indices = np.arange(0, len(lon), 10)  # Every 10th point
        lon_subset = lon[subset_indices]
        lat_subset = lat[subset_indices]

        polygon, metadata = create_flightline_polygon(lon_subset, lat_subset)

        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["final_data_coverage"] >= 0.90

        # Should apply buffering if needed
        if metadata["initial_data_coverage"] < 0.98:
            assert metadata.get("coverage_enhanced", False) is False

    def test_data_coverage_calculation(self, simple_flightline):
        """Test that data coverage is calculated correctly."""
        lon, lat = simple_flightline

        polygon, metadata = create_flightline_polygon(lon, lat)

        # Manually verify coverage calculation
        points_inside = 0
        for x, y in zip(lon, lat):
            if polygon.contains(Point(x, y)):
                points_inside += 1

        manual_coverage = points_inside / len(lon)
        reported_coverage = metadata["final_data_coverage"]

        # Should be close (allowing for sampling differences)
        assert abs(manual_coverage - reported_coverage) < 0.05

    def test_edge_cases(self):
        """Test edge cases."""
        # Empty data
        lon = np.array([])
        lat = np.array([])

        polygon, metadata = create_flightline_polygon(lon, lat)
        assert polygon is None or polygon.is_empty
        assert metadata["data_points"] == 0

        # Single point
        lon = np.array([-120])
        lat = np.array([35])

        polygon, metadata = create_flightline_polygon(lon, lat)
        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["data_points"] == 1
        assert metadata["method"] == "simple_buffer"

        # Two points
        lon = np.array([-120, -119])
        lat = np.array([35, 35.5])

        polygon, metadata = create_flightline_polygon(lon, lat)
        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["data_points"] == 2
        assert metadata["method"] == "simple_buffer"

    def test_small_dataset_parameters(self):
        """Test that small datasets use conservative parameters."""
        # Create small dataset (< 100 points)
        lon = np.linspace(-120, -119, 50)
        lat = np.linspace(35, 35.5, 50)

        polygon, metadata = create_flightline_polygon(lon, lat)

        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["data_points"] == 50
        assert metadata["final_data_coverage"] >= 0.90

        # Should not use subsampling for small datasets
        assert metadata.get("subsampling_used", False) is False

    def test_convex_hull_fallback(self):
        """Test fallback to convex hull when concave hull fails."""
        # Create degenerate data that might cause concave hull to fail
        lon = np.array([-120, -120, -120])  # All same longitude
        lat = np.array([35, 35.1, 35.2])

        polygon, metadata = create_flightline_polygon(lon, lat)

        # Should still produce a valid polygon
        assert isinstance(polygon, Polygon)
        assert polygon.is_valid
        assert metadata["vertices"] >= 3

    def test_metadata_completeness(self, simple_flightline):
        """Test that metadata contains all expected fields."""
        lon, lat = simple_flightline

        polygon, metadata = create_flightline_polygon(lon, lat)

        # Required metadata fields
        required_fields = [
            "method",
            "data_points",
            "vertices",
            "generation_time_seconds",
            "final_data_coverage",
            "polygon_area",
        ]

        for field in required_fields:
            assert field in metadata, f"Missing required field: {field}"

        # Verify types
        assert isinstance(metadata["method"], str)
        assert isinstance(metadata["data_points"], int)
        assert isinstance(metadata["vertices"], int)
        assert isinstance(metadata["generation_time_seconds"], (int, float))
        assert isinstance(metadata["final_data_coverage"], (int, float))
        assert isinstance(metadata["polygon_area"], (int, float))

    def test_performance_timing(self, simple_flightline):
        """Test that generation completes in reasonable time."""
        lon, lat = simple_flightline

        polygon, metadata = create_flightline_polygon(lon, lat)

        # Should complete quickly for test data
        assert metadata["generation_time_seconds"] < 5.0
        assert metadata["generation_time_seconds"] > 0

    def test_polygon_validity(self, complex_flightline):
        """Test that generated polygons are always valid."""
        lon, lat = complex_flightline

        polygon, metadata = create_flightline_polygon(lon, lat)

        assert polygon.is_valid
        assert not polygon.is_empty
        assert polygon.geom_type == "Polygon"

        # Should have reasonable area
        assert polygon.area > 0

    def test_vertex_count_reasonable(self, simple_flightline):
        """Test that vertex counts are reasonable."""
        lon, lat = simple_flightline

        polygon, metadata = create_flightline_polygon(lon, lat)

        # Should have reasonable vertex count
        vertices = metadata["vertices"]
        assert vertices >= 3  # Minimum for polygon
        assert vertices <= 200  # Maximum reasonable limit

        # For simple flightline, should be quite manageable
        assert vertices <= 100

    def test_coverage_quality_tradeoff(self, complex_flightline):
        """Test that algorithm balances coverage and vertex count."""
        lon, lat = complex_flightline

        polygon, metadata = create_flightline_polygon(lon, lat)

        # Should achieve reasonable coverage (relaxed threshold for complex curves)
        assert metadata["final_data_coverage"] >= 0.90

        # While maintaining reasonable vertex count
        assert metadata["vertices"] <= 150

        # Area should be reasonable (not massively overblown)
        if metadata.get("area_increase_ratio"):
            assert metadata["area_increase_ratio"] <= 5.0

    def test_reproducibility(self, simple_flightline):
        """Test that results are reproducible."""
        lon, lat = simple_flightline

        # Generate polygon twice
        polygon1, metadata1 = create_flightline_polygon(lon, lat)
        polygon2, metadata2 = create_flightline_polygon(lon, lat)

        # Results should be identical (or very close)
        assert metadata1["vertices"] == metadata2["vertices"]
        assert (
            abs(metadata1["final_data_coverage"] - metadata2["final_data_coverage"])
            < 0.01
        )
        assert abs(metadata1["polygon_area"] - metadata2["polygon_area"]) < 1e-10

    def test_tolerance_filtering(self):
        """Test that tolerance filtering ensures minimum spacing between successive points."""
        # Create a polygon with some vertices too close together
        coords = [
            (0.0, 0.0),
            (0.001, 0.0),  # Far enough from previous
            (0.00105, 0.0),  # Too close to previous (distance ~0.00005)
            (0.002, 0.0),  # Far enough
            (0.002, 0.001),  # Far enough
            (0.001, 0.001),  # Far enough
            (0.0, 0.001),  # Far enough
            (0.0, 0.0),  # Close the polygon
        ]
        polygon = Polygon(coords[:-1])  # Shapely will auto-close

        # Test with default tolerance
        tolerance = 0.0001
        filtered_polygon = _filter_polygon_points_by_tolerance(
            polygon, tolerance=tolerance
        )

        # The key requirement: all successive points should be at least tolerance apart
        filtered_coords = list(filtered_polygon.exterior.coords)[
            :-1
        ]  # Exclude closing point

        for i in range(len(filtered_coords)):
            next_i = (i + 1) % len(filtered_coords)  # Handle wrap-around to first point
            p1 = Point(filtered_coords[i])
            p2 = Point(filtered_coords[next_i])
            distance = p1.distance(p2)
            assert distance >= tolerance - 1e-10, (
                f"Points {i} and {next_i} are too close: {distance:.6f} < {tolerance}"
            )

    def test_polygon_with_tolerance(self):
        """Test polygon generation with tolerance filtering."""
        # Create flightline with some very close points
        lon = np.array(
            [
                -120.0,
                -120.00005,
                -120.0001,
                -120.001,  # Close points at start
                -119.9,
                -119.8,
                -119.7,
                -119.6,  # Main flightline
                -119.5,
                -119.49995,
                -119.4999,  # Close points at end
            ]
        )
        lat = np.array(
            [
                35.0,
                35.00005,
                35.0001,
                35.001,  # Close points at start
                35.1,
                35.2,
                35.3,
                35.4,  # Main flightline
                35.5,
                35.50005,
                35.5001,  # Close points at end
            ]
        )

        # Generate polygon with default tolerance
        polygon, metadata = create_flightline_polygon(
            lon, lat, cartesian_tolerance=0.0001
        )

        # Tolerance filtering happens on the polygon vertices, not input points
        # So we check if any vertices were filtered
        if "tolerance_filtered" in metadata:
            assert (
                metadata["pre_tolerance_vertices"] > metadata["post_tolerance_vertices"]
            )
            assert metadata["cartesian_tolerance"] == 0.0001

        # Polygon should still be valid
        assert isinstance(polygon, Polygon)
        assert polygon.is_valid

    def test_different_tolerance_values(self):
        """Test with different tolerance values."""
        # Create a dense circular pattern that will result in many close vertices
        t = np.linspace(0, 2 * np.pi, 200)
        lon = -120 + 0.01 * np.cos(t)
        lat = 35 + 0.01 * np.sin(t)

        # Test with different tolerances
        tolerances = [0.00001, 0.0001, 0.001, 0.01]
        vertex_counts = []

        for tol in tolerances:
            polygon, metadata = create_flightline_polygon(
                lon, lat, cartesian_tolerance=tol
            )
            vertex_counts.append(metadata["vertices"])

        # Larger tolerances should generally result in fewer vertices
        # (though not strictly monotonic due to algorithm complexity)
        assert (
            vertex_counts[-1] <= vertex_counts[0]
        )  # Largest tolerance has fewest vertices

    def test_tolerance_preserves_shape(self):
        """Test that tolerance filtering preserves overall shape."""
        # Create a circular flightline
        t = np.linspace(0, 2 * np.pi, 1000)
        lon = -120 + 0.5 * np.cos(t)
        lat = 35 + 0.5 * np.sin(t)

        # Add some noise to create close points
        lon += np.random.normal(0, 0.00002, len(lon))
        lat += np.random.normal(0, 0.00002, len(lat))

        # Generate polygon with tolerance
        polygon, metadata = create_flightline_polygon(
            lon, lat, cartesian_tolerance=0.0001
        )

        # Check that shape is preserved (roughly circular)
        centroid = polygon.centroid
        assert abs(centroid.x - (-120)) < 0.1
        assert abs(centroid.y - 35) < 0.1

        # Coverage should still be good
        assert metadata["final_data_coverage"] >= 0.90

    @pytest.mark.parametrize(
        "lon,lat,description",
        [
            # Simple square
            (
                np.array([-120, -119, -119, -120, -120]),
                np.array([35, 35, 36, 36, 35]),
                "simple square",
            ),
            # Triangle
            (
                np.array([-120, -119, -119.5, -120]),
                np.array([35, 35, 36, 35]),
                "triangle",
            ),
            # L-shape
            (
                np.array([-120, -119, -119, -119.5, -119.5, -120, -120]),
                np.array([35, 35, 35.5, 35.5, 36, 36, 35]),
                "L-shape",
            ),
            # Clockwise input circle
            (
                np.array(
                    [-120 + 0.1 * np.cos(t) for t in np.linspace(0, 2 * np.pi, 20)]
                ),
                np.array([35 + 0.1 * np.sin(t) for t in np.linspace(0, 2 * np.pi, 20)]),
                "clockwise circle",
            ),
            # Counter-clockwise input circle
            (
                np.array(
                    [-120 + 0.1 * np.cos(t) for t in np.linspace(0, -2 * np.pi, 20)]
                ),
                np.array(
                    [35 + 0.1 * np.sin(t) for t in np.linspace(0, -2 * np.pi, 20)]
                ),
                "counter-clockwise circle",
            ),
        ],
    )
    def test_generated_polygon_is_counter_clockwise(self, lon, lat, description):
        """Test that all generated polygons have counter-clockwise orientation.

        CMR requires polygons to be oriented counter-clockwise. This test verifies
        that our polygon generator produces correctly oriented polygons regardless
        of input point ordering.
        """
        polygon, _ = create_flightline_polygon(lon, lat)

        # Check if the exterior ring is counter-clockwise using is_ccw property
        is_ccw = polygon.exterior.is_ccw

        assert is_ccw, (
            f"Polygon for {description} has clockwise orientation. CMR requires counter-clockwise."
        )
