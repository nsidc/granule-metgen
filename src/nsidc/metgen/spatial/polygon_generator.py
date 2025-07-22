"""
Polygon Generator Module

Simple, reliable polygon generation using the concave_hull library.
This module replaces the old complex polygon generation with a more
effective approach that achieves better results with less complexity.

Includes backward-compatible PolygonGenerator class wrapper.
"""

import logging
import time

import numpy as np
from concave_hull import concave_hull
from shapely import set_precision
from shapely.geometry import Point, Polygon
from shapely.geometry.polygon import orient
from shapely.validation import make_valid

logger = logging.getLogger(__name__)


def _filter_polygon_points_by_tolerance(polygon, tolerance=0.0001):
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


def create_flightline_polygon(
    lon, lat, target_coverage=0.98, max_vertices=100, cartesian_tolerance=0.0001
):
    """
    Create a polygon representing the flightline coverage using concave hull.

    This function uses a simple, reliable approach with the concave_hull library
    and configurable quality parameters, ensuring all points meet CMR tolerance requirements.

    Parameters:
    -----------
    lon : array-like
        Longitude coordinates
    lat : array-like
        Latitude coordinates
    target_coverage : float, optional
        Target data coverage percentage (default: 0.98)
    max_vertices : int, optional
        Maximum number of vertices in final polygon (default: 100)
    cartesian_tolerance : float, optional
        Minimum spacing between points in degrees (default: 0.0001)
        This ensures CMR validation passes

    Returns:
    --------
    tuple: (polygon, metadata)
        - polygon: Shapely Polygon object with tolerance-compliant vertices
        - metadata: Dictionary with generation details
    """
    start_time = time.time()

    # Initialize metadata
    metadata = {
        "method": "concave_hull",
        "data_points": len(lon),
        "vertices": 0,
        "generation_time_seconds": 0,
    }

    logger.info(f"Processing {len(lon)} points")

    # For very small datasets, use more conservative parameters
    is_small_dataset = len(lon) < 100
    if is_small_dataset:
        logger.info(
            f"Small dataset detected ({len(lon)} points) - using conservative parameters"
        )

    # Handle edge cases
    if len(lon) < 3:
        logger.warning("Insufficient points for polygon, creating simple buffer")
        # Create a simple line buffer for very few points
        from shapely.geometry import LineString, Point

        if len(lon) == 1:
            polygon = Point(lon[0], lat[0]).buffer(0.01)
        else:
            line = LineString(zip(lon, lat))
            polygon = line.buffer(0.01)
        metadata["vertices"] = len(polygon.exterior.coords) - 1
        metadata["method"] = "simple_buffer"
        metadata["generation_time_seconds"] = time.time() - start_time
        return polygon, metadata

    # Preserve original coordinates for coverage calculations
    original_lon = np.array(lon)
    original_lat = np.array(lat)

    # Handle antimeridian crossing before creating points array
    lon = _handle_antimeridian_crossing(lon)

    # Create points array
    points = np.column_stack((lon, lat))

    # Intelligent subsampling to preserve boundary points for better coverage
    original_point_count = len(points)
    if len(points) > 8000:
        # More conservative subsampling, preserving more boundary points
        step = len(points) // 5000  # Target around 5000 points (increased from 3000)

        # Combine main sampling with boundary preservation

        # Combine and remove duplicates
        combined_indices = set()
        combined_indices.update(range(0, len(points), step))  # Main sampling
        combined_indices.update(range(min(100, len(points) // 10)))  # Start boundary
        combined_indices.update(
            range(len(points) - min(100, len(points) // 10), len(points))
        )  # End boundary

        points = points[sorted(list(combined_indices))]

        logger.info(
            f"Smart subsampled from {original_point_count} to {len(points)} points (preserving boundaries)"
        )
        metadata["subsampling_used"] = True
        metadata["subsampling_method"] = "boundary_preserving"
        metadata["original_point_count"] = original_point_count
        metadata["subsampled_point_count"] = len(points)

    logger.debug("Generating concave hull...")

    try:
        # Calculate appropriate length threshold based on data spread
        lon_range = np.ptp(points[:, 0])
        lat_range = np.ptp(points[:, 1])
        avg_range = (lon_range + lat_range) / 2

        # Adaptive length threshold based on dataset size
        if is_small_dataset:
            # For small datasets, use larger threshold to avoid over-detailed polygons
            length_threshold = max(avg_range * 0.025, 0.001)
        else:
            # Use 1.5% of average range as length threshold (reduced for better coverage)
            length_threshold = max(avg_range * 0.015, 0.0005)

        logger.debug(f"Length threshold: {length_threshold:.6f} degrees")

        # Generate concave hull
        hull_points = concave_hull(points, length_threshold=length_threshold)

        if len(hull_points) < 3:
            logger.warning("Concave hull failed, falling back to convex hull")
            from shapely.geometry import MultiPoint

            multipoint = MultiPoint(points)
            polygon = multipoint.convex_hull

            # Ensure we have a polygon, not a line/point
            if polygon.geom_type != "Polygon":
                polygon = polygon.buffer(0.01)  # Small buffer to create polygon
                metadata["buffered_degenerate"] = True

            metadata["method"] = "convex_hull_fallback"
        else:
            # Create polygon from hull points
            polygon = Polygon(hull_points)
            metadata["hull_points"] = len(hull_points)

            # Simple vertex reduction to keep polygons manageable
            if hasattr(polygon, "exterior") and len(polygon.exterior.coords) > 100:
                # Use basic simplification to reduce vertex count without obsessing over coverage
                tolerance = length_threshold * 0.5  # Conservative simplification
                simplified = polygon.simplify(tolerance, preserve_topology=True)
                if (
                    simplified
                    and not simplified.is_empty
                    and hasattr(simplified, "exterior")
                ):
                    polygon = simplified
                    metadata["simplified"] = True
                    metadata["simplify_tolerance"] = tolerance

    except Exception as e:
        logger.warning(f"Concave hull failed ({e}), falling back to convex hull")
        from shapely.geometry import MultiPoint

        multipoint = MultiPoint(points)
        polygon = multipoint.convex_hull

        # Ensure we have a polygon, not a line/point
        if polygon.geom_type != "Polygon":
            polygon = polygon.buffer(0.01)  # Small buffer to create polygon
            metadata["buffered_degenerate"] = True

        metadata["method"] = "convex_hull_fallback"
        metadata["error"] = str(e)

    # Ensure valid polygon and validate coverage
    if polygon is not None:
        polygon = make_valid(polygon)

        # Normalize longitude coordinates back to [-180, 180] range if needed
        polygon = _normalize_polygon_coordinates(polygon)

        # Apply tolerance filtering to ensure CMR compliance
        pre_filter_vertices = (
            len(polygon.exterior.coords) - 1 if hasattr(polygon, "exterior") else 0
        )
        polygon = _filter_polygon_points_by_tolerance(
            polygon, tolerance=cartesian_tolerance
        )
        post_filter_vertices = (
            len(polygon.exterior.coords) - 1 if hasattr(polygon, "exterior") else 0
        )

        if post_filter_vertices < pre_filter_vertices:
            logger.info(
                f"Tolerance filtering: {pre_filter_vertices} -> {post_filter_vertices} vertices "
                f"(tolerance: {cartesian_tolerance}°)"
            )
            metadata["tolerance_filtered"] = True
            metadata["pre_tolerance_vertices"] = pre_filter_vertices
            metadata["post_tolerance_vertices"] = post_filter_vertices
            metadata["cartesian_tolerance"] = cartesian_tolerance

        # Calculate coverage with original points for validation
        original_points = np.column_stack((original_lon, original_lat))
        coverage = _calculate_data_coverage(polygon, original_points)
        metadata["initial_data_coverage"] = coverage

        # Apply buffering if coverage is below target
        if coverage < target_coverage:
            logger.info(
                f"Initial coverage {coverage:.1%} < {target_coverage:.0%}, applying buffer enhancement..."
            )
            buffered_polygon = _buffer_enhance_coverage(
                polygon, original_points, target_coverage=target_coverage
            )
            if buffered_polygon:
                buffered_coverage = _calculate_data_coverage(
                    buffered_polygon, original_points
                )
                buffered_vertices = (
                    len(buffered_polygon.exterior.coords) - 1
                    if hasattr(buffered_polygon, "exterior")
                    else 0
                )

                # Calculate area ratio to avoid over-buffering
                original_area = polygon.area
                buffered_area = buffered_polygon.area
                area_increase = (
                    buffered_area / original_area if original_area > 0 else 1.0
                )

                logger.debug(
                    f"Buffered: {buffered_coverage:.1%} coverage, {buffered_vertices} vertices, {area_increase:.1f}x area"
                )

                # More conservative acceptance criteria - avoid excessive area growth
                coverage_improvement = buffered_coverage - coverage

                # Balanced acceptance: prioritize coverage but control area growth
                if (
                    (
                        buffered_coverage >= target_coverage
                        and area_increase < 3.0
                        and buffered_vertices < max_vertices * 1.2
                    )
                    or (
                        coverage_improvement > 0.05
                        and area_increase < 2.5
                        and buffered_vertices < max_vertices
                    )
                    or (
                        coverage_improvement > 0.03
                        and area_increase < 2.0
                        and buffered_vertices < max_vertices * 0.8
                    )
                    or (
                        coverage_improvement > 0.10
                        and buffered_vertices < max_vertices * 1.5
                    )
                ):  # Accept big improvements
                    polygon = buffered_polygon
                    coverage = buffered_coverage
                    metadata["coverage_enhanced"] = True
                    metadata["enhancement_method"] = "buffering"
                    metadata["enhancement_improvement"] = coverage_improvement
                    metadata["post_buffer_vertices"] = buffered_vertices
                    metadata["area_increase_ratio"] = area_increase
                else:
                    logger.debug(
                        f"Rejected buffering: area increase {area_increase:.1f}x too large or insufficient improvement"
                    )

                    # Emergency fallback: if original coverage is really bad, accept any reasonable improvement
                    if coverage < 0.85 and buffered_coverage > coverage + 0.15:
                        logger.info(
                            "Emergency fallback: accepting due to very low initial coverage"
                        )
                        polygon = buffered_polygon
                        coverage = buffered_coverage
                        metadata["coverage_enhanced"] = True
                        metadata["enhancement_method"] = "emergency_buffering"
                        metadata["enhancement_improvement"] = coverage_improvement
                        metadata["post_buffer_vertices"] = buffered_vertices
                        metadata["area_increase_ratio"] = area_increase

        metadata["final_data_coverage"] = coverage

        # Calculate final metrics
        if hasattr(polygon, "exterior"):
            metadata["vertices"] = len(polygon.exterior.coords) - 1
        else:
            metadata["vertices"] = 0

        metadata["polygon_area"] = polygon.area
    else:
        metadata["vertices"] = 0
        metadata["polygon_area"] = 0
        metadata["final_data_coverage"] = 0

    # Record generation time
    end_time = time.time()
    generation_time = end_time - start_time
    metadata["generation_time_seconds"] = generation_time

    logger.info(f"Complete: Generated in {generation_time:.2f}s")
    logger.info(f"Method: {metadata['method']}")
    logger.info(f"Vertices: {metadata['vertices']}")
    if "final_data_coverage" in metadata:
        logger.info(f"Final Data Coverage: {metadata['final_data_coverage']:.1%}")

    # Final step: ensure counter-clockwise orientation for CMR compliance
    if polygon is not None:
        polygon = _ensure_counter_clockwise(polygon)

    return polygon, metadata


def _calculate_data_coverage(polygon, data_points, sample_size=2000):
    """
    Calculate what percentage of data points are covered by the polygon.

    Parameters:
    -----------
    polygon : shapely.geometry.Polygon
        The polygon to test
    data_points : array-like
        Nx2 array of [lon, lat] data points
    sample_size : int
        Maximum number of points to sample for performance

    Returns:
    --------
    float : Coverage ratio (0.0 to 1.0)
    """
    if len(data_points) == 0:
        return 0.0

    # Sample points if dataset is large
    if len(data_points) > sample_size:
        indices = np.random.choice(len(data_points), sample_size, replace=False)
        sample_points = data_points[indices]
    else:
        sample_points = data_points

    # Count points inside polygon
    points_inside = 0
    for point in sample_points:
        if polygon.contains(Point(point)):
            points_inside += 1

    return points_inside / len(sample_points)


def _buffer_enhance_coverage(polygon, data_points, target_coverage=0.98):
    """
    Enhance polygon coverage by applying a simple buffer to expand coverage.

    This is much more efficient than complex point-by-point enhancement and
    maintains reasonable vertex counts while improving data coverage.

    Parameters:
    -----------
    polygon : shapely.geometry.Polygon
        Initial polygon
    data_points : array-like
        Nx2 array of [lon, lat] data points
    target_coverage : float
        Target coverage ratio to achieve

    Returns:
    --------
    shapely.geometry.Polygon or None : Buffered polygon or None if enhancement failed
    """
    try:
        current_coverage = _calculate_data_coverage(polygon, data_points)

        if current_coverage >= target_coverage:
            return polygon

        # Calculate appropriate buffer size based on data characteristics
        # Use a small buffer - typically 0.001-0.005 degrees (100m-500m at equator)
        lon_range = np.ptp(data_points[:, 0])
        lat_range = np.ptp(data_points[:, 1])
        avg_range = (lon_range + lat_range) / 2

        # Adaptive buffer sizing based on dataset characteristics
        is_small_dataset = len(data_points) < 100

        if is_small_dataset:
            # For small datasets, use moderate buffering but with area control
            base_buffer = avg_range * 0.005  # Same as normal datasets
            max_buffer = avg_range * 0.015  # Slightly more conservative max
        else:
            # Standard buffering for larger datasets
            base_buffer = avg_range * 0.005  # 0.5%
            max_buffer = avg_range * 0.02  # 2%

        for multiplier in [1.0, 1.5, 2.0, 3.0]:  # Removed 2.5 to be more conservative
            buffer_size = min(base_buffer * multiplier, max_buffer)

            # Apply buffer
            buffered = polygon.buffer(buffer_size)
            buffered = make_valid(buffered)

            # Take largest component if multipolygon
            if hasattr(buffered, "geoms"):
                buffered = max(buffered.geoms, key=lambda p: p.area)

            # Smooth and simplify the buffered polygon to reduce vertex count
            smoothed = _smooth_buffered_polygon(buffered, data_points)
            if smoothed:
                buffered = smoothed

            # Check coverage improvement
            new_coverage = _calculate_data_coverage(buffered, data_points)

            # Check vertex count
            vertices = (
                len(buffered.exterior.coords) - 1
                if hasattr(buffered, "exterior")
                else 0
            )

            # Accept if we improve coverage significantly (more generous acceptance)
            if (
                new_coverage >= target_coverage and vertices < 150
            ):  # Increased vertex limit
                return buffered
            elif (
                new_coverage > current_coverage + 0.03 and vertices < 80
            ):  # Lower threshold for improvement
                # Accept smaller improvement with lower vertex count
                return buffered

        # If no good buffer found, try one small buffer as fallback
        small_buffer = polygon.buffer(base_buffer * 0.5)
        small_buffer = make_valid(small_buffer)
        if hasattr(small_buffer, "geoms"):
            small_buffer = max(small_buffer.geoms, key=lambda p: p.area)

        fallback_coverage = _calculate_data_coverage(small_buffer, data_points)
        if fallback_coverage > current_coverage:
            return small_buffer

        return None

    except Exception as e:
        logger.error(f"Buffer enhancement failed: {e}")
        return None


def _smooth_buffered_polygon(polygon, data_points):
    """
    Smooth and simplify a buffered polygon to reduce vertex count while preserving coverage.

    Parameters:
    -----------
    polygon : shapely.geometry.Polygon
        Buffered polygon to smooth
    data_points : array-like
        Original data points for coverage checking

    Returns:
    --------
    shapely.geometry.Polygon or None : Smoothed polygon or None if failed
    """
    try:
        if not hasattr(polygon, "exterior"):
            return None

        original_vertices = len(polygon.exterior.coords) - 1
        original_coverage = _calculate_data_coverage(polygon, data_points)

        # Don't smooth if already low vertex count
        if original_vertices <= 30:
            return polygon

        # Calculate data range for tolerance scaling
        lon_range = np.ptp(data_points[:, 0])
        lat_range = np.ptp(data_points[:, 1])
        avg_range = (lon_range + lat_range) / 2

        # Try different simplification tolerances
        base_tolerance = avg_range * 0.001  # Start with 0.1% of data range

        best_polygon = polygon
        best_vertices = original_vertices

        for multiplier in [0.5, 1.0, 1.5, 2.0, 2.5]:
            tolerance = base_tolerance * multiplier

            # Apply simplification
            simplified = polygon.simplify(tolerance, preserve_topology=True)
            simplified = make_valid(simplified)

            if not hasattr(simplified, "exterior"):
                continue

            # Check vertex reduction and coverage preservation
            new_vertices = len(simplified.exterior.coords) - 1
            new_coverage = _calculate_data_coverage(simplified, data_points)

            # Accept if we reduce vertices significantly while keeping high coverage
            vertex_reduction = (original_vertices - new_vertices) / original_vertices
            coverage_loss = original_coverage - new_coverage

            # Good trade-off: reduce vertices by 25%+ with minimal coverage loss
            if (
                vertex_reduction >= 0.25
                and coverage_loss <= 0.02
                and new_vertices < best_vertices
            ):
                best_polygon = simplified
                best_vertices = new_vertices

        # Return smoothed version only if it's meaningfully better
        if best_vertices < original_vertices * 0.8:  # At least 20% vertex reduction
            return best_polygon
        else:
            return polygon

    except Exception as e:
        logger.error(f"Smoothing failed: {e}")
        return polygon


def _handle_antimeridian_crossing(lon):
    """
    Detect and handle antimeridian crossing in longitude data.

    When a flightline crosses the antimeridian (±180° longitude), coordinates
    can jump from ~179° to ~-179°, creating artificial longitude ranges of ~358°.
    This breaks polygon generation algorithms.

    Strategy: Convert to a continuous longitude range by adding 360° to negative
    longitudes when crossing is detected.

    Parameters:
    -----------
    lon : array-like
        Array of longitude values

    Returns:
    --------
    array : Processed longitude values
    """
    lon = np.array(lon)

    if len(lon) < 2:
        return lon

    # Detect potential antimeridian crossing
    lon_range = np.ptp(lon)  # Peak-to-peak (max - min)

    # If longitude range > 180°, likely antimeridian crossing
    if lon_range > 180:
        logger.info(f"Antimeridian crossing detected (range: {lon_range:.1f}°)")

        # Find the largest gap between consecutive longitudes
        lon_sorted_idx = np.argsort(lon)
        lon_sorted = lon[lon_sorted_idx]

        # Calculate gaps between consecutive sorted longitudes
        gaps = np.diff(lon_sorted)
        max_gap_idx = np.argmax(gaps)
        max_gap = gaps[max_gap_idx]

        # If the largest gap is > 180°, it's likely the antimeridian crossing
        if max_gap > 180:
            # Split point: longitude value after the largest gap
            split_lon = lon_sorted[max_gap_idx + 1]

            # Add 360° to all longitudes less than the split point
            # This creates a continuous longitude range
            adjusted_lon = lon.copy()
            adjusted_lon[lon < split_lon] += 360

            new_range = np.ptp(adjusted_lon)
            logger.debug(
                f"Adjusted longitude range: {new_range:.1f}° (split at {split_lon:.1f}°)"
            )

            return adjusted_lon
        else:
            # Large range but no clear crossing point - might be global data
            logger.warning(
                f"Large longitude range ({lon_range:.1f}°) but no clear antimeridian crossing"
            )
            return lon

    return lon


def _normalize_polygon_coordinates(polygon):
    """
    Normalize polygon coordinates to standard [-180, 180] longitude range.

    After antimeridian processing, polygon coordinates might be outside the
    standard longitude range (e.g., 270° instead of -90°). This function
    normalizes them back to [-180, 180] for proper GeoJSON output.

    Parameters:
    -----------
    polygon : shapely.geometry.Polygon
        Polygon with potentially unnormalized coordinates

    Returns:
    --------
    shapely.geometry.Polygon : Polygon with normalized coordinates
    """
    try:
        if not hasattr(polygon, "exterior"):
            return polygon

        # Get exterior coordinates
        coords = list(polygon.exterior.coords)

        # Normalize longitude coordinates
        normalized_coords = []
        for lon, lat in coords:
            # Normalize longitude to [-180, 180] range
            normalized_lon = ((lon + 180) % 360) - 180
            normalized_coords.append((normalized_lon, lat))

        # Create new polygon with normalized coordinates
        normalized_polygon = Polygon(normalized_coords)

        # Handle any interior holes (though rare for our use case)
        if polygon.interiors:
            holes = []
            for interior in polygon.interiors:
                hole_coords = []
                for lon, lat in interior.coords:
                    normalized_lon = ((lon + 180) % 360) - 180
                    hole_coords.append((normalized_lon, lat))
                holes.append(hole_coords)
            normalized_polygon = Polygon(normalized_coords, holes)

        return make_valid(normalized_polygon)

    except Exception as e:
        logger.error(f"Coordinate normalization failed: {e}")
        return polygon


def _ensure_counter_clockwise(polygon):
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
