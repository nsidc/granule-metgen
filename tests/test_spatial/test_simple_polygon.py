"""
Tests for the simple_polygon module.
"""

import pytest
from shapely.geometry import Polygon

from nsidc.metgen.spatial.simple_polygon import (
    has_antimeridian_crossing,
    shift_western_hemi,
    unshift_western_hemi,
    create_buffered_polygon,
)


class TestAntimeridianDetection:
    """Test suite for antimeridian crossing detection."""

    def test_no_crossing_eastern_hemisphere(self):
        """Test points entirely in eastern hemisphere."""
        points = [(10.0, 45.0), (20.0, 46.0), (30.0, 47.0)]
        assert not has_antimeridian_crossing(points)

    def test_no_crossing_western_hemisphere(self):
        """Test points entirely in western hemisphere."""
        points = [(-120.0, 35.0), (-119.0, 36.0), (-118.0, 37.0)]
        assert not has_antimeridian_crossing(points)

    def test_crossing_east_to_west(self):
        """Test crossing from eastern to western hemisphere."""
        points = [(179.0, 80.0), (-179.0, 81.0)]
        assert has_antimeridian_crossing(points)

    def test_crossing_west_to_east(self):
        """Test crossing from western to eastern hemisphere."""
        points = [(-179.0, 80.0), (179.0, 81.0)]
        assert has_antimeridian_crossing(points)

    def test_multiple_crossings(self):
        """Test track with multiple antimeridian crossings."""
        points = [(170.0, 75.0), (-170.0, 76.0), (170.0, 77.0), (-170.0, 78.0)]
        assert has_antimeridian_crossing(points)

    def test_no_crossing_at_boundary(self):
        """Test points near but not crossing antimeridian."""
        points = [(178.0, 80.0), (179.0, 81.0), (179.5, 82.0)]
        assert not has_antimeridian_crossing(points)

    def test_single_point(self):
        """Test single point (no segments to cross)."""
        points = [(0.0, 0.0)]
        assert not has_antimeridian_crossing(points)

    def test_two_points_no_crossing(self):
        """Test two points without crossing."""
        points = [(0.0, 0.0), (10.0, 10.0)]
        assert not has_antimeridian_crossing(points)


class TestShiftWesternHemi:
    """Test suite for shifting western hemisphere coordinates."""

    def test_shift_negative_to_360(self):
        """Test shifting negative longitudes to [180, 360) range."""
        points = [(-170.0, 80.0), (170.0, 81.0), (-10.0, 82.0), (10.0, 83.0)]
        shifted = shift_western_hemi(points)

        expected = [(190.0, 80.0), (170.0, 81.0), (350.0, 82.0), (10.0, 83.0)]
        assert shifted == expected

    def test_shift_all_positive(self):
        """Test shifting when all longitudes are already positive."""
        points = [(10.0, 45.0), (20.0, 46.0), (30.0, 47.0)]
        shifted = shift_western_hemi(points)

        assert shifted == points

    def test_shift_all_negative(self):
        """Test shifting when all longitudes are negative."""
        points = [(-120.0, 35.0), (-119.0, 36.0), (-118.0, 37.0)]
        shifted = shift_western_hemi(points)

        expected = [(240.0, 35.0), (241.0, 36.0), (242.0, 37.0)]
        assert shifted == expected

    def test_shift_zero_longitude(self):
        """Test shifting with zero longitude."""
        points = [(0.0, 0.0)]
        shifted = shift_western_hemi(points)

        assert shifted == [(0.0, 0.0)]

    def test_shift_boundary_values(self):
        """Test shifting with boundary longitude values."""
        points = [(-180.0, 0.0), (-0.1, 0.0), (0.0, 0.0), (179.9, 0.0)]
        shifted = shift_western_hemi(points)

        expected = [(180.0, 0.0), (359.9, 0.0), (0.0, 0.0), (179.9, 0.0)]
        assert shifted == expected


class TestUnshiftWesternHemi:
    """Test suite for unshifting western hemisphere coordinates."""

    def test_unshift_polygon_from_360_range(self):
        """Test unshifting a polygon from [180, 360) back to [-180, 0)."""
        # Polygon created after shifting, with coords in [180, 360) range
        coords = [(190.0, 80.0), (200.0, 80.0), (200.0, 85.0), (190.0, 85.0), (190.0, 80.0)]
        poly = Polygon(coords)

        unshifted = unshift_western_hemi(poly)

        expected_coords = [(-170.0, 80.0), (-160.0, 80.0), (-160.0, 85.0), (-170.0, 85.0), (-170.0, 80.0)]
        assert list(unshifted.exterior.coords) == expected_coords

    def test_unshift_polygon_mixed_range(self):
        """Test unshifting polygon with mixed coordinate ranges."""
        # Polygon spanning the original antimeridian position
        coords = [(170.0, 80.0), (190.0, 80.0), (190.0, 85.0), (170.0, 85.0), (170.0, 80.0)]
        poly = Polygon(coords)

        unshifted = unshift_western_hemi(poly)

        # Only coordinates >= 180 should be shifted
        expected_coords = [(170.0, 80.0), (-170.0, 80.0), (-170.0, 85.0), (170.0, 85.0), (170.0, 80.0)]
        assert list(unshifted.exterior.coords) == expected_coords

    def test_unshift_polygon_no_change(self):
        """Test unshifting polygon with all coordinates < 180."""
        coords = [(10.0, 45.0), (20.0, 45.0), (20.0, 50.0), (10.0, 50.0), (10.0, 45.0)]
        poly = Polygon(coords)

        unshifted = unshift_western_hemi(poly)

        assert list(unshifted.exterior.coords) == coords

    def test_unshift_polygon_at_boundary(self):
        """Test unshifting polygon with coordinates at 180 boundary."""
        coords = [(180.0, 80.0), (190.0, 80.0), (190.0, 85.0), (180.0, 85.0), (180.0, 80.0)]
        poly = Polygon(coords)

        unshifted = unshift_western_hemi(poly)

        # 180.0 should be shifted to -180.0
        expected_coords = [(-180.0, 80.0), (-170.0, 80.0), (-170.0, 85.0), (-180.0, 85.0), (-180.0, 80.0)]
        assert list(unshifted.exterior.coords) == expected_coords

    def test_unshift_preserves_validity(self):
        """Test that unshifting preserves polygon validity."""
        coords = [(200.0, 80.0), (210.0, 80.0), (210.0, 85.0), (200.0, 85.0), (200.0, 80.0)]
        poly = Polygon(coords)

        unshifted = unshift_western_hemi(poly)

        assert unshifted.is_valid


class TestCreateBufferedPolygon:
    """Test suite for buffered polygon creation."""

    def test_simple_track_no_crossing(self):
        """Test buffering a simple track without antimeridian crossing."""
        points = [(10.0, 45.0), (20.0, 46.0), (30.0, 47.0)]
        buffer_distance = 1.0

        result = create_buffered_polygon(points, buffer_distance)

        assert isinstance(result, Polygon)
        # Check that all coordinates are in valid range
        coords = list(result.exterior.coords)

        for lon, lat in coords:
            assert -180 <= lon <= 180
            assert -90 <= lat <= 90

    def test_track_crossing_antimeridian(self):
        """Test buffering a track that crosses the antimeridian."""
        points = [(179.0, 80.0), (-179.0, 81.0), (-178.0, 82.0)]
        buffer_distance = 1.0

        result = create_buffered_polygon(points, buffer_distance)

        assert isinstance(result, Polygon)

        # For antimeridian-crossing tracks, should get a single polygon
        # with coordinates spanning positive to negative
        coords = list(result.exterior.coords)
        lons = [lon for lon, lat in coords]

        # Should have both positive and negative longitudes
        assert any(lon > 0 for lon in lons)
        assert any(lon < 0 for lon in lons)

        # All coordinates should be in [-180, 180] range
        for lon, lat in coords:
            assert -180 <= lon <= 180
            assert -90 <= lat <= 90

    def test_buffer_distance_affects_size(self):
        """Test that buffer distance affects polygon size."""
        points = [(10.0, 45.0), (20.0, 46.0), (30.0, 47.0)]

        small_buffer = create_buffered_polygon(points, 0.5)
        large_buffer = create_buffered_polygon(points, 2.0)

        # Larger buffer should create larger polygon
        assert large_buffer.area > small_buffer.area

    def test_minimum_points_error(self):
        """Test error is raised with insufficient points."""
        with pytest.raises(ValueError, match="Need at least 2 points"):
            create_buffered_polygon([(0.0, 0.0)], 1.0)

    def test_minimum_valid_points(self):
        """Test with minimum valid number of points."""
        points = [(10.0, 45.0), (20.0, 46.0)]
        buffer_distance = 1.0

        result = create_buffered_polygon(points, buffer_distance)

        assert isinstance(result, Polygon)
        assert result.is_valid

    def test_polar_region_track(self):
        """Test buffering a track in polar regions."""
        # High latitude track crossing antimeridian
        points = [(170.0, 85.0), (-170.0, 86.0), (-160.0, 87.0)]
        buffer_distance = 1.0

        result = create_buffered_polygon(points, buffer_distance)

        assert isinstance(result, Polygon)
        assert result.is_valid

    def test_long_track_many_points(self):
        """Test buffering a long track with many points."""
        # Create a long track
        points = [(i * 0.1, 45.0 + i * 0.01) for i in range(100)]
        buffer_distance = 0.5

        result = create_buffered_polygon(points, buffer_distance)

        assert isinstance(result, Polygon)
        assert result.is_valid

    def test_track_multiple_antimeridian_crossings(self):
        """Test track that crosses antimeridian multiple times."""
        points = [
            (170.0, 75.0),
            (-170.0, 76.0),
            (175.0, 77.0),
            (-175.0, 78.0)
        ]
        buffer_distance = 1.0

        result = create_buffered_polygon(points, buffer_distance)

        assert isinstance(result, Polygon)
        assert result.is_valid

    def test_result_geometry_validity(self):
        """Test that resulting geometries are always valid."""
        test_cases = [
            # No crossing
            ([(10.0, 45.0), (20.0, 46.0), (30.0, 47.0)], 1.0),
            # Crossing
            ([(179.0, 80.0), (-179.0, 81.0)], 1.0),
            # Small buffer
            ([(0.0, 0.0), (1.0, 1.0)], 0.1),
            # Large buffer
            ([(0.0, 0.0), (1.0, 1.0)], 5.0),
        ]

        for points, buffer_dist in test_cases:
            result = create_buffered_polygon(points, buffer_dist)
            assert result.is_valid, f"Invalid geometry for points={points}, buffer={buffer_dist}"

    def test_zero_buffer_distance(self):
        """Test with zero buffer distance."""
        points = [(10.0, 45.0), (20.0, 46.0)]

        result = create_buffered_polygon(points, 0.0)

        # Should still return a valid geometry (though might be degenerate)
        assert isinstance(result, Polygon)

    def test_western_hemisphere_track(self):
        """Test track entirely in western hemisphere."""
        points = [(-120.0, 35.0), (-119.0, 36.0), (-118.0, 37.0)]
        buffer_distance = 0.5

        result = create_buffered_polygon(points, buffer_distance)

        assert isinstance(result, Polygon)
        assert result.is_valid

        # All coordinates should remain in western hemisphere
        coords = list(result.exterior.coords)
        for lon, lat in coords:
            assert -180 <= lon <= 180


class TestCoordinateClamping:
    """Test suite for coordinate clamping to valid ranges."""

    def test_latitude_clamping_near_pole(self):
        """Test that latitudes are clamped to [-89.9, 89.9] range near poles."""
        # High latitude track with large buffer
        points = [(0.0, 88.0), (10.0, 89.0), (20.0, 89.5)]
        buffer_distance = 2.0  # Large buffer that would exceed 89.9

        result = create_buffered_polygon(points, buffer_distance)

        coords = list(result.exterior.coords)
        for lon, lat in coords:
            assert -89.9 <= lat <= 89.9, f"Latitude {lat} out of range [-89.9, 89.9]"

    def test_latitude_clamping_south_pole(self):
        """Test latitude clamping near south pole."""
        points = [(0.0, -88.0), (10.0, -89.0), (20.0, -89.5)]
        buffer_distance = 2.0

        result = create_buffered_polygon(points, buffer_distance)

        coords = list(result.exterior.coords)
        for lon, lat in coords:
            assert -89.9 <= lat <= 89.9, f"Latitude {lat} out of range [-89.9, 89.9]"

    def test_longitude_clamping_all_coords(self):
        """Test that all longitudes are in [-180, 180] range."""
        # Track crossing antimeridian
        points = [(179.0, 80.0), (-179.0, 81.0), (-178.0, 82.0)]
        buffer_distance = 1.0

        result = create_buffered_polygon(points, buffer_distance)

        coords = list(result.exterior.coords)
        for lon, lat in coords:
            assert -180 <= lon <= 180, f"Longitude {lon} out of range [-180, 180]"

    def test_no_clamping_needed_mid_latitudes(self):
        """Test tracks that don't require clamping."""
        points = [(10.0, 45.0), (20.0, 46.0), (30.0, 47.0)]
        buffer_distance = 1.0

        result = create_buffered_polygon(points, buffer_distance)

        # Should still be valid without clamping
        coords = list(result.exterior.coords)
        for lon, lat in coords:
            assert -180 <= lon <= 180
            assert -90 <= lat <= 90

    def test_longitude_clamping_no_antimeridian(self):
        """Test longitude clamping for tracks without antimeridian crossing."""
        # Track near but not crossing 180
        points = [(175.0, 45.0), (178.0, 46.0), (179.0, 47.0)]
        buffer_distance = 2.0  # Large buffer

        result = create_buffered_polygon(points, buffer_distance)

        coords = list(result.exterior.coords)
        for lon, lat in coords:
            assert -180 <= lon <= 180, f"Longitude {lon} out of range [-180, 180]"
            assert -90 <= lat <= 90

    def test_longitude_clamping_western_edge(self):
        """Test longitude clamping near -180."""
        points = [(-178.0, 45.0), (-179.0, 46.0), (-179.5, 47.0)]
        buffer_distance = 2.0

        result = create_buffered_polygon(points, buffer_distance)

        coords = list(result.exterior.coords)
        for lon, lat in coords:
            assert -180 <= lon <= 180, f"Longitude {lon} out of range [-180, 180]"

    def test_track_grazing_north_pole(self):
        """Test track that grazes the north pole at 89.0°."""
        # Track that passes very close to north pole
        points = [(0.0, 88.5), (30.0, 89.0), (60.0, 89.0), (90.0, 88.5)]
        buffer_distance = 1.5

        result = create_buffered_polygon(points, buffer_distance)

        assert result.is_valid
        coords = list(result.exterior.coords)

        # Check all coordinates are in valid ranges
        for lon, lat in coords:
            assert -180 <= lon <= 180
            assert -89.9 <= lat <= 89.9

        # Should have some points at or near the clamp limit
        max_lat = max(lat for lon, lat in coords)
        assert max_lat >= 89.0, "Expected track to reach high latitudes"

    def test_track_grazing_south_pole(self):
        """Test track that grazes the south pole at -89.0°."""
        # Track that passes very close to south pole
        points = [(0.0, -88.5), (30.0, -89.0), (60.0, -89.0), (90.0, -88.5)]
        buffer_distance = 1.5

        result = create_buffered_polygon(points, buffer_distance)

        assert result.is_valid
        coords = list(result.exterior.coords)

        # Check all coordinates are in valid ranges
        for lon, lat in coords:
            assert -180 <= lon <= 180
            assert -89.9 <= lat <= 89.9

        # Should have some points at or near the clamp limit
        min_lat = min(lat for lon, lat in coords)
        assert min_lat <= -89.0, "Expected track to reach high southern latitudes"


class TestPolygonSimplification:
    """Test suite for polygon simplification."""

    def test_simplification_reduces_points(self):
        """Test that simplification reduces the number of polygon points."""
        # Create a long track with many points
        points = [(i * 0.1, 45.0 + i * 0.01) for i in range(1000)]
        buffer_distance = 0.5

        result = create_buffered_polygon(points, buffer_distance)

        num_coords = len(result.exterior.coords)
        # Simplified polygon should have significantly fewer points than the buffered version
        # A buffered polygon from 1000 points would normally have thousands of coordinates
        assert num_coords < 500, f"Polygon not simplified enough: {num_coords} coordinates"

    def test_simplification_preserves_coverage(self):
        """Test that simplified polygon still covers the input track."""
        points = [(i * 0.1, 45.0 + i * 0.01) for i in range(100)]
        buffer_distance = 0.5

        result = create_buffered_polygon(points, buffer_distance)

        # All original points should be within the buffered polygon
        from shapely.geometry import Point
        for lon, lat in points:
            point = Point(lon, lat)
            assert result.contains(point) or result.touches(point), \
                f"Point ({lon}, {lat}) not covered by simplified polygon"

    def test_simplification_with_antimeridian_crossing(self):
        """Test that simplification works correctly with antimeridian crossing."""
        # Long track crossing antimeridian multiple times
        points = []
        for i in range(200):
            lon = 170.0 + (i * 0.1)
            if lon > 180:
                lon = lon - 360
            lat = 75.0 + i * 0.01
            points.append((lon, lat))

        buffer_distance = 1.0
        result = create_buffered_polygon(points, buffer_distance)

        # Should be simplified and valid
        assert result.is_valid
        num_coords = len(result.exterior.coords)
        assert num_coords < 300, f"Antimeridian-crossing polygon not simplified: {num_coords} coords"

    def test_simplification_maintains_validity(self):
        """Test that simplified polygons are always valid."""
        test_cases = [
            # Long straight track
            ([(i * 0.5, 45.0) for i in range(500)], 1.0),
            # Curved track
            ([(i * 0.1, 45.0 + 0.1 * (i % 10)) for i in range(300)], 0.5),
            # Dense track
            ([(i * 0.01, 45.0 + i * 0.001) for i in range(1000)], 0.2),
        ]

        for points, buffer_dist in test_cases:
            result = create_buffered_polygon(points, buffer_dist)
            assert result.is_valid, f"Simplified polygon invalid for {len(points)} points"

    def test_simplification_small_track_unchanged(self):
        """Test that small tracks don't get over-simplified."""
        # Small track with just a few points
        points = [(10.0, 45.0), (20.0, 46.0), (30.0, 47.0)]
        buffer_distance = 1.0

        result = create_buffered_polygon(points, buffer_distance)

        # Should still be valid with reasonable number of points
        assert result.is_valid
        num_coords = len(result.exterior.coords)
        # Should have enough points to represent a reasonable buffered shape
        assert num_coords >= 4, "Polygon over-simplified"

    def test_simplification_tolerance_parameter(self):
        """Test that simplification can be controlled via tolerance parameter."""
        points = [(i * 0.1, 45.0 + i * 0.01) for i in range(500)]
        buffer_distance = 0.5

        # This test assumes we might add a tolerance parameter in the future
        # For now, just test with default behavior
        result = create_buffered_polygon(points, buffer_distance)

        assert result.is_valid
        # Simplified polygon should have manageable number of coordinates
        num_coords = len(result.exterior.coords)
        assert num_coords < 1000, f"Too many coordinates: {num_coords}"
