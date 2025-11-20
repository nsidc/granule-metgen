"""
Utility functions for spatial geometry operations.

This module contains shared utilities used by polygon generation algorithms
for handling satellite ground track buffering and spatial operations.
"""

import logging

from shapely import set_precision
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely.validation import make_valid

logger = logging.getLogger(__name__)


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

    When buffering polygons near the antimeridian (±180°), buffer points can
    extend beyond valid longitude bounds, creating invalid coordinates like
    -180.5° or 180.5°. This function clamps all longitude values to ensure
    they remain within the valid range.

    Args:
        geom: A Polygon in standard [-180, 180] longitude space

    Returns:
        A Polygon with longitude clamped to [-180, 180]
    """
    if not isinstance(geom, Polygon):
        return geom

    def clamp_coords(coords):
        return [(max(-180.0, min(180.0, lon)), lat) for lon, lat in coords]

    exterior = clamp_coords(geom.exterior.coords)
    return Polygon(exterior)


def filter_polygon_points_by_tolerance(polygon, tolerance=0.0001):
    """
    Filter polygon points to ensure minimum spacing according to CMR tolerance requirements.

    Uses Shapely's set_precision to snap points to a grid, which automatically
    merges vertices that are closer than the tolerance. This ensures that no two
    successive points in the polygon boundary are within the tolerance distance.

    Parameters:
    -----------
    polygon : shapely.geometry.Polygon
        Polygon whose vertices need filtering
    tolerance : float
        Minimum required distance between points in degrees (default: 0.0001)

    Returns:
    --------
    shapely.geometry.Polygon : Filtered polygon with tolerance-compliant vertices
    """
    if not hasattr(polygon, "exterior") or len(polygon.exterior.coords) <= 4:
        return polygon

    try:
        # Use set_precision to snap to a grid with spacing equal to tolerance
        # This automatically merges points that are within tolerance of each other
        # mode='pointwise' ensures individual vertices are snapped independently
        filtered_polygon = set_precision(polygon, grid_size=tolerance, mode="pointwise")

        # Ensure the result is valid
        if not filtered_polygon.is_valid:
            filtered_polygon = make_valid(filtered_polygon)

        # Check if we still have enough vertices for a valid polygon
        if (
            hasattr(filtered_polygon, "exterior")
            and len(filtered_polygon.exterior.coords) >= 4
        ):
            return filtered_polygon
        else:
            logger.warning(
                "Tolerance filtering resulted in degenerate polygon, keeping original"
            )
            return polygon

    except Exception as e:
        logger.error(f"Failed to filter polygon by tolerance: {e}")
        return polygon


def ensure_counter_clockwise(polygon):
    """
    Ensure polygon has counter-clockwise winding order as required by CMR.

    The Common Metadata Repository (CMR) requires that polygon points be
    specified in counter-clockwise order. This function checks the orientation
    and corrects it if necessary.

    Parameters:
    -----------
    polygon : shapely.geometry.Polygon
        Polygon to check and potentially reorient

    Returns:
    --------
    shapely.geometry.Polygon : Polygon with counter-clockwise exterior ring
    """
    try:
        if not hasattr(polygon, "exterior"):
            return polygon

        # Use shapely's orient function to ensure counter-clockwise orientation
        # sign=1.0 ensures counter-clockwise exterior, clockwise holes
        oriented_polygon = orient(polygon, sign=1.0)

        return oriented_polygon

    except Exception as e:
        logger.error(f"Failed to ensure counter-clockwise orientation: {e}")
        return polygon
