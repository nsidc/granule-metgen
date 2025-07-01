"""
Polygon Generation Module for LVIS Flightline Processing

This module provides polygon generation using buffer-based methods
(buffer, beam, and adaptive_beam) with iterative simplification.
"""


import numpy as np
import pyproj
from shapely.geometry import MultiPolygon, Point, Polygon
from shapely.ops import unary_union
from shapely.validation import make_valid

from .simplification import iterative_simplify_polygon


class PolygonGenerator:
    """Main class for polygon generation with buffer-based methods."""

    def __init__(self):
        """Initialize the polygon generator."""
        self.default_buffer = 300  # meters
        self.min_buffer = 200
        self.max_buffer = 1000

    def create_flightline_polygon(
        self,
        lon,
        lat,
        method="adaptive_beam",
        buffer_distance=None,
        sample_size=None,
        connect_regions=True,
        connection_buffer_multiplier=3.0,
        iterative_simplify=False,
        target_vertices=None,
        min_iou=0.85,
        min_coverage=0.90,
    ):
        """
        Create a polygon representing the flightline coverage.

        Parameters:
        -----------
        lon, lat : array-like
            Longitude and latitude coordinates
        method : str
            Method to use: 'buffer', 'beam', 'adaptive_beam'
        buffer_distance : float
            Buffer distance in meters (if None, uses adaptive sizing for adaptive_beam)
        sample_size : int
            Number of points to sample for beam methods
        connect_regions : bool
            Whether to connect disconnected regions
        connection_buffer_multiplier : float
            Multiplier for connection buffer size
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
        polygon : shapely.geometry.Polygon or None
            The generated polygon
        metadata : dict
            Metadata about the generation process
        """
        # Filter out invalid coordinates
        mask = np.isfinite(lon) & np.isfinite(lat)
        lon = np.array(lon)[mask]
        lat = np.array(lat)[mask]

        metadata = {
            "method": method,
            "points": len(lon),
            "original_buffer": buffer_distance,
        }

        # Handle empty or insufficient data
        if len(lon) == 0:
            print("No valid coordinates found")
            metadata["vertices"] = 0
            return None, metadata

        if len(lon) == 1:
            # Single point - create a buffer around it
            if buffer_distance is None:
                buffer_distance = self.default_buffer
            point = Point(lon[0], lat[0])
            polygon = self._buffer_in_meters(point, buffer_distance, lat[0])
            metadata["buffer_m"] = buffer_distance
            metadata["vertices"] = len(polygon.exterior.coords) - 1
            return polygon, metadata

        if len(lon) < 3:
            print(f"Only {len(lon)} valid coordinates, creating buffered line")
            # Create line and buffer it
            if buffer_distance is None:
                buffer_distance = self.default_buffer
            from shapely.geometry import LineString

            line = LineString(zip(lon, lat))
            polygon = self._buffer_in_meters(line, buffer_distance, np.mean(lat))
            metadata["buffer_m"] = buffer_distance
            metadata["vertices"] = len(polygon.exterior.coords) - 1
            return polygon, metadata

        # Create points array
        points = np.column_stack((lon, lat))

        # Handle different methods
        if method == "buffer":
            if buffer_distance is None:
                buffer_distance = self.default_buffer
            polygon = self._create_buffer_polygon(points, buffer_distance)
            metadata["buffer_m"] = buffer_distance

        elif method in ["beam", "adaptive_beam"]:
            if method == "adaptive_beam" and buffer_distance is None:
                # Use adaptive buffer sizing
                buffer_distance = self.estimate_optimal_buffer(lon, lat)
                metadata["adaptive_buffer"] = buffer_distance
                print(f"  Calculated adaptive buffer: {buffer_distance:.0f}m")
            elif buffer_distance is None:
                buffer_distance = self.default_buffer

            polygon, beam_metadata = self._create_beam_polygon(
                points,
                buffer_distance,
                sample_size,
                connect_regions,
                connection_buffer_multiplier,
            )
            metadata["buffer_m"] = buffer_distance
            metadata.update(beam_metadata)  # Include sample_size and other metadata

        else:
            raise ValueError(
                f"Unknown method: {method}. Supported methods: buffer, beam, adaptive_beam"
            )

        # Apply iterative simplification if requested
        if iterative_simplify and polygon is not None:
            # Use all data points for better coverage calculation
            data_points = points

            simplified, history = iterative_simplify_polygon(
                polygon,
                data_points=data_points,
                target_vertices=target_vertices,
                min_iou=min_iou,
                min_coverage=min_coverage,
            )

            polygon = simplified
            metadata["simplification_history"] = history

            if history:
                print(
                    f"  Simplified from {history[0]['vertices']} to {history[-1]['vertices']} vertices"
                )

        # Add final vertex count
        if polygon is not None:
            if hasattr(polygon, "exterior"):
                metadata["vertices"] = len(polygon.exterior.coords) - 1
            else:
                metadata["vertices"] = 0
        else:
            metadata["vertices"] = 0

        return polygon, metadata

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

        # Determine UTM zone
        utm_zone = int((center_lon + 180) / 6) + 1

        # Create projection
        if center_lat >= 0:
            proj_string = f"+proj=utm +zone={utm_zone} +north +datum=WGS84"
        else:
            proj_string = f"+proj=utm +zone={utm_zone} +south +datum=WGS84"

        # Create transformers
        to_utm = pyproj.Transformer.from_crs("EPSG:4326", proj_string, always_xy=True)
        to_wgs = pyproj.Transformer.from_crs(proj_string, "EPSG:4326", always_xy=True)

        # Transform to UTM, buffer, transform back
        from shapely.ops import transform

        geom_utm = transform(to_utm.transform, geom)
        buffered_utm = geom_utm.buffer(buffer_distance)
        buffered = transform(to_wgs.transform, buffered_utm)

        return buffered

    def _create_buffer_polygon(self, points, buffer_distance):
        """
        Create polygon by buffering all points.

        Parameters:
        -----------
        points : array-like
            Nx2 array of lon/lat coordinates
        buffer_distance : float
            Buffer distance in meters

        Returns:
        --------
        polygon : shapely.geometry.Polygon
            Buffered polygon
        """
        if len(points) > 10000:
            # For very large datasets, use convex hull as base
            from scipy.spatial import ConvexHull

            hull = ConvexHull(points)
            hull_points = points[hull.vertices]
            base_polygon = Polygon(hull_points)
            polygon = self._buffer_in_meters(
                base_polygon, buffer_distance, np.mean(points[:, 1])
            )
        else:
            # Buffer each point and union
            from shapely.geometry import MultiPoint

            multipoint = MultiPoint(points)
            polygon = self._buffer_in_meters(
                multipoint, buffer_distance, np.mean(points[:, 1])
            )

        # Ensure we return a single Polygon, not MultiPolygon
        polygon = make_valid(polygon)
        if isinstance(polygon, MultiPolygon):
            # Take the largest polygon
            polygon = max(polygon.geoms, key=lambda p: p.area)

        return polygon

    def _create_beam_polygon(
        self,
        points,
        buffer_distance,
        sample_size=None,
        connect_regions=True,
        connection_buffer_multiplier=3.0,
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
