#!/usr/bin/env python3
"""
Iterative polygon simplification algorithm that halves vertices while monitoring fit quality.
"""

import numpy as np
from shapely.geometry import Point, Polygon
from scipy.spatial import cKDTree


def calculate_non_data_coverage(polygon, data_points, num_samples=1000):
    """
    Calculate the percentage of the polygon area that contains no data.
    
    Args:
        polygon: Shapely polygon
        data_points: Array of [lon, lat] data points
        num_samples: Number of random points to sample within polygon
    
    Returns:
        float: Non-data coverage ratio (0.0 = no non-data area, 1.0 = all non-data)
    """
    if not hasattr(polygon, 'bounds') or len(data_points) == 0:
        return 0.0
    
    # Build KDTree for efficient nearest neighbor search
    data_tree = cKDTree(data_points)
    
    # Calculate adaptive radius based on data density
    data_bounds = np.array(data_points)
    min_lon, min_lat = data_bounds.min(axis=0)
    max_lon, max_lat = data_bounds.max(axis=0)
    
    # Use smaller dimension of bounding box for radius calculation
    width = max_lon - min_lon
    height = max_lat - min_lat
    smaller_dimension = min(width, height)
    
    # Set radius as 1% of smaller dimension (tighter than comparison method)
    adaptive_radius = smaller_dimension * 0.01
    
    # Get polygon bounds
    minx, miny, maxx, maxy = polygon.bounds
    
    # Generate random points within polygon bounds
    random_points = []
    attempts = 0
    max_attempts = num_samples * 10
    
    while len(random_points) < num_samples and attempts < max_attempts:
        attempts += 1
        # Random point in bounding box
        rx = np.random.uniform(minx, maxx)
        ry = np.random.uniform(miny, maxy)
        pt = Point(rx, ry)
        
        # Check if point is inside polygon
        if polygon.contains(pt):
            random_points.append([rx, ry])
    
    if len(random_points) == 0:
        return 0.0
    
    # Check each random point for nearby data
    points_with_data = 0
    for rp in random_points:
        # Find points within neighborhood
        nearby_indices = data_tree.query_ball_point(rp, adaptive_radius)
        if len(nearby_indices) > 0:
            points_with_data += 1
    
    # Non-data coverage is proportion of points without nearby data
    data_coverage = points_with_data / len(random_points)
    non_data_coverage = 1.0 - data_coverage
    
    return non_data_coverage


def calculate_polygon_fit_metrics(
    original_polygon, simplified_polygon, data_points=None
):
    """
    Calculate metrics to evaluate how well a simplified polygon fits the original.

    Args:
        original_polygon: Original (complex) polygon
        simplified_polygon: Simplified polygon
        data_points: Optional array of original data points to check coverage

    Returns:
        Dictionary of fit metrics
    """
    # Area-based metrics
    orig_area = original_polygon.area
    simp_area = simplified_polygon.area
    area_ratio = simp_area / orig_area if orig_area > 0 else 0

    # Area overlap metrics (kept for geometric analysis)
    intersection = original_polygon.intersection(simplified_polygon)
    union = original_polygon.union(simplified_polygon)
    iou = intersection.area / union.area if union.area > 0 else 0

    # Hausdorff distance (maximum distance between boundaries)
    try:
        hausdorff_dist = original_polygon.hausdorff_distance(simplified_polygon)
    except Exception:
        hausdorff_dist = float("inf")

    # Coverage of original data points (if provided)
    data_coverage = 1.0
    if data_points is not None and len(data_points) > 0:
        # Sample points if too many
        if len(data_points) > 1000:
            indices = np.random.choice(len(data_points), 1000, replace=False)
            sample_points = data_points[indices]
        else:
            sample_points = data_points

        # Check how many points are still inside simplified polygon
        # First check if any points were inside the original polygon
        original_inside = 0
        for point in sample_points:
            if original_polygon.contains(Point(point)):
                original_inside += 1

        if original_inside > 0:
            # Check how many of those are still inside simplified polygon
            points_inside = 0
            for point in sample_points:
                if original_polygon.contains(
                    Point(point)
                ) and simplified_polygon.contains(Point(point)):
                    points_inside += 1
            data_coverage = points_inside / original_inside
        else:
            # If no points were inside original, use area-based coverage
            data_coverage = (
                min(1.0, simplified_polygon.area / original_polygon.area)
                if original_polygon.area > 0
                else 1.0
            )

    # Vertex counts
    orig_vertices = (
        len(original_polygon.exterior.coords) - 1
        if hasattr(original_polygon, "exterior")
        else 0
    )
    simp_vertices = (
        len(simplified_polygon.exterior.coords) - 1
        if hasattr(simplified_polygon, "exterior")
        else 0
    )

    # Calculate non-data coverage for the simplified polygon
    non_data_coverage = 0.0
    if data_points is not None and len(data_points) > 0:
        non_data_coverage = calculate_non_data_coverage(simplified_polygon, data_points)

    return {
        "area_ratio": area_ratio,
        "iou": iou,
        "hausdorff_distance": hausdorff_dist,
        "data_coverage": data_coverage,
        "non_data_coverage": non_data_coverage,
        "original_vertices": orig_vertices,
        "simplified_vertices": simp_vertices,
        "vertex_reduction": 1 - (simp_vertices / orig_vertices)
        if orig_vertices > 0
        else 0,
    }


def iterative_simplify_polygon(
    polygon,
    data_points=None,
    target_vertices=None,
    min_coverage=0.90,
    max_non_data_coverage=0.15,  # New constraint: max 15% non-data area
    max_iterations=15,
):
    """
    Iteratively simplify a polygon by halving vertices, stopping when quality degrades.

    Args:
        polygon: Input polygon to simplify
        data_points: Original data points (for coverage checking)
        target_vertices: Optional target vertex count
        min_coverage: Minimum data coverage to maintain (default: 0.90)
        max_non_data_coverage: Maximum non-data coverage allowed (default: 0.15)
        max_iterations: Maximum iterations (default: 15)

    Returns:
        Tuple of (best_polygon, simplification_history)
    """
    if not hasattr(polygon, "exterior"):
        return polygon, []

    current_polygon = polygon
    current_vertices = len(polygon.exterior.coords) - 1
    history = []

    # Initial metrics
    initial_metrics = calculate_polygon_fit_metrics(polygon, polygon, data_points)
    initial_metrics["iteration"] = 0
    initial_metrics["tolerance"] = 0
    initial_metrics["vertices"] = current_vertices  # Add vertices key for compatibility
    history.append(initial_metrics)

    print(f"\nIterative simplification starting with {current_vertices} vertices")
    print(
        f"Target: {'halve vertices each iteration' if target_vertices is None else f'{target_vertices} vertices'}"
    )
    print(f"Constraints: Coverage >= {min_coverage:.2f}, Non-data <= {max_non_data_coverage:.1%}")

    # Tolerance progression - start small and increase
    base_tolerance = 0.00001

    # Cache to avoid retrying same tolerance values
    tolerance_cache = {}

    for iteration in range(1, max_iterations + 1):
        # CONSERVATIVE reduction strategy - prioritize coverage over vertex reduction
        if target_vertices:
            # Be more conservative - take smaller steps to preserve coverage
            if current_vertices > target_vertices * 3:
                target = max(target_vertices * 2, current_vertices * 2 // 3)  # Reduce by 1/3 instead of 1/2
            elif current_vertices > target_vertices * 1.5:
                target = max(target_vertices, current_vertices * 3 // 4)  # Reduce by 1/4
            else:
                target = target_vertices  # Go directly to target
        else:
            # Default: reduce by 1/3 instead of halving to preserve coverage
            target = current_vertices * 2 // 3

        # Stop if we're already at or below minimum viable vertices
        if target < 4:
            print(f"  Iteration {iteration}: Cannot reduce below 4 vertices")
            break

        print(f"\n  Iteration {iteration}: {current_vertices} → {target} vertices")

        # Try different tolerances to achieve target
        best_polygon = current_polygon
        best_metrics = None

        # Exponentially increase tolerance search range - more aggressive
        tolerances = [base_tolerance * (2**i) for i in range(20)]

        for tol in tolerances:
            # Skip if we've already tried this tolerance
            tol_key = f"{current_vertices}_{tol:.10f}"
            if tol_key in tolerance_cache:
                continue

            try:
                simplified = current_polygon.simplify(tol, preserve_topology=True)
                tolerance_cache[tol_key] = simplified

                if not hasattr(simplified, "exterior"):
                    continue

                vertices = len(simplified.exterior.coords) - 1

                # More flexible vertex count checking
                if vertices <= target or (
                    target_vertices and vertices <= target_vertices
                ):
                    metrics = calculate_polygon_fit_metrics(
                        polygon, simplified, data_points
                    )
                    metrics["iteration"] = iteration
                    metrics["tolerance"] = tol
                    metrics["vertices"] = vertices  # Add vertices key for compatibility

                    # Check quality constraints - PRIORITIZE DATA COVERAGE FIRST
                    # If data coverage is excellent (99%+), relax non-data constraint
                    non_data_limit = max_non_data_coverage
                    if metrics["data_coverage"] >= 0.99:
                        non_data_limit = min(0.35, max_non_data_coverage * 1.5)  # Allow more non-data if coverage is excellent
                    
                    if (metrics["data_coverage"] >= min_coverage and 
                        metrics["non_data_coverage"] <= non_data_limit):
                        # Accept this simplification using multi-objective scoring
                        if best_metrics is None:
                            best_polygon = simplified
                            best_metrics = metrics
                        else:
                            # PRIORITIZE DATA COVERAGE: Calculate scores with data coverage emphasis
                            current_score = (metrics["data_coverage"] * 0.8 + 
                                           (1.0 - metrics["non_data_coverage"]) * 0.2)
                            best_score = (best_metrics["data_coverage"] * 0.8 + 
                                        (1.0 - best_metrics["non_data_coverage"]) * 0.2)
                            
                            # Accept if better data coverage, or similar coverage with better overall score
                            if (metrics["data_coverage"] > best_metrics["data_coverage"] + 0.005 or  # Better data coverage
                                (abs(metrics["data_coverage"] - best_metrics["data_coverage"]) < 0.005 and 
                                 current_score > best_score)):
                                best_polygon = simplified
                                best_metrics = metrics

                        # Continue searching but be less aggressive about vertex reduction
                        if vertices == target or (
                            target_vertices and vertices <= target_vertices
                        ):
                            continue  # Keep searching but prioritize coverage
                    else:
                        # Quality dropped too much
                        if best_metrics is None and vertices <= target:
                            print(
                                f"    Tolerance {tol:.6f}: {vertices} vertices - "
                                f"REJECTED (Coverage={metrics['data_coverage']:.3f}, Non-data={metrics['non_data_coverage']:.3f})"
                            )

            except Exception:
                continue

        # Check if we found a valid simplification
        if best_metrics is None:
            print("    No valid simplification found - stopping")
            break

        # Update current polygon and report
        current_polygon = best_polygon
        current_vertices = best_metrics["simplified_vertices"]
        history.append(best_metrics)

        print(
            f"    Success: {best_metrics['original_vertices']} → {current_vertices} vertices"
        )
        print(
            f"    Quality: Coverage={best_metrics['data_coverage']:.3f}, "
            f"Non-data={best_metrics['non_data_coverage']:.3f}, "
            f"Area ratio={best_metrics['area_ratio']:.3f}"
        )

        # Check if we've reached our target OR achieved excellent coverage
        if target_vertices and current_vertices <= target_vertices:
            print(f"  Reached target of {target_vertices} vertices")
            break
        
        # PRIORITIZE DATA COVERAGE: Stop early if we have excellent data coverage
        if (best_metrics["data_coverage"] >= 0.995 and 
            current_vertices <= target_vertices * 1.5):
            print(f"  Stopping early: Excellent data coverage ({best_metrics['data_coverage']:.1%}) achieved")
            break

        # Update base tolerance for next iteration - be more aggressive
        base_tolerance = best_metrics["tolerance"] * 1.5

    # Find best result from history
    # PRIORITIZE: data coverage first, then vertex reduction
    best_score = -1
    best_result = polygon
    best_iteration = 0

    for i, metrics in enumerate(history[1:], 1):  # Skip initial
        # REBALANCED: Prioritize data coverage (70%) over non-data minimization (15%) and vertex reduction (15%)
        data_coverage_score = metrics["data_coverage"] * 0.7
        non_data_score = (1.0 - metrics["non_data_coverage"]) * 0.15  # Reduced weight
        vertex_score = metrics["vertex_reduction"] * 0.15
        
        score = data_coverage_score + non_data_score + vertex_score
        
        # Strong bonus for excellent data coverage (99%+)
        if metrics["data_coverage"] >= 0.99:
            score += 0.2
        elif metrics["data_coverage"] >= 0.98:
            score += 0.1
        
        # Smaller bonus for low non-data coverage (only if data coverage is good)
        if metrics["data_coverage"] >= 0.98 and metrics["non_data_coverage"] <= 0.10:
            score += 0.05
        
        # Strong penalty for cutting off data
        if metrics["data_coverage"] < 0.98:
            score -= 0.3
        
        # Penalty for very low data coverage
        if metrics["data_coverage"] < min_coverage + 0.02:
            score -= 0.5

        if score > best_score:
            best_score = score
            best_iteration = i

    # Get the polygon from the best iteration
    if best_iteration > 0:
        # Recreate the best polygon
        tol = history[best_iteration]["tolerance"]
        best_result = polygon.simplify(tol, preserve_topology=True)

    print(
        f"\nBest result: Iteration {best_iteration} with {history[best_iteration]['simplified_vertices']} vertices"
    )

    return best_result, history


def simplify_to_match_cmr(polygon, cmr_polygon, data_points=None, cmr_weight=0.5):
    """
    Simplify polygon to best match a CMR reference polygon.

    Args:
        polygon: Polygon to simplify
        cmr_polygon: Target CMR polygon to match
        data_points: Original data points
        cmr_weight: Weight for CMR matching vs data coverage (0-1)

    Returns:
        Simplified polygon that best matches CMR
    """
    # Get CMR characteristics
    cmr_vertices = (
        len(cmr_polygon.exterior.coords) - 1 if hasattr(cmr_polygon, "exterior") else 10
    )

    print(f"\nSimplifying to match CMR polygon ({cmr_vertices} vertices)")

    # Run iterative simplification targeting CMR vertex count
    simplified, history = iterative_simplify_polygon(
        polygon,
        data_points=data_points,
        target_vertices=cmr_vertices,
        min_coverage=0.80,  # Lower threshold when matching CMR
    )

    # Calculate data coverage of final result
    if data_points is not None and len(data_points) > 0:
        from shapely.geometry import Point

        covered_points = sum(
            1 for point in data_points if simplified.contains(Point(point))
        )
        coverage = covered_points / len(data_points)
        print(f"Final data coverage: {coverage:.1%}")
    else:
        print("Final simplification complete")

    return simplified


# Integration with visualize_flightline.py
def add_iterative_simplification_to_polygon_creation(original_function):
    """
    Decorator to add iterative simplification to polygon creation.
    """

    def wrapper(
        lon,
        lat,
        method="convex",
        alpha=2.0,
        buffer_m=1500,
        concave_ratio=0.3,
        iterative_simplify=False,
        target_vertices=None,
    ):
        # Create initial polygon
        polygon = original_function(lon, lat, method, alpha, buffer_m, concave_ratio)

        # Apply iterative simplification if requested
        if iterative_simplify and hasattr(polygon, "exterior"):
            print("\nApplying iterative simplification...")

            # Prepare data points
            mask = ~(np.isnan(lon) | np.isnan(lat))
            data_points = np.column_stack([lon[mask], lat[mask]])

            # Simplify
            polygon, history = iterative_simplify_polygon(
                polygon,
                data_points=data_points,
                target_vertices=target_vertices,
            )

            # Print summary
            if history:
                print("\nSimplification summary:")
                print(f"  Original: {history[0]['original_vertices']} vertices")
                print(f"  Final: {history[-1]['simplified_vertices']} vertices")
                print(f"  Reduction: {history[-1]['vertex_reduction']:.1%}")
                print(f"  Final coverage: {history[-1]['data_coverage']:.3f}")

        return polygon

    return wrapper


if __name__ == "__main__":
    # Test the algorithm
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MplPolygon

    # Create a test polygon with many vertices
    theta = np.linspace(0, 2 * np.pi, 1000)
    r = 1 + 0.3 * np.sin(5 * theta) + 0.1 * np.sin(15 * theta)
    x = r * np.cos(theta)
    y = r * np.sin(theta)

    # Create polygon
    coords = list(zip(x, y))
    original_polygon = Polygon(coords)

    # Generate some data points inside
    data_points = []
    for _ in range(500):
        angle = np.random.uniform(0, 2 * np.pi)
        radius = np.random.uniform(0, 0.9)
        px = radius * np.cos(angle)
        py = radius * np.sin(angle)
        data_points.append([px, py])
    data_points = np.array(data_points)

    # Run iterative simplification
    simplified, history = iterative_simplify_polygon(
        original_polygon, data_points=data_points, target_vertices=20
    )

    # Plot results
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Original
    ax1.add_patch(
        MplPolygon(
            original_polygon.exterior.coords, fill=False, edgecolor="blue", linewidth=2
        )
    )
    ax1.scatter(data_points[:, 0], data_points[:, 1], c="red", s=5, alpha=0.5)
    ax1.set_title(f"Original ({len(original_polygon.exterior.coords)-1} vertices)")
    ax1.set_aspect("equal")
    ax1.grid(True, alpha=0.3)

    # Simplified
    ax2.add_patch(
        MplPolygon(
            simplified.exterior.coords, fill=False, edgecolor="green", linewidth=2
        )
    )
    ax2.scatter(data_points[:, 0], data_points[:, 1], c="red", s=5, alpha=0.5)
    ax2.set_title(f"Simplified ({len(simplified.exterior.coords)-1} vertices)")
    ax2.set_aspect("equal")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig("iterative_simplification_test.png", dpi=150)
    print("\nTest plot saved to: iterative_simplification_test.png")

    # Print history
    print("\nSimplification history:")
    print(
        f"{'Iter':<5} {'Vertices':<10} {'Coverage':<10} {'Area Ratio':<12} {'Quality':<8}"
    )
    print("-" * 50)
    for h in history:
        print(
            f"{h['iteration']:<5} {h['simplified_vertices']:<10} "
            f"{h['data_coverage']:<10.3f} {h['area_ratio']:<12.3f} {h['iou']:<8.3f}"
        )
