"""
Polygon Generation Module for LVIS Flightline Processing

This module provides polygon generation using multiple methods:
- beam: Sample points along flightpath and buffer
- adaptive_beam: Use data density to determine optimal buffer size
- union_buffer: Buffer all points, union, connect components, and smooth
- line_buffer: Create line through sequential points, buffer, and optimize

All methods support iterative simplification to achieve target vertex counts
while maintaining data coverage and minimizing non-data area.
"""

import time
from functools import lru_cache

import numpy as np
import pyproj
from shapely.geometry import MultiPolygon, Point
from shapely.ops import unary_union
from shapely.validation import make_valid

from .simplification import iterative_simplify_polygon


@lru_cache(maxsize=128)
def get_utm_transformers(center_lon, center_lat):
    """
    Get cached UTM transformers for a given location.
    
    Parameters:
    -----------
    center_lon : float
        Center longitude for UTM zone calculation
    center_lat : float
        Center latitude for hemisphere determination
        
    Returns:
    --------
    tuple : (to_utm, to_wgs) transformer objects
    """
    # Determine UTM zone
    utm_zone = int((center_lon + 180) / 6) + 1
    
    # Create projection string
    if center_lat >= 0:
        proj_string = f"+proj=utm +zone={utm_zone} +north +datum=WGS84"
    else:
        proj_string = f"+proj=utm +zone={utm_zone} +south +datum=WGS84"
    
    # Create transformers
    to_utm = pyproj.Transformer.from_crs("EPSG:4326", proj_string, always_xy=True)
    to_wgs = pyproj.Transformer.from_crs(proj_string, "EPSG:4326", always_xy=True)
    
    return to_utm, to_wgs


class PolygonGenerator:
    """Main class for polygon generation with beam-based methods."""

    def __init__(self):
        """Initialize the polygon generator."""
        self.default_buffer = 1000  # meters - updated for line_buffer optimization
        self.min_buffer = 200
        self.max_buffer = 2000  # increased to allow 2.0x multiplier on 1000m default

    def create_flightline_polygon(self, lon, lat):
        """
        Create a polygon representing the flightline coverage.
        
        The algorithm automatically:
        1. Analyzes data characteristics (density, linearity, spacing)
        2. Selects the optimal generation method
        3. Determines appropriate parameters (buffer size, target vertices)
        4. Generates and optimizes the polygon
        5. Ensures high data coverage with minimal non-data area

        Parameters:
        -----------
        lon, lat : array-like
            Longitude and latitude coordinates

        Returns:
        --------
        polygon : shapely.geometry.Polygon or None
            The generated polygon
        metadata : dict
            Metadata about the generation process including:
            - method: Selected generation method
            - points: Number of input points
            - vertices: Final vertex count
            - data_coverage: Percentage of data covered
            - generation_time_seconds: Total processing time
            - data_analysis: Characteristics that drove method selection
        """
        # Start timing for polygon generation
        start_time = time.time()

        # Filter out invalid coordinates
        mask = np.isfinite(lon) & np.isfinite(lat)
        lon = np.array(lon)[mask]
        lat = np.array(lat)[mask]

        metadata = {
            "points": len(lon),
        }

        # Handle empty or insufficient data
        if len(lon) == 0:
            print("[PolygonGenerator] Error: No valid coordinates found")
            metadata["vertices"] = 0
            metadata["method"] = "none"
            return None, metadata

        if len(lon) == 1:
            # Single point - create a buffer around it
            buffer_distance = self.default_buffer
            point = Point(lon[0], lat[0])
            polygon = self._buffer_in_meters(point, buffer_distance, lat[0])
            metadata["buffer_m"] = buffer_distance
            metadata["vertices"] = len(polygon.exterior.coords) - 1
            metadata["method"] = "point_buffer"
            return polygon, metadata

        if len(lon) < 3:
            print(f"[PolygonGenerator] Note: Only {len(lon)} coordinates, using simple line buffer")
            # Create line and buffer it
            buffer_distance = self.default_buffer
            from shapely.geometry import LineString

            line = LineString(zip(lon, lat))
            polygon = self._buffer_in_meters(line, buffer_distance, np.mean(lat))
            metadata["buffer_m"] = buffer_distance
            metadata["vertices"] = len(polygon.exterior.coords) - 1
            metadata["method"] = "line_buffer_simple"
            return polygon, metadata

        # Create points array
        points = np.column_stack((lon, lat))

        # Analyze data characteristics to determine optimal approach
        data_metrics = self._analyze_data_characteristics(points)
        
        # Select method based on data characteristics
        method = self._select_optimal_method(data_metrics)
        
        # Determine target vertices based on data characteristics
        target_vertices = self._select_target_vertices(data_metrics)
        
        # Determine minimum coverage based on data quality
        min_coverage = self._select_min_coverage(data_metrics)
        
        # Set other parameters based on method and data
        connect_regions = True  # Always try to connect regions
        connection_buffer_multiplier = 1.5  # Conservative multiplier
        buffer_distance = None  # Let each method calculate its own
        
        # Log analysis results
        print("\n[PolygonGenerator] Stage 1: Data Analysis")
        print(f"  Points: {len(points)}")
        print(f"  Characteristics: {data_metrics['summary']}")
        print(f"\n[PolygonGenerator] Stage 2: Method Selection")
        print(f"  Selected method: {method}")
        print(f"  Target vertices: {target_vertices}")
        print(f"  Min coverage: {min_coverage:.0%}")
        
        # Store analysis in metadata
        metadata["method"] = method
        metadata["data_analysis"] = {
            "metrics": data_metrics,
            "selected_method": method,
            "target_vertices": target_vertices,
            "min_coverage": min_coverage
        }

        # Handle different methods
        if method in ["beam", "adaptive_beam"]:
            if method == "adaptive_beam" and buffer_distance is None:
                # Use adaptive buffer sizing
                buffer_distance = self.estimate_optimal_buffer(lon, lat)
                metadata["adaptive_buffer"] = buffer_distance
                print(f"\n[PolygonGenerator] Stage 3: Generate Polygon (adaptive_beam)")
                print(f"  Adaptive buffer: {buffer_distance:.0f}m")
            elif buffer_distance is None:
                buffer_distance = self.default_buffer

            # Determine sample size based on data size
            sample_size = min(1000, max(100, len(points) // 10))
            
            if buffer_distance is None:
                buffer_distance = self.default_buffer
                
            print(f"\n[PolygonGenerator] Stage 3: Generate Polygon ({method})")
            print(f"  Buffer: {buffer_distance:.0f}m, Sample size: {sample_size} points")
            
            polygon, beam_metadata = self._create_beam_polygon(
                points,
                buffer_distance,
                sample_size,
                connect_regions,
                connection_buffer_multiplier,
            )
            metadata["buffer_m"] = buffer_distance
            metadata.update(beam_metadata)  # Include sample_size and other metadata

        elif method == "union_buffer":
            if buffer_distance is None:
                # Calculate adaptive buffer based on nearest neighbor distances
                buffer_distance = self._calculate_adaptive_union_buffer(points)
                metadata["adaptive_buffer_calculation"] = "nearest_neighbors"
            print(f"\n[PolygonGenerator] Stage 3: Generate Polygon (union_buffer)")
            print(f"  Adaptive buffer: {buffer_distance:.0f}m (based on nearest neighbors)")

            polygon, union_metadata = self._create_union_buffer_polygon(
                points, buffer_distance, connect_regions, connection_buffer_multiplier
            )
            metadata["buffer_m"] = buffer_distance
            metadata.update(union_metadata)

        elif method == "line_buffer":
            if buffer_distance is None:
                # Calculate initial buffer based on average distance between sequential points
                buffer_distance = self._calculate_line_buffer_distance(points)
                metadata["adaptive_buffer_calculation"] = "sequential_distances"
            print(f"\n[PolygonGenerator] Stage 3: Generate Polygon (line_buffer)")
            print(f"  Adaptive buffer: {buffer_distance:.0f}m (based on sequential distances)")

            polygon, line_metadata = self._create_line_buffer_polygon(
                points, buffer_distance
            )
            metadata["buffer_m"] = buffer_distance
            metadata.update(line_metadata)

        else:
            raise ValueError(
                f"Unknown method: {method}. Supported methods: auto, beam, adaptive_beam, union_buffer, line_buffer"
            )

        # Always apply iterative simplification to optimize the polygon
        if polygon is not None:
            print(f"\n[PolygonGenerator] Stage 4: Polygon Simplification")
            print(f"  Initial vertices: {len(polygon.exterior.coords) - 1 if hasattr(polygon, 'exterior') else 'N/A'}")
            
            # Use all data points for better coverage calculation
            data_points = points

            simplified, history = iterative_simplify_polygon(
                polygon,
                data_points=data_points,
                target_vertices=target_vertices,
                min_coverage=min_coverage,
                max_non_data_coverage=0.25,  # Allow up to 25% non-data area to prioritize data coverage
            )

            polygon = simplified
            metadata["simplification_history"] = history

            if history:
                print(f"  Final vertices: {history[-1]['vertices']}")
                print(f"  Data coverage: {history[-1].get('data_coverage', 'N/A'):.1%}")
                print(f"  Non-data coverage: {history[-1].get('non_data_coverage', 'N/A'):.1%}")

        # Add final vertex count
        if polygon is not None:
            if hasattr(polygon, "exterior"):
                metadata["vertices"] = len(polygon.exterior.coords) - 1
            else:
                metadata["vertices"] = 0
        else:
            metadata["vertices"] = 0

        # Record total generation time
        end_time = time.time()
        generation_time = end_time - start_time
        metadata["generation_time_seconds"] = generation_time

        print(f"\n[PolygonGenerator] Complete: Generated in {generation_time:.2f}s")

        return polygon, metadata

    def _analyze_data_characteristics(self, points):
        """
        Analyze data characteristics to inform method selection.
        
        Parameters:
        -----------
        points : array-like
            Nx2 array of lon/lat coordinates
            
        Returns:
        --------
        dict : Data characteristics and metrics
        """
        from shapely.geometry import MultiPoint
        
        metrics = {}
        
        # Basic counts
        metrics['total_points'] = len(points)
        
        if len(points) < 3:
            metrics['summary'] = f"{len(points)} points (insufficient for analysis)"
            return metrics
        
        # Distance analysis between successive points
        diffs = np.diff(points, axis=0)
        distances_deg = np.sqrt(diffs[:, 0] ** 2 + diffs[:, 1] ** 2)
        
        # Convert to meters (approximate)
        mean_lat = np.mean(points[:, 1])
        lat_factor = 111000  # meters per degree latitude
        lon_factor = 111000 * np.cos(np.radians(mean_lat))
        
        distances_m = []
        for i, dist_deg in enumerate(distances_deg):
            lon_diff = diffs[i, 0]
            lat_diff = diffs[i, 1]
            dist_m = np.sqrt((lon_diff * lon_factor) ** 2 + (lat_diff * lat_factor) ** 2)
            distances_m.append(dist_m)
        
        distances_m = np.array(distances_m)
        distances_m = distances_m[distances_m > 0]  # Remove zero distances
        
        if len(distances_m) > 0:
            metrics['distance_min_m'] = np.min(distances_m)
            metrics['distance_median_m'] = np.median(distances_m)
            metrics['distance_mean_m'] = np.mean(distances_m)
            metrics['distance_max_m'] = np.max(distances_m)
            metrics['distance_std_m'] = np.std(distances_m)
            metrics['distance_cv'] = metrics['distance_std_m'] / metrics['distance_mean_m'] if metrics['distance_mean_m'] > 0 else 0
        else:
            metrics.update({
                'distance_min_m': 0, 'distance_median_m': 0, 'distance_mean_m': 0,
                'distance_max_m': 0, 'distance_std_m': 0, 'distance_cv': 0
            })
        
        # Convex hull analysis
        try:
            multipoint = MultiPoint(points)
            convex_hull = multipoint.convex_hull
            metrics['convex_hull_area_deg2'] = convex_hull.area
            
            # Convert to approximate area in km²
            area_km2 = convex_hull.area * (lat_factor/1000) * (lon_factor/1000)
            metrics['convex_hull_area_km2'] = area_km2
            
            # Density: points per km²
            metrics['density_points_per_km2'] = metrics['total_points'] / area_km2 if area_km2 > 0 else 0
            
            # Aspect ratio of convex hull
            bounds = convex_hull.bounds
            width = (bounds[2] - bounds[0]) * lon_factor / 1000  # km
            height = (bounds[3] - bounds[1]) * lat_factor / 1000  # km
            metrics['width_km'] = width
            metrics['height_km'] = height
            metrics['aspect_ratio'] = max(width, height) / min(width, height) if min(width, height) > 0 else 1
            
        except Exception:
            metrics.update({
                'convex_hull_area_deg2': 0, 'convex_hull_area_km2': 0,
                'density_points_per_km2': 0, 'width_km': 0, 'height_km': 0, 'aspect_ratio': 1
            })
        
        # Linearity measure: how well do points follow a straight line?
        if len(points) > 2:
            # Fit a line through first and last points
            start, end = points[0], points[-1]
            line_length = np.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)
            
            if line_length > 0:
                # Calculate total path length
                total_path_length = np.sum(distances_deg)
                metrics['linearity'] = line_length / total_path_length if total_path_length > 0 else 0
            else:
                metrics['linearity'] = 0
        else:
            metrics['linearity'] = 1
        
        # Create summary description
        if metrics['total_points'] > 100000:
            size_desc = "very dense"
        elif metrics['total_points'] > 10000:
            size_desc = "dense"
        elif metrics['total_points'] > 1000:
            size_desc = "moderate"
        else:
            size_desc = "sparse"
        
        if metrics['aspect_ratio'] > 5:
            shape_desc = "linear"
        elif metrics['aspect_ratio'] > 2:
            shape_desc = "elongated"
        else:
            shape_desc = "compact"
        
        if metrics['distance_cv'] < 0.5:
            spacing_desc = "regular"
        elif metrics['distance_cv'] < 1.0:
            spacing_desc = "variable"
        else:
            spacing_desc = "irregular"
        
        metrics['summary'] = f"{size_desc}, {shape_desc}, {spacing_desc} spacing"
        
        return metrics
    
    def _select_optimal_method(self, metrics):
        """
        Select optimal method based on data characteristics.
        
        Parameters:
        -----------
        metrics : dict
            Data characteristics from _analyze_data_characteristics
            
        Returns:
        --------
        str : Recommended method
        """
        
        total_points = metrics['total_points']
        density = metrics.get('density_points_per_km2', 0)
        aspect_ratio = metrics.get('aspect_ratio', 1)
        linearity = metrics.get('linearity', 0)
        distance_cv = metrics.get('distance_cv', 0)
        
        # Decision tree for method selection
        
        # Very sparse data - use convex hull
        if total_points < 50 or density < 10:
            return "union_buffer"  # Simple but effective for sparse data
        
        # Very dense data in compact area - use union buffer
        if density > 10000 and aspect_ratio < 3:
            return "union_buffer"
        
        # Linear data with regular spacing - line buffer is good
        if aspect_ratio > 5 and linearity > 0.7 and distance_cv < 0.8:
            return "line_buffer"
        
        # Irregular or very dense data - union buffer
        if distance_cv > 1.0 or density > 5000:
            return "union_buffer"
        
        # Default to line buffer for moderate cases
        return "line_buffer"
    
    def _select_target_vertices(self, metrics):
        """
        Select appropriate target vertex count based on data characteristics.
        Prioritizes data coverage over aggressive vertex reduction.
        
        Parameters:
        -----------
        metrics : dict
            Data characteristics from _analyze_data_characteristics
            
        Returns:
        --------
        int : Target vertex count
        """
        total_points = metrics['total_points']
        density = metrics.get('density_points_per_km2', 0)
        aspect_ratio = metrics.get('aspect_ratio', 1)
        distance_cv = metrics.get('distance_cv', 0)
        
        # CONSERVATIVE APPROACH: Allow more vertices to maintain data coverage
        
        # Sparse data - still keep simple but allow slightly more vertices
        if total_points < 50:
            return 12  # Increased from 8
        
        # Dense data in compact area - allow significantly more vertices for coverage
        if density > 10000 and aspect_ratio < 3:
            return min(48, max(24, total_points // 5000))  # More generous
        
        # Linear data - allow more vertices for better coverage along the line
        if aspect_ratio > 5:
            return min(32, max(16, total_points // 3000))  # More generous
        
        # Irregular spacing - need more vertices to capture complexity
        if distance_cv > 1.0:
            return min(40, max(20, total_points // 2000))  # Much more generous
        
        # Default based on point count - prioritize coverage over simplicity
        if total_points < 1000:
            return 16  # Increased from 12
        elif total_points < 10000:
            return 24  # Increased from 16
        else:
            return min(48, max(24, total_points // 5000))  # Much more generous
    
    def _select_min_coverage(self, metrics):
        """
        Select minimum coverage threshold based on data quality.
        Prioritizes maintaining high data coverage.
        
        Parameters:
        -----------
        metrics : dict
            Data characteristics from _analyze_data_characteristics
            
        Returns:
        --------
        float : Minimum coverage threshold (0.0 to 1.0)
        """
        total_points = metrics['total_points']
        density = metrics.get('density_points_per_km2', 0)
        distance_cv = metrics.get('distance_cv', 0)
        
        # CONSERVATIVE APPROACH: Higher minimum coverage across the board
        
        # Very sparse or irregular data - still maintain good coverage
        if total_points < 50 or density < 10 or distance_cv > 1.5:
            return 0.90  # Increased from 0.85
        
        # Dense, regular data - require very high coverage
        if density > 5000 and distance_cv < 0.5:
            return 0.97  # Increased from 0.95
        
        # Default to higher coverage requirement
        return 0.93  # Increased from 0.90

    def _buffer_in_meters(self, geom, buffer_distance, center_lat):
        """
        Buffer a geometry by a distance in meters.

        Parameters:
        -----------
        geom : shapely geometry
            Geometry to buffer
        buffer_distance : float
            Buffer distance in meters
        center_lat : float
            Latitude for UTM zone selection

        Returns:
        --------
        buffered : shapely geometry
            Buffered geometry in original CRS
        """
        # Get center longitude for UTM zone
        if hasattr(geom, "centroid"):
            center_lon = geom.centroid.x
        else:
            center_lon = geom.x if hasattr(geom, "x") else 0

        # Get cached transformers
        # Round to 1 decimal place to improve cache hit rate
        center_lon_rounded = round(center_lon, 1)
        center_lat_rounded = round(center_lat, 1)
        to_utm, to_wgs = get_utm_transformers(center_lon_rounded, center_lat_rounded)

        # Transform to UTM, buffer, transform back
        from shapely.ops import transform

        geom_utm = transform(to_utm.transform, geom)
        buffered_utm = geom_utm.buffer(buffer_distance)
        buffered = transform(to_wgs.transform, buffered_utm)

        return buffered

    def _create_beam_polygon(
        self,
        points,
        buffer_distance,
        sample_size=None,
        connect_regions=True,
        connection_buffer_multiplier=1.5,
    ):
        """
        Create polygon using beam method (sample points along path).

        Parameters:
        -----------
        points : array-like
            Nx2 array of lon/lat coordinates
        buffer_distance : float
            Buffer distance in meters
        sample_size : int
            Number of points to sample
        connect_regions : bool
            Whether to connect disconnected regions
        connection_buffer_multiplier : float
            Multiplier for connection buffer size

        Returns:
        --------
        polygon : shapely.geometry.Polygon
            Beam polygon
        metadata : dict
            Metadata about the process
        """
        metadata = {}

        # Determine sample size based on total points
        if sample_size is None:
            if len(points) < 100:
                sample_size = len(points)  # Use all points
            elif len(points) < 1000:
                sample_size = max(50, len(points) // 10)
            elif len(points) < 10000:
                sample_size = max(100, len(points) // 50)
            else:
                sample_size = max(200, len(points) // 100)

        metadata["sample_size"] = sample_size

        # Sample points
        if sample_size >= len(points):
            sampled_points = points
        else:
            # Sample evenly along the path
            indices = np.round(np.linspace(0, len(points) - 1, sample_size)).astype(int)
            sampled_points = points[indices]

        # Buffer sampled points
        polygons = []
        mean_lat = np.mean(points[:, 1])

        for point in sampled_points:
            p = Point(point)
            buffered = self._buffer_in_meters(p, buffer_distance, mean_lat)
            polygons.append(buffered)

        # Union all buffers
        union = unary_union(polygons)

        # Handle multi-polygon result
        if isinstance(union, MultiPolygon):
            if connect_regions and len(union.geoms) > 1:
                # Connect regions
                union = self._connect_multipolygon(
                    union, buffer_distance * connection_buffer_multiplier, mean_lat
                )
            else:
                # Just take the largest polygon
                union = max(union.geoms, key=lambda p: p.area)

        polygon = make_valid(union)
        metadata["projection"] = f"UTM (center lat: {mean_lat:.2f})"

        return polygon, metadata

    def _connect_multipolygon(self, multipoly, connection_buffer, center_lat):
        """
        Connect disconnected regions of a MultiPolygon.

        Parameters:
        -----------
        multipoly : shapely.geometry.MultiPolygon
            MultiPolygon to connect
        connection_buffer : float
            Buffer distance for connections in meters
        center_lat : float
            Latitude for projection

        Returns:
        --------
        polygon : shapely.geometry.Polygon
            Connected polygon
        """
        if len(multipoly.geoms) == 1:
            return multipoly.geoms[0]

        # Get centroids of each polygon
        centroids = [p.centroid for p in multipoly.geoms]

        # Create minimum spanning tree of centroids
        from scipy.spatial.distance import cdist
        from shapely.geometry import LineString

        # Calculate distances between all centroids
        centroid_coords = np.array([[c.x, c.y] for c in centroids])
        distances = cdist(centroid_coords, centroid_coords)

        # Simple MST using nearest neighbor
        connected = set([0])
        edges = []

        while len(connected) < len(centroids):
            min_dist = float("inf")
            min_edge = None

            for i in connected:
                for j in range(len(centroids)):
                    if j not in connected and distances[i, j] < min_dist:
                        min_dist = distances[i, j]
                        min_edge = (i, j)

            if min_edge:
                edges.append(min_edge)
                connected.add(min_edge[1])

        # Create lines between connected centroids
        connection_lines = []
        for i, j in edges:
            line = LineString([centroids[i], centroids[j]])
            connection_lines.append(line)

        # Buffer the lines
        buffered_connections = []
        for line in connection_lines:
            buffered = self._buffer_in_meters(line, connection_buffer, center_lat)
            buffered_connections.append(buffered)

        # Union everything
        all_geoms = list(multipoly.geoms) + buffered_connections
        result = unary_union(all_geoms)

        # Return largest polygon if still multi
        if isinstance(result, MultiPolygon):
            result = max(result.geoms, key=lambda p: p.area)

        return make_valid(result)

    def estimate_optimal_buffer(self, lon, lat):
        """
        Estimate optimal buffer size based on data characteristics.

        Parameters:
        -----------
        lon, lat : array-like
            Coordinates

        Returns:
        --------
        buffer_m : float
            Optimal buffer size in meters
        """
        # Calculate basic statistics
        if len(lon) < 2:
            return self.default_buffer

        # Get point spacing
        coords = np.column_stack((lon, lat))

        # Calculate distances between consecutive points
        if len(coords) > 1:
            diffs = np.diff(coords, axis=0)
            distances = np.sqrt(diffs[:, 0] ** 2 + diffs[:, 1] ** 2)

            # Convert to meters (approximate)
            mean_lat = np.mean(lat)
            lat_factor = 111000  # meters per degree latitude
            lon_factor = 111000 * np.cos(
                np.radians(mean_lat)
            )  # meters per degree longitude

            distances_m = (
                distances
                * np.sqrt(
                    (lon_factor * diffs[:, 0]) ** 2 + (lat_factor * diffs[:, 1]) ** 2
                )
                / distances
            )

            # Remove outliers
            distances_m = distances_m[np.isfinite(distances_m)]
            if len(distances_m) > 0:
                percentile_95 = np.percentile(distances_m, 95)

                # Buffer should be large enough to connect points
                # but not so large it oversimplifies
                buffer_size = min(
                    max(percentile_95 * 2, self.min_buffer), self.max_buffer
                )

                # Adjust based on total extent
                lon_range = np.ptp(lon)
                lat_range = np.ptp(lat)
                extent_km = max(lon_range * lon_factor, lat_range * lat_factor) / 1000

                if extent_km > 100:  # Large extent
                    buffer_size = min(buffer_size * 1.5, self.max_buffer)
                elif extent_km < 10:  # Small extent
                    buffer_size = max(buffer_size * 0.7, self.min_buffer)

                return int(buffer_size)

        return self.default_buffer

    def _calculate_adaptive_union_buffer(self, points):
        """
        Calculate buffer size based on local data density.

        Uses the average distance to 2nd-5th nearest neighbors, then takes the 75th percentile
        with a 2x margin. This creates generous coverage while maintaining connectivity.

        Parameters:
        -----------
        points : array-like
            Nx2 array of lon/lat coordinates

        Returns:
        --------
        buffer_m : float
            Buffer size in meters
        """
        if len(points) < 3:
            return self.default_buffer

        # For performance with large datasets, sample points for distance calculation
        if len(points) > 1000:
            sample_size = min(500, len(points))
            indices = np.random.choice(len(points), sample_size, replace=False)
            sample_points = points[indices]
        else:
            sample_points = points

        from scipy.spatial.distance import cdist

        # Calculate all pairwise distances
        distances = cdist(sample_points, sample_points)

        # For each point, find distances to multiple nearest neighbors
        neighbor_distances = []
        for i in range(len(sample_points)):
            # Sort distances for this point (skip self at index 0)
            sorted_distances = np.sort(distances[i])
            if len(sorted_distances) >= 6:  # Need at least 6 points to get 5th nearest
                # Take average of 2nd through 5th nearest neighbors
                # This gives a better sense of local data density
                avg_nearby = np.mean(sorted_distances[2:6])  # indices 2,3,4,5
                neighbor_distances.append(avg_nearby)
            elif len(sorted_distances) >= 3:
                # Fallback: use 2nd nearest if we don't have enough points
                neighbor_distances.append(sorted_distances[2])

        if not neighbor_distances:
            return self.default_buffer

        # Convert from degrees to meters (approximate)
        mean_lat = np.mean(points[:, 1])
        lat_factor = 111000  # meters per degree latitude
        lon_factor = 111000 * np.cos(
            np.radians(mean_lat)
        )  # meters per degree longitude

        # Convert distances to meters (assuming roughly equal lat/lon spacing)
        distances_m = []
        for dist_deg in neighbor_distances:
            # Approximate conversion (could be more sophisticated)
            dist_m = dist_deg * np.sqrt((lat_factor**2 + lon_factor**2) / 2)
            distances_m.append(dist_m)

        # Use 75th percentile instead of median to be more generous
        # This captures more of the data distribution
        percentile_75_dist = np.percentile(distances_m, 75)

        # Calculate some additional statistics for diagnostics
        min_dist = np.min(distances_m)
        max_dist = np.max(distances_m)
        median_dist = np.median(distances_m)
        percentile_90_dist = np.percentile(distances_m, 90)

        # BALANCED BUFFER: Ensure good data coverage while controlling non-data area
        # Use 75th percentile as base with modest multiplier
        buffer_size = percentile_75_dist * 1.3
        
        # For sparse data, be more generous to avoid cutting off data
        if percentile_90_dist > percentile_75_dist * 2.0:
            buffer_size = percentile_75_dist * 1.6
        
        # Ensure sufficient buffer for data coverage
        min_buffer_for_coverage = median_dist * 1.5
        if buffer_size < min_buffer_for_coverage:
            buffer_size = min_buffer_for_coverage

        # Clamp to reasonable bounds (but allow larger max for better coverage)
        buffer_size = max(self.min_buffer, min(buffer_size, self.max_buffer * 4))

        return int(buffer_size)

    def _calculate_line_buffer_distance(self, points):
        """
        Calculate buffer distance for line method based on sequential point distances.

        Returns a default of 1000m for the line buffer optimization to work with.

        Parameters:
        -----------
        points : array-like
            Nx2 array of lon/lat coordinates

        Returns:
        --------
        buffer_m : float
            Buffer distance in meters
        """
        if len(points) < 2:
            return 1000  # New default for line buffer

        # Calculate distances between consecutive points
        diffs = np.diff(points, axis=0)
        distances_deg = np.sqrt(diffs[:, 0] ** 2 + diffs[:, 1] ** 2)

        # Convert to meters
        mean_lat = np.mean(points[:, 1])
        lat_factor = 111000  # meters per degree latitude
        lon_factor = 111000 * np.cos(
            np.radians(mean_lat)
        )  # meters per degree longitude

        distances_m = []
        for i, dist_deg in enumerate(distances_deg):
            lon_diff = diffs[i, 0]
            lat_diff = diffs[i, 1]
            dist_m = np.sqrt(
                (lon_diff * lon_factor) ** 2 + (lat_diff * lat_factor) ** 2
            )
            distances_m.append(dist_m)

        # Remove outliers (very large gaps might be data discontinuities)
        distances_m = np.array(distances_m)
        distances_m = distances_m[distances_m < np.percentile(distances_m, 95)]

        if len(distances_m) == 0:
            return 1000  # New default for line buffer

        # Smart buffer calculation based on average point spacing
        avg_distance = np.mean(distances_m)
        
        if avg_distance < 100:  # Very dense data (< 100m spacing)
            # Use much larger multiplier for dense data to ensure coverage
            # For LVIS-like data, we need to cover the swath width, not just point spacing
            buffer_size = max(500, int(avg_distance * 15))
        elif avg_distance < 1000:  # Dense data (100m - 1km spacing)
            buffer_size = max(500, int(avg_distance * 5))
        elif avg_distance < 5000:  # Normal spacing (1km - 5km)
            buffer_size = 1000  # Default for most cases
        else:  # Sparse flightlines (> 5km spacing)
            # Use 30% of average distance, capped at 1500m
            buffer_size = min(1500, int(avg_distance * 0.3))
        
        # No need for verbose distance output in auto mode

        return int(buffer_size)

    def _create_union_buffer_polygon(
        self,
        points,
        buffer_distance,
        connect_regions=True,
        connection_buffer_multiplier=1.5,
    ):
        """
        Create polygon using union buffer method.

        This method:
        1. Buffers each point by radius 'rb' (buffer_distance)
        2. Takes the union of all circles using incremental batching for efficiency
        3. Connects disconnected components with buffered lines
        4. Returns the result for further smoothing

        Performance optimizations:
        - Automatically calculates buffer size based on 2nd nearest neighbor distances
        - For large datasets (>1000 points), uses random subsampling to limit to 1000 points
        - Processes points in batches of 100 to reduce memory usage
        - Incrementally unions batches to avoid holding all geometries in memory
        - Periodically simplifies intermediate results to prevent complexity explosion
        - Handles excessive disconnected components by trying larger buffers or taking largest component

        Parameters:
        -----------
        points : array-like
            Nx2 array of lon/lat coordinates
        buffer_distance : float
            Buffer radius in meters (rb)
        connect_regions : bool
            Whether to connect disconnected regions
        connection_buffer_multiplier : float
            Multiplier for connection buffer size

        Returns:
        --------
        polygon : shapely geometry
            Union buffer polygon
        metadata : dict
            Metadata about the process
        """
        metadata = {}

        # Simplified output for union buffer

        # Calculate mean latitude for projection
        mean_lat = np.mean(points[:, 1])

        # For large datasets, subsample points to improve performance
        if len(points) > 1000:
            # Simple random sampling
            n_sample = min(1000, len(points))  # Limit to 1000 points max
            indices = np.random.choice(len(points), n_sample, replace=False)
            selected_points = points[indices]

            metadata["sampling_used"] = True
            metadata["original_points"] = len(points)
            metadata["processed_points"] = len(selected_points)
        else:
            selected_points = points
            metadata["sampling_used"] = False
            metadata["processed_points"] = len(points)

        # Create buffered circles and incrementally union them for efficiency

        # Use batch processing for better memory efficiency and speed
        batch_size = 100  # Process points in batches
        union_geom = None

        for batch_start in range(0, len(selected_points), batch_size):
            batch_end = min(batch_start + batch_size, len(selected_points))
            batch_points = selected_points[batch_start:batch_end]

            if batch_start % (batch_size * 10) == 0:
                pass  # Process silently

            # Buffer all points in this batch
            batch_buffered = []
            for point in batch_points:
                p = Point(point)
                buffered = self._buffer_in_meters(p, buffer_distance, mean_lat)
                batch_buffered.append(buffered)

            # Union this batch
            if len(batch_buffered) == 1:
                batch_union = batch_buffered[0]
            else:
                batch_union = unary_union(batch_buffered)

            # Merge with overall union
            if union_geom is None:
                union_geom = batch_union
            else:
                union_geom = union_geom.union(batch_union)

                # Periodically simplify to prevent geometry complexity explosion
                if batch_start > 0 and batch_start % (batch_size * 5) == 0:
                    # Light simplification to keep performance good
                    union_geom = union_geom.simplify(0.0001, preserve_topology=True)

        print(
            f"  Processed {len(selected_points)} points in {(len(selected_points)-1)//batch_size + 1} batches"
        )

        metadata["initial_circles"] = len(selected_points)
        metadata["batch_size"] = batch_size

        # Handle multi-polygon result
        if isinstance(union_geom, MultiPolygon):
            num_components = len(union_geom.geoms)
            print(f"  Union resulted in {num_components} disconnected components")
            metadata["disconnected_components"] = num_components

            # If too many components, try increasing buffer size first
            if num_components > 50:
                print(
                    f"  Too many components ({num_components}), trying larger buffer..."
                )

                # Try with 2x buffer size on a subset of points
                larger_buffer = buffer_distance * 2
                print(f"  Retrying with {larger_buffer:.0f}m buffer on subset...")

                # Use even smaller subset for the retry
                subset_size = min(200, len(selected_points))
                subset_indices = np.random.choice(
                    len(selected_points), subset_size, replace=False
                )
                subset_points = selected_points[subset_indices]

                # Retry with larger buffer
                retry_geoms = []
                for point in subset_points:
                    p = Point(point)
                    buffered = self._buffer_in_meters(p, larger_buffer, mean_lat)
                    retry_geoms.append(buffered)

                retry_union = unary_union(retry_geoms)

                if isinstance(retry_union, MultiPolygon):
                    retry_components = len(retry_union.geoms)
                    print(f"  Retry resulted in {retry_components} components")
                    if retry_components < 10:
                        # Use the retry result
                        union_geom = retry_union
                        metadata["retry_used"] = True
                        metadata["retry_buffer"] = larger_buffer
                        metadata["retry_points"] = subset_size
                        num_components = retry_components
                    else:
                        # Still too many, just take largest from original
                        print(
                            "  Still too many components, taking largest from original"
                        )
                        union_geom = max(union_geom.geoms, key=lambda p: p.area)
                        metadata["connected"] = False
                        metadata["connection_skipped"] = "too_many_components"
                        # Skip further processing but continue to return properly
                        polygon = make_valid(union_geom)
                        data_coverage_info = self._calculate_data_coverage_metrics(
                            polygon, points
                        )
                        metadata.update(data_coverage_info)
                        return polygon, metadata
                else:
                    # Retry succeeded in creating single component
                    union_geom = retry_union
                    metadata["retry_used"] = True
                    metadata["retry_buffer"] = larger_buffer
                    metadata["retry_points"] = subset_size
                    num_components = 1
            elif connect_regions and num_components > 1:
                print("  Connecting disconnected components...")
                union_geom = self._connect_multipolygon_advanced(
                    union_geom,
                    buffer_distance * connection_buffer_multiplier,
                    mean_lat,
                    points,
                )
                metadata["connected"] = True
            else:
                # Just take the largest polygon
                union_geom = max(union_geom.geoms, key=lambda p: p.area)
                metadata["connected"] = False
                print("  Taking largest component only")
        else:
            print("  Union resulted in single connected component")
            metadata["disconnected_components"] = 1
            metadata["connected"] = False

        # Validate the result
        polygon = make_valid(union_geom)

        # Calculate data coverage metrics for optimization guidance (use original points)
        data_coverage_info = self._calculate_data_coverage_metrics(polygon, points)
        metadata.update(data_coverage_info)

        # If data coverage is poor, try with a larger buffer
        initial_coverage = data_coverage_info.get("data_coverage", 0)
        if initial_coverage < 0.85:  # Less than 85% coverage
            print(
                f"  Low data coverage ({initial_coverage:.1%}), retrying with larger buffer..."
            )

            # Try with 50% larger buffer
            larger_buffer = int(buffer_distance * 1.5)
            retry_polygon, retry_metadata = self._create_union_buffer_polygon_simple(
                points, larger_buffer, connect_regions, connection_buffer_multiplier
            )

            retry_coverage_info = self._calculate_data_coverage_metrics(
                retry_polygon, points
            )
            retry_coverage = retry_coverage_info.get("data_coverage", 0)

            print(f"  Retry coverage: {retry_coverage:.1%}")

            # Use retry result if it's significantly better
            if retry_coverage > initial_coverage + 0.1:  # At least 10% improvement
                print(
                    f"  Using retry result (improved from {initial_coverage:.1%} to {retry_coverage:.1%})"
                )
                polygon = retry_polygon
                data_coverage_info = retry_coverage_info
                metadata.update(data_coverage_info)
                metadata["buffer_retry_used"] = True
                metadata["buffer_retry_size"] = larger_buffer
                metadata["original_coverage"] = initial_coverage
                metadata["retry_coverage"] = retry_coverage
            else:
                print("  Retry didn't improve significantly, keeping original")

        print(f"  Final polygon: {metadata.get('vertices', 'unknown')} vertices")
        print(f"  Data coverage: {metadata.get('data_coverage', 0):.1%}")
        print(
            f"  Non-data area estimate: {metadata.get('estimated_non_data_ratio', 0):.1%}"
        )

        return polygon, metadata

    def _create_line_buffer_polygon(self, points, initial_buffer_distance):
        """
        Create polygon by buffering a line through sequential points with optimization.

        This method:
        1. Creates a line connecting sequential points
        2. Buffers the line by distance 'b'
        3. Optimizes 'b' to meet coverage and vertex count goals

        Parameters:
        -----------
        points : array-like
            Nx2 array of lon/lat coordinates
        initial_buffer_distance : float
            Initial buffer distance in meters

        Returns:
        --------
        polygon : shapely geometry
            Optimized line buffer polygon
        metadata : dict
            Metadata about the optimization process
        """
        metadata = {
            "method": "line_buffer",
            "initial_buffer": initial_buffer_distance,
            "optimization_attempts": [],
        }

        # Concise output handled by optimization summary

        # Calculate mean latitude for projection
        mean_lat = np.mean(points[:, 1])

        # Try different buffer sizes (simplified from original)
        best_polygon = None
        best_score = -1
        best_params = {}

        # Expanded buffer multiplier range to handle diverse datasets
        buffer_multipliers = [0.25, 0.5, 1.0, 2.0, 4.0]
        
        for buf_mult in buffer_multipliers:
            buffer_dist = initial_buffer_distance * buf_mult

            try:
                # Always use 0.0 simplification tolerance (no simplification during optimization)
                polygon, attempt_metadata = self._create_line_buffer_attempt(
                    points, buffer_dist, 0.0, mean_lat
                )

                if polygon is None:
                    continue

                # Calculate score based on goals
                score = self._score_line_buffer_result(
                    polygon, points, attempt_metadata
                )

                attempt_info = {
                    "buffer_multiplier": buf_mult,
                    "buffer_distance": buffer_dist,
                    "simplify_tolerance": 0.0,
                    "score": score,
                    "vertices": attempt_metadata.get("vertices", 0),
                    "data_coverage": attempt_metadata.get("data_coverage", 0),
                    "area_efficiency": attempt_metadata.get("area_efficiency", 0),
                }
                metadata["optimization_attempts"].append(attempt_info)

                if score > best_score:
                    best_score = score
                    best_polygon = polygon
                    best_params = attempt_info.copy()
                    
                    # Early termination if we achieve near-optimal score
                    # Raised threshold to allow more buffer exploration
                    if score >= 0.95:
                        print(f"    Near-optimal score achieved ({score:.3f}), stopping early")
                        break

            except Exception as e:
                print(
                    f"    Attempt failed (buf={buf_mult:.1f}): {e}"
                )
                continue

        if best_polygon is None:
            print("  No valid polygon found, using fallback")
            best_polygon, fallback_metadata = self._create_line_buffer_attempt(
                points, initial_buffer_distance, 0.0, mean_lat
            )
            best_params = fallback_metadata

        metadata.update(best_params)
        metadata["best_score"] = best_score
        metadata["total_attempts"] = len(metadata["optimization_attempts"])

        print(f"  Optimization: {best_params.get('buffer_distance', 0):.0f}m buffer, {best_params.get('vertices', 0)} vertices, {best_params.get('data_coverage', 0):.1%} coverage")

        return best_polygon, metadata

    def _create_line_buffer_attempt(
        self, points, buffer_distance, simplify_tolerance, mean_lat
    ):
        """
        Single attempt at creating a line buffer polygon with given parameters.
        """
        from shapely.geometry import LineString

        # Create line through points
        if len(points) < 2:
            return None, {}

        # For large datasets, sample points to create manageable line
        if len(points) > 100000:
            # For very dense data like LVIS, use aggressive sampling
            step = max(1, len(points) // 200)  # Sample to ~200 points
            sampled_points = points[::step]
        elif len(points) > 1000:
            # Normal sampling for moderately large datasets
            step = max(1, len(points) // 500)
            sampled_points = points[::step]
        else:
            sampled_points = points

        try:
            line = LineString(sampled_points)
        except Exception:
            return None, {}

        # Buffer the line
        try:
            buffered_line = self._buffer_in_meters(line, buffer_distance, mean_lat)
        except Exception:
            return None, {}

        # Apply simplification if requested
        if simplify_tolerance > 0:
            try:
                buffered_line = buffered_line.simplify(
                    simplify_tolerance, preserve_topology=True
                )
            except Exception:
                pass  # Continue with unsimplified version

        # Ensure valid polygon
        polygon = make_valid(buffered_line)

        # Handle MultiPolygon by taking largest component
        if isinstance(polygon, MultiPolygon):
            polygon = max(polygon.geoms, key=lambda p: p.area)

        # Calculate metrics
        coverage_info = self._calculate_data_coverage_metrics(polygon, points)

        metadata = {
            "vertices": len(polygon.exterior.coords) - 1
            if hasattr(polygon, "exterior")
            else 0,
            "buffer_distance": buffer_distance,
            "simplify_tolerance": simplify_tolerance,
            "sampled_points": len(sampled_points),
            "original_points": len(points),
        }
        metadata.update(coverage_info)

        return polygon, metadata

    def _score_line_buffer_result(self, polygon, points, metadata):
        """
        Score a line buffer result based on the optimization goals.

        Goals:
        1. Maximize data coverage (as close to 100% as possible) - PRIORITY
        2. Balance area efficiency with vertex count
        3. Prefer reasonable vertex counts (not too aggressive on reduction)
        """
        vertices = metadata.get("vertices", 0)
        data_coverage = metadata.get("data_coverage", 0)
        
        # Quick reject if too many vertices (performance optimization)
        if vertices > 1000:
            return 0.0
        
        # Prioritize 100% coverage but less aggressively
        if data_coverage < 1.0:
            # Moderate penalty for incomplete coverage (was 0.5, now 0.7)
            return data_coverage * 0.7
        
        # For 100% coverage, balance area efficiency and vertex count
        # Area efficiency is more important than vertex count for quality
        area_efficiency = 1.0 - metadata.get("estimated_non_data_ratio", 0.2)  # Default 80% efficiency
        
        # Vertex efficiency: be less aggressive about vertex reduction
        # Use a gentler curve that doesn't heavily penalize reasonable vertex counts
        if vertices <= 50:
            vertex_efficiency = 1.0  # No penalty for reasonable vertex counts
        elif vertices <= 200:
            vertex_efficiency = 0.9  # Small penalty
        elif vertices <= 500:
            vertex_efficiency = 0.7  # Moderate penalty
        else:
            vertex_efficiency = 0.5  # Larger penalty for very high vertex counts
        
        # Combined score with more balanced weights
        # Emphasize area efficiency over vertex reduction
        score = (
            0.8  # Base score for 100% coverage
            + 0.15 * area_efficiency  # 15% weight on area efficiency
            + 0.05 * vertex_efficiency  # 5% weight on vertex efficiency
        )
        
        return min(1.0, score)  # Cap at 1.0

    def _create_union_buffer_polygon_simple(
        self, points, buffer_distance, connect_regions, connection_buffer_multiplier
    ):
        """
        Simplified version for retry attempts - just does basic buffering without all the optimization.
        """
        # Use smaller subset for retry
        if len(points) > 200:
            indices = np.random.choice(len(points), 200, replace=False)
            selected_points = points[indices]
        else:
            selected_points = points

        mean_lat = np.mean(points[:, 1])

        # Simple buffering
        buffered_geoms = []
        for point in selected_points:
            p = Point(point)
            buffered = self._buffer_in_meters(p, buffer_distance, mean_lat)
            buffered_geoms.append(buffered)

        # Union all
        union_geom = unary_union(buffered_geoms)

        # Handle disconnected components simply
        if isinstance(union_geom, MultiPolygon):
            if len(union_geom.geoms) > 10:
                # Too many components, just take largest
                union_geom = max(union_geom.geoms, key=lambda p: p.area)
            elif connect_regions:
                # Simple connection for small number of components
                union_geom = self._connect_multipolygon_simple(
                    union_geom, buffer_distance * connection_buffer_multiplier, mean_lat
                )

        polygon = make_valid(union_geom)
        metadata = {"retry": True, "buffer_m": buffer_distance}

        return polygon, metadata

    def _connect_multipolygon_simple(self, multipoly, connection_buffer, center_lat):
        """
        Simple connection - just buffer the convex hull of centroids.
        """
        if len(multipoly.geoms) <= 1:
            return multipoly.geoms[0] if len(multipoly.geoms) == 1 else multipoly

        # Get centroids
        centroids = [p.centroid for p in multipoly.geoms]

        # Create convex hull of centroids and buffer it
        from shapely.geometry import MultiPoint

        centroid_points = MultiPoint(centroids)
        hull = centroid_points.convex_hull
        # Use reduced buffer for connection zone to minimize non-data area
        reduced_connection_buffer = connection_buffer * 0.3
        connection_zone = self._buffer_in_meters(hull, reduced_connection_buffer, center_lat)

        # Union everything
        all_geoms = list(multipoly.geoms) + [connection_zone]
        result = unary_union(all_geoms)

        if isinstance(result, MultiPolygon):
            result = max(result.geoms, key=lambda p: p.area)

        return make_valid(result)

    def _connect_multipolygon_advanced(
        self, multipoly, connection_buffer, center_lat, original_points
    ):
        """
        Advanced connection method that considers data distribution.

        This method tries to minimize non-data area when connecting components
        by choosing connection paths that follow data density patterns.
        """
        if len(multipoly.geoms) == 1:
            return multipoly.geoms[0]

        print(f"    Connecting {len(multipoly.geoms)} components...")

        # Get centroids and bounds of each polygon
        components = []
        for i, poly in enumerate(multipoly.geoms):
            components.append(
                {
                    "polygon": poly,
                    "centroid": poly.centroid,
                    "bounds": poly.bounds,
                    "area": poly.area,
                    "index": i,
                }
            )

        # Sort by area (largest first) to prioritize keeping large components
        components.sort(key=lambda x: x["area"], reverse=True)

        # For performance, limit to connecting only the largest components
        max_components_to_connect = min(20, len(components))
        if len(components) > max_components_to_connect:
            print(
                f"    Limiting connection to largest {max_components_to_connect} components"
            )
            components = components[:max_components_to_connect]

        # Use data-aware minimum spanning tree
        from scipy.spatial.distance import cdist
        from shapely.geometry import LineString

        # Calculate distances between all component centroids
        centroids = [comp["centroid"] for comp in components]
        centroid_coords = np.array([[c.x, c.y] for c in centroids])
        distances = cdist(centroid_coords, centroid_coords)

        # Weight distances by data density along connection paths
        weighted_distances = distances.copy()
        for i in range(len(components)):
            for j in range(i + 1, len(components)):
                # Create line between centroids
                line = LineString([centroids[i], centroids[j]])
                # Calculate data points near this connection line
                line_buffered = self._buffer_in_meters(
                    line, connection_buffer / 2, center_lat
                )

                # Count original data points within this connection zone
                data_in_connection = 0
                for point in original_points:
                    if line_buffered.contains(Point(point)):
                        data_in_connection += 1

                # If there's data along the connection path, prefer this connection
                # by reducing its weight
                if data_in_connection > 0:
                    data_density_factor = min(
                        0.5, data_in_connection / len(original_points)
                    )
                    weighted_distances[i, j] *= 1 - data_density_factor
                    weighted_distances[j, i] = weighted_distances[i, j]

        # Build minimum spanning tree using weighted distances
        connected = set([0])  # Start with largest component
        edges = []

        while len(connected) < len(components):
            min_dist = float("inf")
            min_edge = None

            for i in connected:
                for j in range(len(components)):
                    if j not in connected and weighted_distances[i, j] < min_dist:
                        min_dist = weighted_distances[i, j]
                        min_edge = (i, j)

            if min_edge:
                edges.append(min_edge)
                connected.add(min_edge[1])

        # Create connection lines and buffer them
        connection_lines = []
        for i, j in edges:
            line = LineString([centroids[i], centroids[j]])
            connection_lines.append(line)

        # Buffer the connection lines with reduced buffer for minimal non-data area
        buffered_connections = []
        for line in connection_lines:
            # Use smaller buffer for connections to minimize non-data area
            reduced_buffer = connection_buffer * 0.5
            buffered = self._buffer_in_meters(line, reduced_buffer, center_lat)
            buffered_connections.append(buffered)

        print(f"    Created {len(buffered_connections)} connections")

        # Union all components and connections
        all_geoms = [comp["polygon"] for comp in components] + buffered_connections
        result = unary_union(all_geoms)

        # Return largest polygon if still multi
        if isinstance(result, MultiPolygon):
            result = max(result.geoms, key=lambda p: p.area)

        return make_valid(result)

    def _calculate_data_coverage_metrics(self, polygon, points):
        """
        Calculate metrics about how well the polygon covers data vs non-data areas.

        This provides guidance for the smoothing process.
        """
        from shapely.geometry import Point

        # Sample points to check coverage
        sample_size = min(1000, len(points))
        if sample_size < len(points):
            indices = np.random.choice(len(points), sample_size, replace=False)
            sample_points = points[indices]
        else:
            sample_points = points

        # Count data points inside polygon
        points_inside = 0
        for point in sample_points:
            if polygon.contains(Point(point)):
                points_inside += 1

        data_coverage = (
            points_inside / len(sample_points) if len(sample_points) > 0 else 0
        )

        # Estimate non-data coverage using polygon area vs data distribution
        # Calculate data bounding box area
        min_x, min_y = np.min(points, axis=0)
        max_x, max_y = np.max(points, axis=0)
        data_bounds_area = (max_x - min_x) * (max_y - min_y)

        # Convert polygon area to degrees² for comparison
        polygon_area = polygon.area

        # Rough estimate of non-data ratio
        if data_bounds_area > 0:
            area_expansion = polygon_area / data_bounds_area
            # If polygon is much larger than data bounds, likely more non-data coverage
            estimated_non_data_ratio = max(
                0, min(1, (area_expansion - 1) / area_expansion)
            )
        else:
            estimated_non_data_ratio = 0

        # Vertex count for smoothing guidance
        if hasattr(polygon, "exterior"):
            vertices = len(polygon.exterior.coords) - 1
        else:
            vertices = 0

        return {
            "data_coverage": data_coverage,
            "estimated_non_data_ratio": estimated_non_data_ratio,
            "vertices": vertices,
            "polygon_area_deg2": polygon_area,
            "data_bounds_area_deg2": data_bounds_area,
            "area_expansion_factor": polygon_area / data_bounds_area
            if data_bounds_area > 0
            else 0,
        }
