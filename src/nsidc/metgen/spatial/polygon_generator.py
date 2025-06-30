"""
Polygon Generation Module for LVIS Flightline Processing

This module consolidates all polygon generation, adaptive buffer sizing,
and iterative simplification functionality.
"""

import numpy as np
import warnings
from scipy.spatial import Delaunay
from scipy.interpolate import UnivariateSpline
from shapely.geometry import Polygon, MultiPolygon, Point, LineString
from shapely.ops import unary_union
import pyproj
from shapely.validation import make_valid
from shapely.algorithms.polylabel import polylabel
from scipy.spatial.distance import cdist
from .simplification import optimize_polygon_for_cmr


class PolygonGenerator:
    """Main class for polygon generation with various methods."""
    
    def __init__(self):
        """Initialize the polygon generator."""
        self.default_buffer = 300  # meters
        self.min_buffer = 200
        self.max_buffer = 1000
        
    def create_flightline_polygon(self, lon, lat, method='adaptive_beam', 
                                 buffer_distance=None, alpha=0.5, 
                                 concave_ratio=0.2, max_points=None,
                                 iterative_simplify=False, target_vertices=None,
                                 min_iou=0.85, min_coverage=0.90):
        """
        Create a polygon representing the flightline coverage.
        
        Parameters:
        -----------
        lon, lat : array-like
            Longitude and latitude coordinates
        method : str
            Method to use: 'convex', 'concave', 'alpha', 'buffer', 
            'centerline', 'beam', 'adaptive_beam'
        buffer_distance : float
            Buffer distance in meters (if None, uses adaptive sizing)
        alpha : float
            Alpha parameter for alpha shapes
        concave_ratio : float
            Ratio for concave hull (0-1, lower = more concave)
        max_points : int
            Maximum vertices in final polygon
        iterative_simplify : bool
            Whether to use iterative simplification
        target_vertices : int
            Target number of vertices for iterative simplification
        min_iou : float
            Minimum IoU for iterative simplification
        min_coverage : float
            Minimum data coverage for iterative simplification
            
        Returns:
        --------
        polygon : shapely.geometry.Polygon
            The generated polygon
        metadata : dict
            Metadata about the generation process
        """
        # Filter out invalid coordinates
        mask = np.isfinite(lon) & np.isfinite(lat)
        lon = np.array(lon)[mask]
        lat = np.array(lat)[mask]
        
        if len(lon) < 3:
            raise ValueError("Insufficient valid coordinates")
        
        metadata = {
            'method': method,
            'points': len(lon),
            'original_buffer': buffer_distance
        }
        
        # Create points
        points = np.column_stack((lon, lat))
        
        # Handle different methods
        if method == 'convex':
            polygon = self._create_convex_hull(points)
            
        elif method == 'concave':
            polygon = self.create_concave_hull(points, concave_ratio)
            
        elif method == 'alpha':
            polygon = self.create_alpha_shape(points, alpha)
            
        elif method == 'buffer':
            if buffer_distance is None:
                buffer_distance = self.default_buffer
            polygon = self._create_buffer_polygon(points, buffer_distance)
            
        elif method == 'centerline':
            if buffer_distance is None:
                buffer_distance = self.default_buffer
            polygon = self._create_centerline_polygon(points, buffer_distance)
            
        elif method in ['beam', 'adaptive_beam']:
            if method == 'adaptive_beam' and buffer_distance is None:
                # Use adaptive buffer sizing
                buffer_distance = self.estimate_optimal_buffer(lon, lat)
                metadata['adaptive_buffer'] = buffer_distance
                print(f"  Calculated adaptive buffer: {buffer_distance:.0f}m")
            elif buffer_distance is None:
                buffer_distance = self.default_buffer
                
            polygon = self._create_beam_polygon(points, buffer_distance)
            
        else:
            raise ValueError(f"Unknown method: {method}")
        
        # Apply iterative simplification if requested
        if iterative_simplify and polygon is not None:
            # Use all data points for better coverage calculation
            data_points = points
            
            simplified, history = optimize_polygon_for_cmr(
                polygon,
                data_points=data_points,
                target_vertices=target_vertices,
                min_iou=min_iou,
                min_coverage=min_coverage
            )
            
            polygon = simplified
            metadata['simplification_history'] = history
            metadata['final_vertices'] = polygon.exterior.coords[:-1].__len__()
        
        # Apply vertex limit if specified
        elif max_points and polygon is not None:
            polygon = self.simplify_polygon_with_constraints(
                polygon, max_points, min_distance_m=50
            )
        
        metadata['vertices'] = len(polygon.exterior.coords) - 1 if polygon else 0
        
        return polygon, metadata
    
    def create_alpha_shape(self, points, alpha):
        """
        Create an alpha shape (concave hull) from points.
        
        Parameters:
        -----------
        points : np.ndarray
            Array of (x, y) coordinates
        alpha : float
            Alpha parameter (larger = tighter fit)
            
        Returns:
        --------
        polygon : shapely.geometry.Polygon or None
        """
        if len(points) < 4:
            # Fall back to convex hull for too few points
            return Polygon(points).convex_hull
        
        # Create Delaunay triangulation
        tri = Delaunay(points)
        
        # Get triangles as point indices
        triangles = points[tri.simplices]
        
        # Calculate circumradius for each triangle
        a = ((triangles[:, 0, 0] - triangles[:, 1, 0]) ** 2 + 
             (triangles[:, 0, 1] - triangles[:, 1, 1]) ** 2) ** 0.5
        b = ((triangles[:, 1, 0] - triangles[:, 2, 0]) ** 2 + 
             (triangles[:, 1, 1] - triangles[:, 2, 1]) ** 2) ** 0.5
        c = ((triangles[:, 2, 0] - triangles[:, 0, 0]) ** 2 + 
             (triangles[:, 2, 1] - triangles[:, 0, 1]) ** 2) ** 0.5
        
        s = (a + b + c) / 2.0
        areas = (s * (s - a) * (s - b) * (s - c)) ** 0.5
        
        # Avoid division by zero
        areas = np.maximum(areas, 1e-10)
        circum_r = a * b * c / (4.0 * areas)
        
        # Filter triangles by alpha criterion
        filtered = triangles[circum_r < 1.0 / alpha]
        
        if len(filtered) == 0:
            # If no triangles pass, return convex hull
            return Polygon(points).convex_hull
        
        # Extract edges from filtered triangles
        edges = set()
        for tri in filtered:
            for i in range(3):
                edge = tuple(sorted([tuple(tri[i]), tuple(tri[(i + 1) % 3])]))
                edges.add(edge)
        
        # Build polygon from edges
        try:
            # Convert edges to LineString and union them
            lines = [LineString(edge) for edge in edges]
            merged = unary_union(lines)
            
            # Extract the outer boundary
            if hasattr(merged, 'convex_hull'):
                return merged.convex_hull
            else:
                return None
        except:
            # Fall back to convex hull on any error
            return Polygon(points).convex_hull
    
    def create_concave_hull(self, points, ratio=0.2):
        """
        Create a concave hull from points.
        
        Parameters:
        -----------
        points : np.ndarray
            Array of (x, y) coordinates
        ratio : float
            Concavity ratio (0-1, lower = more concave)
            
        Returns:
        --------
        polygon : shapely.geometry.Polygon
        """
        # Subsample if too many points
        if len(points) > 10000:
            indices = np.random.choice(len(points), 10000, replace=False)
            points = points[indices]
        
        # Try shapely's concave hull if available
        try:
            from shapely.geometry import MultiPoint
            mp = MultiPoint(points)
            return mp.concave_hull(ratio)
        except (ImportError, AttributeError):
            # Fall back to alpha shape
            alpha = 1.0 / (ratio + 0.01)  # Convert ratio to alpha
            return self.create_alpha_shape(points, alpha)
    
    def estimate_optimal_buffer(self, lon, lat, target_cmr_area=None):
        """
        Estimate optimal buffer size based on data characteristics.
        
        Parameters:
        -----------
        lon, lat : array-like
            Longitude and latitude coordinates
        target_cmr_area : float, optional
            Target area from CMR polygon for refinement
            
        Returns:
        --------
        buffer_m : float
            Optimal buffer size in meters
        """
        # Calculate data extent
        lon_range = np.max(lon) - np.min(lon)
        lat_range = np.max(lat) - np.min(lat)
        
        # Characteristic length (diagonal of bounding box)
        char_length_deg = np.sqrt(lon_range**2 + lat_range**2)
        
        # Convert to meters (approximate)
        center_lat = np.mean(lat)
        char_length_m = char_length_deg * 111000 * np.cos(np.radians(center_lat))
        
        # Base buffer as percentage of characteristic length
        base_buffer = char_length_m * 0.05  # 5% of extent
        
        # Adjust based on point density
        area_deg2 = lon_range * lat_range
        points_per_deg2 = len(lon) / max(area_deg2, 0.0001)
        
        # High density needs smaller buffer, low density needs larger
        if points_per_deg2 > 1000000:  # Very dense
            density_factor = 0.5
        elif points_per_deg2 > 100000:  # Dense
            density_factor = 0.7
        elif points_per_deg2 < 10000:  # Sparse
            density_factor = 1.5
        else:  # Normal
            density_factor = 1.0
        
        # Apply density adjustment
        buffer_m = base_buffer * density_factor
        
        # Optional: Refine based on target CMR area
        if target_cmr_area is not None:
            # This would require iterative refinement
            # For now, just use as a scaling hint
            pass
        
        # Clamp to reasonable range
        buffer_m = np.clip(buffer_m, self.min_buffer, self.max_buffer)
        
        return buffer_m
    
    def _create_convex_hull(self, points):
        """Create convex hull from points."""
        return Polygon(points).convex_hull
    
    def _create_buffer_polygon(self, points, buffer_distance):
        """Create polygon by buffering all points."""
        # Project to UTM for accurate buffering
        center_lon = np.mean(points[:, 0])
        center_lat = np.mean(points[:, 1])
        
        # Determine UTM zone
        utm_zone = int((center_lon + 180) / 6) + 1
        utm_crs = f"+proj=utm +zone={utm_zone} +datum=WGS84"
        
        # Create transformer
        transformer = pyproj.Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
        
        # Transform points to UTM
        utm_points = np.array([transformer.transform(p[0], p[1]) for p in points])
        
        # Create buffer around each point and union
        buffers = [Point(p).buffer(buffer_distance) for p in utm_points]
        utm_polygon = unary_union(buffers)
        
        # Transform back to lat/lon
        transformer_back = pyproj.Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)
        
        if hasattr(utm_polygon, 'exterior'):
            coords = list(utm_polygon.exterior.coords)
            lonlat_coords = [transformer_back.transform(x, y) for x, y in coords]
            return Polygon(lonlat_coords)
        
        return None
    
    def _create_centerline_polygon(self, points, buffer_distance):
        """Create polygon by buffering flight centerline."""
        # Find centerline
        centerline_coords = self.find_centerline(points)
        
        if centerline_coords is None:
            return None
        
        # Create LineString and buffer it
        center_lon = np.mean(centerline_coords[:, 0])
        center_lat = np.mean(centerline_coords[:, 1])
        
        # Project to UTM
        utm_zone = int((center_lon + 180) / 6) + 1
        utm_crs = f"+proj=utm +zone={utm_zone} +datum=WGS84"
        
        transformer = pyproj.Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
        utm_coords = np.array([transformer.transform(p[0], p[1]) 
                              for p in centerline_coords])
        
        # Create buffered line
        line = LineString(utm_coords)
        utm_polygon = line.buffer(buffer_distance, cap_style=2)  # Round caps
        
        # Transform back
        transformer_back = pyproj.Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)
        coords = list(utm_polygon.exterior.coords)
        lonlat_coords = [transformer_back.transform(x, y) for x, y in coords]
        
        return Polygon(lonlat_coords)
    
    def _create_beam_polygon(self, points, buffer_distance):
        """Create polygon using beam method (buffer with connections) - OPTIMIZED."""
        import time
        print(f"    Creating beam polygon with {len(points)} points...")
        
        # For very large datasets, use convex hull with buffer as fallback
        if len(points) > 5000:
            print(f"    Using fast convex hull method for {len(points)} points")
            start = time.time()
            
            # Create convex hull
            hull = Polygon(points).convex_hull
            
            # Project to UTM for buffering
            center_lon = np.mean(points[:, 0])
            center_lat = np.mean(points[:, 1])
            utm_zone = int((center_lon + 180) / 6) + 1
            utm_crs = f"+proj=utm +zone={utm_zone} +datum=WGS84"
            
            transformer_to = pyproj.Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
            transformer_from = pyproj.Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)
            
            # Transform hull to UTM
            hull_coords = np.array(hull.exterior.coords)
            utm_coords = np.array([transformer_to.transform(x, y) for x, y in hull_coords])
            utm_hull = Polygon(utm_coords)
            
            # Buffer in UTM
            buffered = utm_hull.buffer(buffer_distance * 1.5)  # Slightly larger buffer
            
            # Transform back
            buffered_coords = np.array(buffered.exterior.coords)
            wgs_coords = np.array([transformer_from.transform(x, y) for x, y in buffered_coords])
            
            print(f"    Fast convex hull method took {time.time() - start:.2f}s")
            return Polygon(wgs_coords)
        
        # Original method for smaller datasets
        print(f"    Using standard beam method")
        
        # Subsample if still too many
        if len(points) > 5000:
            indices = np.random.choice(len(points), 5000, replace=False)
            points = points[indices]
            print(f"    Subsampled to {len(points)} points")
        
        # Project to UTM
        center_lon = np.mean(points[:, 0])
        center_lat = np.mean(points[:, 1])
        utm_zone = int((center_lon + 180) / 6) + 1
        utm_crs = f"+proj=utm +zone={utm_zone} +datum=WGS84"
        
        transformer = pyproj.Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
        utm_points = np.array([transformer.transform(p[0], p[1]) for p in points])
        
        # Create buffered points - but limit the number
        start = time.time()
        if len(utm_points) > 1000:
            # For many points, create a multipoint and buffer once
            multipoint = unary_union([Point(p) for p in utm_points])
            merged = multipoint.buffer(buffer_distance)
            print(f"    Multipoint buffer took {time.time() - start:.2f}s")
        else:
            # Original method for fewer points
            buffered_points = [Point(p).buffer(buffer_distance) for p in utm_points]
            merged = unary_union(buffered_points)
            print(f"    Individual buffers took {time.time() - start:.2f}s")
        
        # If result is MultiPolygon, connect the parts
        if isinstance(merged, MultiPolygon):
            polygons = list(merged.geoms)
            
            while len(polygons) > 1:
                # Find two closest polygons
                min_dist = float('inf')
                merge_idx = (0, 1)
                
                for i in range(len(polygons)):
                    for j in range(i + 1, len(polygons)):
                        dist = polygons[i].distance(polygons[j])
                        if dist < min_dist:
                            min_dist = dist
                            merge_idx = (i, j)
                
                # Connect them
                poly1 = polygons[merge_idx[0]]
                poly2 = polygons[merge_idx[1]]
                
                # Find closest points
                coords1 = np.array(poly1.exterior.coords)
                coords2 = np.array(poly2.exterior.coords)
                
                distances = cdist(coords1, coords2)
                min_idx = np.unravel_index(distances.argmin(), distances.shape)
                
                # Create connecting corridor
                p1 = Point(coords1[min_idx[0]])
                p2 = Point(coords2[min_idx[1]])
                connector = LineString([p1, p2]).buffer(buffer_distance)
                
                # Merge polygons
                merged_poly = unary_union([poly1, poly2, connector])
                
                # Update polygon list
                polygons = [p for i, p in enumerate(polygons) 
                           if i not in merge_idx]
                if hasattr(merged_poly, 'geoms'):
                    polygons.extend(merged_poly.geoms)
                else:
                    polygons.append(merged_poly)
            
            merged = polygons[0] if polygons else merged
        
        # Transform back to lat/lon
        transformer_back = pyproj.Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)
        
        if hasattr(merged, 'exterior'):
            coords = list(merged.exterior.coords)
            lonlat_coords = [transformer_back.transform(x, y) for x, y in coords]
            return Polygon(lonlat_coords)
        
        return None
    
    def find_centerline(self, coords, subsample_size=1000):
        """
        Find smoothed centerline through points.
        
        Parameters:
        -----------
        coords : np.ndarray
            Array of (x, y) coordinates
        subsample_size : int
            Number of points to subsample to
            
        Returns:
        --------
        centerline : np.ndarray or None
            Smoothed centerline coordinates
        """
        if len(coords) < 4:
            return None
        
        # Subsample if needed
        if len(coords) > subsample_size:
            indices = np.linspace(0, len(coords) - 1, subsample_size, dtype=int)
            coords = coords[indices]
        
        # Calculate cumulative distance along path
        distances = np.zeros(len(coords))
        for i in range(1, len(coords)):
            distances[i] = distances[i-1] + np.linalg.norm(
                coords[i] - coords[i-1]
            )
        
        # Fit splines to smooth the path
        try:
            spline_x = UnivariateSpline(distances, coords[:, 0], s=0.01)
            spline_y = UnivariateSpline(distances, coords[:, 1], s=0.01)
            
            # Generate smooth centerline
            smooth_distances = np.linspace(0, distances[-1], len(coords))
            smooth_x = spline_x(smooth_distances)
            smooth_y = spline_y(smooth_distances)
            
            return np.column_stack((smooth_x, smooth_y))
        except:
            return coords
    
    def simplify_polygon_with_constraints(self, polygon, max_points, min_distance_m=50):
        """
        Simplify polygon to meet vertex count constraints.
        
        Parameters:
        -----------
        polygon : shapely.geometry.Polygon
            Input polygon
        max_points : int
            Maximum number of vertices
        min_distance_m : float
            Minimum distance between vertices in meters
            
        Returns:
        --------
        simplified : shapely.geometry.Polygon
            Simplified polygon
        """
        if polygon is None or polygon.is_empty:
            return polygon
        
        current_points = len(polygon.exterior.coords) - 1
        
        if current_points <= max_points:
            return polygon
        
        # For very low vertex counts, use aggressive simplification
        if max_points < 20:
            # Use increasingly aggressive tolerance
            for tolerance_factor in [0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05]:
                simplified = polygon.simplify(tolerance_factor, preserve_topology=True)
                if len(simplified.exterior.coords) - 1 <= max_points:
                    return simplified
        
        # Standard simplification for moderate vertex counts
        tolerance = 0.00001
        while current_points > max_points and tolerance < 1.0:
            simplified = polygon.simplify(tolerance, preserve_topology=True)
            current_points = len(simplified.exterior.coords) - 1
            
            if current_points <= max_points:
                return simplified
            
            tolerance *= 2
        
        return simplified
    
    def calculate_polygon_fit_metrics(self, polygon, original_polygon, data_points=None):
        """
        Calculate quality metrics for polygon fit.
        
        Parameters:
        -----------
        polygon : shapely.geometry.Polygon
            Simplified polygon
        original_polygon : shapely.geometry.Polygon
            Original polygon
        data_points : np.ndarray, optional
            Data points to check coverage
            
        Returns:
        --------
        metrics : dict
            Dictionary of quality metrics
        """
        metrics = {}
        
        # IoU (Intersection over Union)
        intersection = polygon.intersection(original_polygon).area
        union = polygon.union(original_polygon).area
        metrics['iou'] = intersection / union if union > 0 else 0
        
        # Area ratio
        metrics['area_ratio'] = polygon.area / original_polygon.area if original_polygon.area > 0 else 0
        
        # Hausdorff distance (shape similarity)
        try:
            from shapely.ops import nearest_points
            coords1 = np.array(polygon.exterior.coords)
            coords2 = np.array(original_polygon.exterior.coords)
            
            # Sample points if too many
            if len(coords1) > 100:
                indices = np.linspace(0, len(coords1)-1, 100, dtype=int)
                coords1 = coords1[indices]
            if len(coords2) > 100:
                indices = np.linspace(0, len(coords2)-1, 100, dtype=int)
                coords2 = coords2[indices]
            
            distances1 = [Point(c).distance(original_polygon.exterior) for c in coords1]
            distances2 = [Point(c).distance(polygon.exterior) for c in coords2]
            
            metrics['hausdorff_distance'] = max(max(distances1), max(distances2))
        except:
            metrics['hausdorff_distance'] = 0
        
        # Data coverage (if data points provided)
        if data_points is not None and len(data_points) > 0:
            # First check how many points were in original
            original_inside = sum(1 for p in data_points if original_polygon.contains(Point(p)))
            
            if original_inside > 0:
                # Check how many are in simplified
                simplified_inside = sum(1 for p in data_points if polygon.contains(Point(p)))
                metrics['data_coverage'] = simplified_inside / original_inside
            else:
                metrics['data_coverage'] = 1.0
        else:
            metrics['data_coverage'] = 1.0
        
        # Vertex count
        metrics['vertices'] = len(polygon.exterior.coords) - 1
        
        return metrics
    
    def create_cmr_optimized_polygon(self, lon, lat, cmr_polygon, method='adaptive_beam'):
        """
        Create a polygon optimized to replace a CMR polygon.
        
        This method ensures:
        1. 100% data coverage
        2. Vertices <= CMR vertices
        3. Minimal non-data area
        4. Area <= CMR area
        
        Parameters:
        -----------
        lon, lat : array-like
            Data point coordinates
        cmr_polygon : shapely.geometry.Polygon
            Current CMR polygon to replace
        method : str
            Initial generation method
            
        Returns:
        --------
        polygon : shapely.geometry.Polygon
            Optimized polygon
        metadata : dict
            Generation and optimization metadata
        """
        # First generate initial polygon with good coverage
        # Use slightly larger buffer to ensure full coverage
        initial_polygon, initial_metadata = self.create_flightline_polygon(
            lon, lat, 
            method=method,
            buffer_distance=None,  # Use adaptive
            iterative_simplify=False  # We'll do custom optimization
        )
        
        # Prepare data points for optimization
        data_points = np.column_stack((lon, lat))
        
        # Run CMR-focused optimization
        optimized_polygon, final_metrics = optimize_polygon_for_cmr(
            initial_polygon, 
            data_points, 
            cmr_polygon
        )
        
        # Combine metadata
        metadata = initial_metadata.copy()
        metadata.update({
            'cmr_optimized': True,
            'final_vertices': final_metrics['vertices'],
            'final_area': final_metrics['area'],
            'data_coverage': final_metrics['data_coverage'],
            'meets_constraints': (
                final_metrics['data_coverage'] >= 1.0 and
                final_metrics['vertices'] <= final_metrics.get('cmr_vertices', float('inf')) and
                final_metrics['area'] <= final_metrics.get('cmr_area', float('inf'))
            )
        })
        
        return optimized_polygon, metadata


# Create a default instance for convenience
default_generator = PolygonGenerator()