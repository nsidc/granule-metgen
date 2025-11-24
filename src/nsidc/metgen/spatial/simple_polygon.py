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

from typing import Dict, List, Tuple

from shapely.geometry import LineString, Polygon

from .spatial_utils import (
    clamp_latitude,
    clamp_longitude,
    ensure_counter_clockwise,
    filter_polygon_points_by_tolerance,
)

# Default parameters for simple buffering algorithm
DEFAULT_BUFFER_DISTANCE = 0.1  # degrees
DEFAULT_SIMPLIFY_TOLERANCE = 0.01  # degrees
DEFAULT_CARTESIAN_TOLERANCE = 0.0001  # degrees


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
    lon: List[float],
    lat: List[float],
    buffer_distance: float = DEFAULT_BUFFER_DISTANCE,
    simplify_tolerance: float = DEFAULT_SIMPLIFY_TOLERANCE,
    cartesian_tolerance: float = DEFAULT_CARTESIAN_TOLERANCE,
) -> Tuple[Polygon, Dict]:
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
        lon: Array of longitude values in [-180, 180] range
        lat: Array of latitude values in [-90, 90] range
        buffer_distance: Buffer distance in degrees (default: 1.0)
        simplify_tolerance: Tolerance for polygon simplification in degrees.
                           Smaller values preserve more detail (default: 0.01)
        cartesian_tolerance: Minimum spacing between points in degrees for CMR
                            compliance (default: 0.0001)

    Returns:
        Tuple of (polygon, metadata):
            - polygon: A Polygon representing the buffered track.
                      For tracks crossing the antimeridian, returns a single polygon
                      with coordinates spanning from positive to negative longitudes.
            - metadata: Dictionary containing algorithm metadata including:
                       - method: Algorithm used ('simple_buffer')
                       - buffer_distance: Buffer distance applied
                       - vertices: Number of vertices in the final polygon
                       - antimeridian_crossing: Whether track crossed antimeridian

    Raises:
        ValueError: If fewer than 2 points are provided

    Example:
        >>> lon = [179.0, -179.0, -178.0]
        >>> lat = [80.0, 81.0, 82.0]
        >>> polygon, metadata = create_buffered_polygon(lon, lat, buffer_distance=1.0)
        >>> # Returns a single Polygon spanning the antimeridian
    """
    if len(lon) < 2 or len(lat) < 2:
        raise ValueError("Need at least 2 points to create a ground track")

    if len(lon) != len(lat):
        raise ValueError("lon and lat arrays must have the same length")

    # Convert lon/lat arrays to points list
    points = list(zip(lon, lat))

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
    buffered = filter_polygon_points_by_tolerance(
        buffered, tolerance=cartesian_tolerance
    )
    buffered = ensure_counter_clockwise(buffered)

    # Build metadata
    metadata = {
        "method": "simple_buffer",
        "buffer_distance": buffer_distance,
        "vertices": len(buffered.exterior.coords) - 1,  # Excluding closing point
        "antimeridian_crossing": crosses_antimeridian,
    }

    return buffered, metadata
