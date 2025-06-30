#!/usr/bin/env python3
"""
Iterative polygon simplification algorithm optimized for CMR polygon replacement.

Goals:
1. 100% data coverage
2. Vertices <= CMR polygon vertices
3. Minimize non-data area
4. Area <= CMR polygon area
"""

import numpy as np
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
import geopandas as gpd


def calculate_polygon_metrics_v2(polygon, data_points=None, cmr_polygon=None):
    """
    Calculate metrics focused on our optimization goals.
    
    Args:
        polygon: Polygon to evaluate
        data_points: Array of (lon, lat) data points
        cmr_polygon: CMR polygon for comparison (optional)
        
    Returns:
        Dictionary of metrics
    """
    metrics = {}
    
    # Basic polygon properties
    metrics['area'] = polygon.area
    metrics['vertices'] = len(polygon.exterior.coords) - 1 if hasattr(polygon, 'exterior') else 0
    
    # Data coverage metrics
    if data_points is not None and len(data_points) > 0:
        # Sample if too many points
        if len(data_points) > 10000:
            indices = np.random.choice(len(data_points), 10000, replace=False)
            sample_points = data_points[indices]
        else:
            sample_points = data_points
        
        # Count points inside polygon
        points_inside = 0
        for point in sample_points:
            if polygon.contains(Point(point[0], point[1])):
                points_inside += 1
        
        metrics['data_coverage'] = points_inside / len(sample_points)
        metrics['points_covered'] = points_inside
        metrics['total_points'] = len(sample_points)
        
        # Estimate non-data area (area efficiency)
        # This is a rough estimate based on point density
        if points_inside > 0:
            # Estimate area covered by data points
            # Assuming uniform distribution within polygon
            data_density = points_inside / polygon.area if polygon.area > 0 else 0
            # Non-data area is inversely related to density
            metrics['non_data_area_ratio'] = max(0, 1 - min(1, data_density / 1000))
        else:
            metrics['non_data_area_ratio'] = 1.0
    else:
        metrics['data_coverage'] = 0
        metrics['non_data_area_ratio'] = 1.0
    
    # CMR comparison metrics
    if cmr_polygon is not None:
        metrics['cmr_area'] = cmr_polygon.area
        metrics['cmr_vertices'] = len(cmr_polygon.exterior.coords) - 1 if hasattr(cmr_polygon, 'exterior') else 0
        metrics['area_vs_cmr'] = metrics['area'] / metrics['cmr_area'] if metrics['cmr_area'] > 0 else float('inf')
        metrics['vertices_vs_cmr'] = metrics['vertices'] / metrics['cmr_vertices'] if metrics['cmr_vertices'] > 0 else float('inf')
        
        # IoU with CMR
        intersection = polygon.intersection(cmr_polygon)
        union = polygon.union(cmr_polygon)
        metrics['iou_with_cmr'] = intersection.area / union.area if union.area > 0 else 0
    
    return metrics


def iterative_simplify_v2(polygon, data_points, cmr_polygon=None, 
                         cmr_vertices=None, cmr_area=None,
                         require_full_coverage=True,
                         max_iterations=20):
    """
    Iteratively simplify polygon with strict optimization goals.
    
    Args:
        polygon: Input polygon to simplify
        data_points: Array of (lon, lat) data points
        cmr_polygon: CMR polygon for constraints (optional)
        cmr_vertices: Max vertices allowed (from CMR)
        cmr_area: Max area allowed (from CMR)
        require_full_coverage: If True, maintain 100% data coverage
        max_iterations: Maximum iterations
        
    Returns:
        Tuple of (best_polygon, history)
    """
    # Extract CMR constraints if polygon provided
    if cmr_polygon is not None:
        if cmr_vertices is None:
            cmr_vertices = len(cmr_polygon.exterior.coords) - 1 if hasattr(cmr_polygon, 'exterior') else None
        if cmr_area is None:
            cmr_area = cmr_polygon.area
    
    current_polygon = polygon
    history = []
    
    # Calculate initial metrics
    initial_metrics = calculate_polygon_metrics_v2(polygon, data_points, cmr_polygon)
    initial_metrics['iteration'] = 0
    initial_metrics['tolerance'] = 0
    initial_metrics['method'] = 'original'
    history.append(initial_metrics)
    
    print(f"\nOptimized Iterative Simplification")
    print(f"Initial: {initial_metrics['vertices']} vertices, {initial_metrics['area']:.6f}° area")
    print(f"Data coverage: {initial_metrics.get('data_coverage', 0):.1%}")
    if cmr_vertices:
        print(f"Target: <= {cmr_vertices} vertices")
    if cmr_area:
        print(f"Target: <= {cmr_area:.6f}° area")
    
    # Check if we already meet vertex constraint
    if cmr_vertices and initial_metrics['vertices'] <= cmr_vertices:
        print("Already meets vertex constraint!")
        return polygon, history
    
    best_polygon = polygon
    best_score = float('inf')  # Lower is better
    
    # Tolerance progression
    base_tolerance = 0.00001
    
    for iteration in range(1, max_iterations + 1):
        current_vertices = len(current_polygon.exterior.coords) - 1
        
        # Target vertices for this iteration
        if cmr_vertices and current_vertices > cmr_vertices:
            # Aim to get closer to CMR vertices
            target = max(cmr_vertices, current_vertices // 2)
        else:
            # Just halve vertices
            target = current_vertices // 2
        
        if target < 4:
            print(f"  Cannot reduce below 4 vertices")
            break
        
        print(f"\n  Iteration {iteration}: {current_vertices} → {target} vertices")
        
        # Try different tolerances
        found_valid = False
        tolerances = [base_tolerance * (2 ** i) for i in range(20)]
        
        for tolerance in tolerances:
            try:
                simplified = current_polygon.simplify(tolerance, preserve_topology=True)
                
                if not simplified.is_valid:
                    continue
                
                vertices = len(simplified.exterior.coords) - 1
                
                # Skip if didn't reduce vertices enough
                if vertices > target:
                    continue
                
                # Calculate metrics
                metrics = calculate_polygon_metrics_v2(simplified, data_points, cmr_polygon)
                metrics['iteration'] = iteration
                metrics['tolerance'] = tolerance
                metrics['method'] = 'simplify'
                
                # Check constraints
                constraints_met = True
                
                # 1. Data coverage constraint
                if require_full_coverage and metrics['data_coverage'] < 1.0:
                    constraints_met = False
                
                # 2. Vertex constraint
                if cmr_vertices and metrics['vertices'] > cmr_vertices:
                    constraints_met = False
                
                # 3. Area constraint
                if cmr_area and metrics['area'] > cmr_area:
                    constraints_met = False
                
                if constraints_met:
                    # Calculate optimization score (lower is better)
                    # Prioritize: fewer vertices, less non-data area
                    score = (
                        metrics['vertices'] * 0.3 +  # Fewer vertices is better
                        metrics['non_data_area_ratio'] * 100 * 0.7  # Less non-data area is better
                    )
                    
                    print(f"    Tolerance {tolerance:.6f}: {vertices} vertices, "
                          f"coverage={metrics['data_coverage']:.1%}, "
                          f"area={metrics['area']:.6f}°, score={score:.2f}")
                    
                    history.append(metrics)
                    
                    if score < best_score:
                        best_score = score
                        best_polygon = simplified
                    
                    current_polygon = simplified
                    found_valid = True
                    break
                    
            except Exception as e:
                continue
        
        if not found_valid:
            print(f"    No valid simplification found at this level")
            break
    
    # Final check - if we still don't meet constraints, try more aggressive simplification
    final_metrics = calculate_polygon_metrics_v2(best_polygon, data_points, cmr_polygon)
    
    if cmr_vertices and final_metrics['vertices'] > cmr_vertices:
        print(f"\nTrying aggressive simplification to reach {cmr_vertices} vertices...")
        
        # Use convex hull as last resort
        points = np.array(best_polygon.exterior.coords[:-1])
        if len(points) > cmr_vertices:
            # Sample points to create simpler polygon
            indices = np.linspace(0, len(points)-1, cmr_vertices, dtype=int)
            sampled_points = points[indices]
            
            try:
                simple_polygon = Polygon(sampled_points)
                if simple_polygon.is_valid:
                    metrics = calculate_polygon_metrics_v2(simple_polygon, data_points, cmr_polygon)
                    metrics['iteration'] = len(history)
                    metrics['method'] = 'aggressive_sample'
                    
                    # Only use if it maintains full coverage
                    if not require_full_coverage or metrics['data_coverage'] >= 1.0:
                        history.append(metrics)
                        best_polygon = simple_polygon
                        print(f"  Achieved {metrics['vertices']} vertices with aggressive sampling")
            except:
                pass
    
    return best_polygon, history


def optimize_polygon_for_cmr(polygon, data_points, cmr_polygon):
    """
    Optimize a polygon to replace CMR polygon while meeting all constraints.
    
    This is the main entry point for polygon optimization.
    
    Args:
        polygon: Generated polygon to optimize
        data_points: Array of (lon, lat) data points
        cmr_polygon: Current CMR polygon to replace
        
    Returns:
        Tuple of (optimized_polygon, metrics)
    """
    # Get CMR constraints
    cmr_vertices = len(cmr_polygon.exterior.coords) - 1 if hasattr(cmr_polygon, 'exterior') else None
    cmr_area = cmr_polygon.area
    
    print(f"\nOptimizing polygon to replace CMR polygon")
    print(f"CMR: {cmr_vertices} vertices, {cmr_area:.6f}° area")
    
    # First ensure we have full data coverage
    initial_metrics = calculate_polygon_metrics_v2(polygon, data_points, cmr_polygon)
    
    if initial_metrics['data_coverage'] < 1.0:
        print(f"Warning: Initial polygon only covers {initial_metrics['data_coverage']:.1%} of data!")
        print("Consider using a larger buffer or different generation method.")
    
    # Run optimization
    optimized, history = iterative_simplify_v2(
        polygon, 
        data_points,
        cmr_polygon=cmr_polygon,
        cmr_vertices=cmr_vertices,
        cmr_area=cmr_area,
        require_full_coverage=True
    )
    
    # Get final metrics
    final_metrics = history[-1] if history else initial_metrics
    
    print(f"\nOptimization complete:")
    print(f"  Vertices: {initial_metrics['vertices']} → {final_metrics['vertices']}")
    print(f"  Area: {initial_metrics['area']:.6f}° → {final_metrics['area']:.6f}°")
    print(f"  Data coverage: {final_metrics['data_coverage']:.1%}")
    print(f"  Non-data area ratio: {final_metrics['non_data_area_ratio']:.1%}")
    
    # Validation
    if final_metrics['vertices'] <= cmr_vertices:
        print(f"  ✓ Meets vertex constraint (<= {cmr_vertices})")
    else:
        print(f"  ✗ Exceeds vertex constraint ({final_metrics['vertices']} > {cmr_vertices})")
    
    if final_metrics['area'] <= cmr_area:
        print(f"  ✓ Meets area constraint (<= {cmr_area:.6f}°)")
    else:
        print(f"  ✗ Exceeds area constraint ({final_metrics['area']:.6f}° > {cmr_area:.6f}°)")
    
    if final_metrics['data_coverage'] >= 1.0:
        print(f"  ✓ Full data coverage")
    else:
        print(f"  ✗ Incomplete data coverage ({final_metrics['data_coverage']:.1%})")
    
    return optimized, final_metrics