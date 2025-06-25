#!/usr/bin/env python3
"""
Iterative polygon simplification algorithm that halves vertices while monitoring fit quality.
"""

import numpy as np
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
import geopandas as gpd


def calculate_polygon_fit_metrics(original_polygon, simplified_polygon, data_points=None):
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
    
    # Intersection over Union (IoU)
    intersection = original_polygon.intersection(simplified_polygon)
    union = original_polygon.union(simplified_polygon)
    iou = intersection.area / union.area if union.area > 0 else 0
    
    # Hausdorff distance (maximum distance between boundaries)
    try:
        hausdorff_dist = original_polygon.hausdorff_distance(simplified_polygon)
    except:
        hausdorff_dist = float('inf')
    
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
                if original_polygon.contains(Point(point)) and simplified_polygon.contains(Point(point)):
                    points_inside += 1
            data_coverage = points_inside / original_inside
        else:
            # If no points were inside original, use area-based coverage
            data_coverage = min(1.0, simplified_polygon.area / original_polygon.area) if original_polygon.area > 0 else 1.0
    
    # Vertex counts
    orig_vertices = len(original_polygon.exterior.coords) - 1 if hasattr(original_polygon, 'exterior') else 0
    simp_vertices = len(simplified_polygon.exterior.coords) - 1 if hasattr(simplified_polygon, 'exterior') else 0
    
    return {
        'area_ratio': area_ratio,
        'iou': iou,
        'hausdorff_distance': hausdorff_dist,
        'data_coverage': data_coverage,
        'original_vertices': orig_vertices,
        'simplified_vertices': simp_vertices,
        'vertex_reduction': 1 - (simp_vertices / orig_vertices) if orig_vertices > 0 else 0
    }


def iterative_simplify_polygon(polygon, data_points=None, target_vertices=None, 
                             min_iou=0.85, min_coverage=0.90, max_iterations=10):
    """
    Iteratively simplify a polygon by halving vertices, stopping when quality degrades.
    
    Args:
        polygon: Input polygon to simplify
        data_points: Original data points (for coverage checking)
        target_vertices: Optional target vertex count
        min_iou: Minimum IoU to maintain (default: 0.85)
        min_coverage: Minimum data coverage to maintain (default: 0.90)
        max_iterations: Maximum iterations (default: 10)
        
    Returns:
        Tuple of (best_polygon, simplification_history)
    """
    if not hasattr(polygon, 'exterior'):
        return polygon, []
    
    current_polygon = polygon
    current_vertices = len(polygon.exterior.coords) - 1
    history = []
    
    # Initial metrics
    initial_metrics = calculate_polygon_fit_metrics(polygon, polygon, data_points)
    initial_metrics['iteration'] = 0
    initial_metrics['tolerance'] = 0
    history.append(initial_metrics)
    
    print(f"\nIterative simplification starting with {current_vertices} vertices")
    print(f"Target: {'halve vertices each iteration' if target_vertices is None else f'{target_vertices} vertices'}")
    print(f"Constraints: IoU >= {min_iou:.2f}, Coverage >= {min_coverage:.2f}")
    
    # Tolerance progression - start small and increase
    base_tolerance = 0.00001
    
    for iteration in range(1, max_iterations + 1):
        # Target is to halve the vertices
        target = current_vertices // 2
        
        # If we have a specific target and we're close, aim for that
        if target_vertices and current_vertices > target_vertices:
            target = max(target_vertices, target)
        
        # Stop if we're already at or below minimum viable vertices
        if target < 4:
            print(f"  Iteration {iteration}: Cannot reduce below 4 vertices")
            break
        
        print(f"\n  Iteration {iteration}: {current_vertices} → {target} vertices")
        
        # Try different tolerances to achieve target
        best_polygon = current_polygon
        best_metrics = None
        
        # Exponentially increase tolerance search range
        tolerances = [base_tolerance * (2 ** i) for i in range(15)]
        
        for tol in tolerances:
            try:
                simplified = current_polygon.simplify(tol, preserve_topology=True)
                
                if not hasattr(simplified, 'exterior'):
                    continue
                
                vertices = len(simplified.exterior.coords) - 1
                
                # Check if we're close to target
                if vertices <= target:
                    metrics = calculate_polygon_fit_metrics(polygon, simplified, data_points)
                    metrics['iteration'] = iteration
                    metrics['tolerance'] = tol
                    
                    # Check quality constraints
                    if metrics['iou'] >= min_iou and metrics['data_coverage'] >= min_coverage:
                        best_polygon = simplified
                        best_metrics = metrics
                        
                        # If we hit our exact target, stop searching
                        if vertices == target or (target_vertices and vertices == target_vertices):
                            break
                    else:
                        # Quality dropped too much, stop this iteration
                        if best_metrics is None:
                            print(f"    Tolerance {tol:.6f}: {vertices} vertices - "
                                  f"REJECTED (IoU={metrics['iou']:.3f}, Coverage={metrics['data_coverage']:.3f})")
                        break
                        
            except Exception as e:
                continue
        
        # Check if we found a valid simplification
        if best_metrics is None:
            print(f"    No valid simplification found - stopping")
            break
        
        # Update current polygon and report
        current_polygon = best_polygon
        current_vertices = best_metrics['simplified_vertices']
        history.append(best_metrics)
        
        print(f"    Success: {best_metrics['original_vertices']} → {current_vertices} vertices")
        print(f"    Quality: IoU={best_metrics['iou']:.3f}, Coverage={best_metrics['data_coverage']:.3f}, "
              f"Area ratio={best_metrics['area_ratio']:.3f}")
        
        # Check if we've reached our target
        if target_vertices and current_vertices <= target_vertices:
            print(f"  Reached target of {target_vertices} vertices")
            break
        
        # Update base tolerance for next iteration
        base_tolerance = best_metrics['tolerance']
    
    # Find best result from history
    # Prefer: high IoU, high coverage, but also significant simplification
    best_score = -1
    best_result = polygon
    best_iteration = 0
    
    for i, metrics in enumerate(history[1:], 1):  # Skip initial
        # Weighted score: balance quality and simplification
        score = (metrics['iou'] * 0.4 + 
                metrics['data_coverage'] * 0.3 + 
                metrics['vertex_reduction'] * 0.3)
        
        if score > best_score:
            best_score = score
            best_iteration = i
    
    # Get the polygon from the best iteration
    if best_iteration > 0:
        # Recreate the best polygon
        tol = history[best_iteration]['tolerance']
        best_result = polygon.simplify(tol, preserve_topology=True)
    
    print(f"\nBest result: Iteration {best_iteration} with {history[best_iteration]['simplified_vertices']} vertices")
    
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
    cmr_vertices = len(cmr_polygon.exterior.coords) - 1 if hasattr(cmr_polygon, 'exterior') else 10
    
    print(f"\nSimplifying to match CMR polygon ({cmr_vertices} vertices)")
    
    # Run iterative simplification targeting CMR vertex count
    simplified, history = iterative_simplify_polygon(
        polygon, 
        data_points=data_points,
        target_vertices=cmr_vertices,
        min_iou=0.7,  # Lower threshold when matching CMR
        min_coverage=0.85
    )
    
    # Calculate match with CMR
    cmr_iou = (cmr_polygon.intersection(simplified).area / 
               cmr_polygon.union(simplified).area) if cmr_polygon.area > 0 else 0
    
    print(f"Final CMR match: IoU={cmr_iou:.3f}")
    
    return simplified


# Integration with visualize_flightline.py
def add_iterative_simplification_to_polygon_creation(original_function):
    """
    Decorator to add iterative simplification to polygon creation.
    """
    def wrapper(lon, lat, method='convex', alpha=2.0, buffer_m=1500, concave_ratio=0.3,
                iterative_simplify=False, target_vertices=None, min_iou=0.85):
        
        # Create initial polygon
        polygon = original_function(lon, lat, method, alpha, buffer_m, concave_ratio)
        
        # Apply iterative simplification if requested
        if iterative_simplify and hasattr(polygon, 'exterior'):
            print("\nApplying iterative simplification...")
            
            # Prepare data points
            mask = ~(np.isnan(lon) | np.isnan(lat))
            data_points = np.column_stack([lon[mask], lat[mask]])
            
            # Simplify
            polygon, history = iterative_simplify_polygon(
                polygon,
                data_points=data_points,
                target_vertices=target_vertices,
                min_iou=min_iou
            )
            
            # Print summary
            if history:
                print(f"\nSimplification summary:")
                print(f"  Original: {history[0]['original_vertices']} vertices")
                print(f"  Final: {history[-1]['simplified_vertices']} vertices")
                print(f"  Reduction: {history[-1]['vertex_reduction']:.1%}")
                print(f"  Final IoU: {history[-1]['iou']:.3f}")
        
        return polygon
    
    return wrapper


if __name__ == "__main__":
    # Test the algorithm
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon as MplPolygon
    
    # Create a test polygon with many vertices
    theta = np.linspace(0, 2*np.pi, 1000)
    r = 1 + 0.3 * np.sin(5*theta) + 0.1 * np.sin(15*theta)
    x = r * np.cos(theta)
    y = r * np.sin(theta)
    
    # Create polygon
    coords = list(zip(x, y))
    original_polygon = Polygon(coords)
    
    # Generate some data points inside
    data_points = []
    for _ in range(500):
        angle = np.random.uniform(0, 2*np.pi)
        radius = np.random.uniform(0, 0.9)
        px = radius * np.cos(angle)
        py = radius * np.sin(angle)
        data_points.append([px, py])
    data_points = np.array(data_points)
    
    # Run iterative simplification
    simplified, history = iterative_simplify_polygon(
        original_polygon,
        data_points=data_points,
        target_vertices=20
    )
    
    # Plot results
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    
    # Original
    ax1.add_patch(MplPolygon(original_polygon.exterior.coords, 
                            fill=False, edgecolor='blue', linewidth=2))
    ax1.scatter(data_points[:, 0], data_points[:, 1], c='red', s=5, alpha=0.5)
    ax1.set_title(f'Original ({len(original_polygon.exterior.coords)-1} vertices)')
    ax1.set_aspect('equal')
    ax1.grid(True, alpha=0.3)
    
    # Simplified
    ax2.add_patch(MplPolygon(simplified.exterior.coords, 
                            fill=False, edgecolor='green', linewidth=2))
    ax2.scatter(data_points[:, 0], data_points[:, 1], c='red', s=5, alpha=0.5)
    ax2.set_title(f'Simplified ({len(simplified.exterior.coords)-1} vertices)')
    ax2.set_aspect('equal')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('iterative_simplification_test.png', dpi=150)
    print(f"\nTest plot saved to: iterative_simplification_test.png")
    
    # Print history
    print("\nSimplification history:")
    print(f"{'Iter':<5} {'Vertices':<10} {'IoU':<8} {'Coverage':<10} {'Area Ratio':<12}")
    print("-" * 50)
    for h in history:
        print(f"{h['iteration']:<5} {h['simplified_vertices']:<10} "
              f"{h['iou']:<8.3f} {h['data_coverage']:<10.3f} {h['area_ratio']:<12.3f}")