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


def clamp_latitude(geom: Polygon) -> Polygon:
    """
    Clamp latitude coordinates to valid range.

    Only clamps latitude to [-89.9, 89.9] range. Longitude is not clamped
    to allow this function to work in both standard [-180, 180] and shifted
    [0, 360) coordinate spaces.

    Latitude is clamped to ±89.9° instead of ±90° to avoid geometric
    degeneracies at the poles where multiple points at the same latitude
    can create self-intersecting polygons.

    Removes duplicate consecutive points that may result from clamping
    to prevent invalid geometries.

    Args:
        geom: A Polygon

    Returns:
        A Polygon with latitude clamped to valid range
    """
    def clamp_coords(coords):
        clamped = []
        prev_coord = None

        for lon, lat in coords:
            # Clamp latitude to [-89.9, 89.9] to avoid pole degeneracies
            lat = max(-89.9, min(89.9, lat))

            # Skip duplicate consecutive points
            current_coord = (lon, lat)
            if current_coord != prev_coord:
                clamped.append(current_coord)
                prev_coord = current_coord

        # Ensure we have at least 3 unique points for a valid polygon
        # (Shapely will close it, so we need 3 distinct points minimum)
        if len(clamped) < 3:
            return None

        return clamped

    exterior = clamp_coords(geom.exterior.coords)

    if exterior is None:
        # Degenerate case - return a very small valid polygon
        # This shouldn't happen in practice with reasonable inputs
        return geom

    return Polygon(exterior)


def clamp_longitude(geom: Polygon) -> Polygon:
    """
    Clamp longitude coordinates to [-180, 180] range.

    This should only be called after unshifting from [0, 360) space to ensure
    we're clamping in the correct coordinate system.

    Args:
        geom: A Polygon in standard [-180, 180] longitude space

    Returns:
        A Polygon with longitude clamped to [-180, 180]
    """
    def clamp_coords(coords):
        return [(max(-180.0, min(180.0, lon)), lat) for lon, lat in coords]

    exterior = clamp_coords(geom.exterior.coords)
    return Polygon(exterior)


def create_buffered_polygon(
    points: List[Tuple[float, float]],
    buffer_distance: float,
    simplify_tolerance: float = 0.01
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

    return buffered
