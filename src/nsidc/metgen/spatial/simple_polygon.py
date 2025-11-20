"""
Simple buffering algorithm for satellite ground tracks.

This module provides a straightforward approach to creating buffered polygons
around satellite ground tracks, with special handling for antimeridian crossings.

The algorithm uses coordinate shifting to maintain polygon continuity across
the antimeridian, producing single polygons compatible with UMM-G GEODETIC
GPolygon format (coordinates in [-180, 180] range that span the antimeridian).

LIMITATIONS:
    This algorithm is designed for ground tracks that cross the antimeridian
    in a consistent manner (e.g., polar orbits that repeatedly cross). It will
    not correctly handle tracks that cross the antimeridian once and then remain
    on one side, or tracks with multiple back-and-forth crossings. Such tracks
    may produce invalid geometries or self-intersecting polygons.

    For typical satellite ground tracks (single continuous passes or orbits),
    this algorithm works correctly.
"""

from typing import List, Tuple

from shapely.geometry import LineString, Polygon

from .spatial_utils import (
    clamp_latitude,
    clamp_longitude,
    ensure_counter_clockwise,
    filter_polygon_points_by_tolerance,
)


def has_antimeridian_crossing(points: List[Tuple[float, float]]) -> bool:
    """
    Check if the track crosses the antimeridian.

    Returns True if any segment has longitude difference > 180 degrees.

    Args:
        points: List of (lon, lat) tuples in [-180, 180] range

    Returns:
        True if track crosses the antimeridian, False otherwise
    """
    for i in range(len(points) - 1):
        lon_diff = abs(points[i + 1][0] - points[i][0])
        if lon_diff > 180:
            return True
    return False


def shift_western_hemi(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """
    Shift negative longitudes from [-180, 0) to [180, 360).

    This creates continuity around the antimeridian by moving the western
    hemisphere to the eastern side, resulting in a continuous space without
    the -180/+180 discontinuity.

    Args:
        points: List of (lon, lat) tuples in [-180, 180] range

    Returns:
        List of (lon, lat) tuples with negative longitudes shifted to [180, 360)
    """
    return [(lon + 360 if lon < 0 else lon, lat) for lon, lat in points]


def unshift_western_hemi(geom: Polygon) -> Polygon:
    """
    Shift longitudes from [180, 360) back to [-180, 0).

    This reverses the shift applied during buffering, converting the geometry
    back to standard [-180, 180] coordinate range while preserving the
    antimeridian-spanning structure.

    Args:
        geom: A Polygon with coordinates potentially in [0, 360) range

    Returns:
        The same geometry with longitudes >= 180 shifted to negative values
    """

    def shift_coords(coords):
        return [(lon - 360 if lon >= 180 else lon, lat) for lon, lat in coords]

    exterior = shift_coords(geom.exterior.coords)
    return Polygon(exterior)


def create_buffered_polygon(
    points: List[Tuple[float, float]],
    buffer_distance: float,
    simplify_tolerance: float = 0.01,
    cartesian_tolerance: float = 0.0001,
) -> Polygon:
    """
    Create a buffered polygon around a satellite ground track.

    This algorithm handles antimeridian crossings by shifting coordinates to
    create a continuous space for buffering, then shifting back to standard
    [-180, 180] range.

    Algorithm:
        1. If antimeridian crossing: shift negative longitudes [-180, 0) to [180, 360)
        2. Buffer the track in continuous space
        3. Simplify the polygon to reduce coordinate count (in shifted space if needed)
        4. If antimeridian crossing: shift back [180, 360) to [-180, 0)
        5. Clamp latitude to [-89.9, 89.9] and longitude to [-180, 180]
        6. Filter polygon points by CMR tolerance (minimum point separation)
        7. Ensure counter-clockwise orientation for CMR compliance

    Note: Simplification (step 3) happens in the shifted space before unshifting
    to avoid creating invalid geometries. Simplification after unshifting can create
    self-intersections because the simplifier doesn't understand that coordinates
    like 179°, -179° represent continuity across the antimeridian.

    The result for antimeridian-crossing tracks is a single polygon with
    coordinates that transition from positive to negative longitudes
    (e.g., 178, 179, -179, -178), which is compatible with UMM-G GEODETIC
    GPolygon representation.

    Args:
        points: List of (lon, lat) tuples in [-180, 180] range representing
                the ground track
        buffer_distance: Buffer distance in degrees
        simplify_tolerance: Tolerance for polygon simplification in degrees.
                           Smaller values preserve more detail. Default is 0.01.
        cartesian_tolerance: Minimum spacing between points in degrees for CMR
                            compliance (default: 0.0001)

    Returns:
        A Polygon representing the buffered track.
        For tracks crossing the antimeridian, returns a single polygon
        with coordinates spanning from positive to negative longitudes.

    Raises:
        ValueError: If fewer than 2 points are provided

    Example:
        >>> points = [(179.0, 80.0), (-179.0, 81.0), (-178.0, 82.0)]
        >>> buffered = create_buffered_polygon(points, 1.0)
        >>> # Returns a single Polygon spanning the antimeridian
    """
    if len(points) < 2:
        raise ValueError("Need at least 2 points to create a ground track")

    # Check if track crosses antimeridian
    crosses_antimeridian = has_antimeridian_crossing(points)

    if crosses_antimeridian:
        # Shift negative longitudes to [180, 360) for continuity
        shifted_points = shift_western_hemi(points)
        track = LineString(shifted_points)
    else:
        # No antimeridian crossing, use points as-is
        track = LineString(points)

    # Buffer the track
    buffered = track.buffer(buffer_distance)

    # Simplify the polygon to reduce coordinate count (in shifted space if needed)
    buffered = buffered.simplify(simplify_tolerance, preserve_topology=True)

    if crosses_antimeridian:
        # Shift back: [180, 360) → [-180, 0)
        buffered = unshift_western_hemi(buffered)

    # Clamp coordinates to valid ranges (after unshifting)
    buffered = clamp_latitude(buffered)
    buffered = clamp_longitude(buffered)

    # Apply CMR compliance: filter points by tolerance and ensure counter-clockwise
    buffered = filter_polygon_points_by_tolerance(buffered, tolerance=cartesian_tolerance)
    buffered = ensure_counter_clockwise(buffered)

    return buffered
