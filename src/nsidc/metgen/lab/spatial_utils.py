"""
Spatial utilities for polygon operations and UMM-G parsing.

This module contains utilities extracted from the original cmr_client module
that are not replaced by earthaccess functionality.
"""

import re
import warnings

import geopandas as gpd
import numpy as np
from shapely.geometry import Point

warnings.filterwarnings("ignore", category=FutureWarning)


def sanitize_granule_ur(granule_ur):
    """
    Sanitize granule UR for use as filename/directory name.

    Parameters:
    -----------
    granule_ur : str
        Granule UR to sanitize

    Returns:
    --------
    str : Sanitized granule UR safe for filesystem use
    """
    # Replace problematic characters with underscores
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", granule_ur)
    # Remove any trailing dots or spaces
    sanitized = sanitized.rstrip(". ")
    # Limit length to 255 characters for filesystem compatibility
    return sanitized[:255]


class UMMGParser:
    """Parser for UMM-G (Unified Metadata Model for Granules) data."""

    @staticmethod
    def extract_polygons(umm_json, granule_ur=None):
        """
        Extract polygon information from UMM-G JSON.

        Parameters:
        -----------
        umm_json : dict
            UMM-G JSON response
        granule_ur : str, optional
            Granule UR for error messages

        Returns:
        --------
        dict : GeoJSON FeatureCollection
        """
        features = []

        try:
            # Handle both direct UMM-G and wrapped format
            if "umm" in umm_json:
                umm_json = umm_json["umm"]

            spatial_extent = umm_json.get("SpatialExtent", {})
            horizontal_extent = spatial_extent.get("HorizontalSpatialDomain", {})
            geometry = horizontal_extent.get("Geometry", {})

            # Extract GPolygons
            gpolygons = geometry.get("GPolygons", [])
            for idx, gpoly in enumerate(gpolygons):
                boundary = gpoly.get("Boundary", {})
                points = boundary.get("Points", [])

                if len(points) >= 3:
                    # Extract coordinates
                    coords = [[p["Longitude"], p["Latitude"]] for p in points]

                    # Ensure polygon is closed
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])

                    feature = {
                        "type": "Feature",
                        "properties": {
                            "source": "CMR UMM-G",
                            "polygon_type": "GPolygon",
                            "index": idx,
                        },
                        "geometry": {"type": "Polygon", "coordinates": [coords]},
                    }
                    features.append(feature)

        except Exception as e:
            print(f"Error extracting polygons from UMM-G: {e}")
            if granule_ur:
                print(f"Granule: {granule_ur}")

        return {"type": "FeatureCollection", "features": features}

    @staticmethod
    def extract_data_urls(umm_json):
        """
        Extract data file URLs from UMM-G JSON.

        Parameters:
        -----------
        umm_json : dict
            UMM-G JSON response

        Returns:
        --------
        list : List of data URLs
        """
        urls = []

        try:
            # Handle both direct UMM-G and wrapped format
            if "umm" in umm_json:
                umm_json = umm_json["umm"]

            # Extract from RelatedUrls
            related_urls = umm_json.get("RelatedUrls", [])
            for url_info in related_urls:
                url_type = url_info.get("Type", "")
                url = url_info.get("URL", "")

                # Look for data URLs
                if url and url_type in ["GET DATA", "GET DATA VIA DIRECT ACCESS"]:
                    urls.append(url)

        except Exception as e:
            print(f"Error extracting data URLs: {e}")

        return urls

    @staticmethod
    def find_data_file(urls, extensions=None):
        """
        Find the first data file URL matching the given extensions.

        Parameters:
        -----------
        urls : list
            List of URLs to search
        extensions : list, optional
            List of file extensions to match (e.g., ['.h5', '.HDF5'])

        Returns:
        --------
        str or None : First matching URL or None
        """
        if not urls:
            return None

        if not extensions:
            # Return first URL if no extensions specified
            return urls[0] if urls else None

        # Normalize extensions to lowercase for comparison
        extensions_lower = [ext.lower() for ext in extensions]

        for url in urls:
            url_lower = url.lower()
            for ext in extensions_lower:
                if url_lower.endswith(ext):
                    return url

        return None


class PolygonComparator:
    """Utilities for comparing spatial polygons."""

    @staticmethod
    def compare(cmr_geojson, generated_geojson, data_points=None):
        """
        Compare CMR and generated polygons.

        Parameters:
        -----------
        cmr_geojson : dict
            CMR polygon as GeoJSON
        generated_geojson : dict
            Generated polygon as GeoJSON
        data_points : array-like, optional
            Nx2 array of [lon, lat] points for coverage calculation

        Returns:
        --------
        dict : Comparison metrics
        """
        metrics = {}

        try:
            # Convert to GeoDataFrames
            cmr_gdf = gpd.GeoDataFrame.from_features(cmr_geojson["features"])
            gen_gdf = gpd.GeoDataFrame.from_features(generated_geojson["features"])

            if cmr_gdf.empty or gen_gdf.empty:
                return {"error": "Empty polygon data"}

            # Get first polygon from each
            cmr_poly = cmr_gdf.geometry.iloc[0]
            gen_poly = gen_gdf.geometry.iloc[0]

            # Basic metrics
            metrics["cmr_area"] = cmr_poly.area
            metrics["generated_area"] = gen_poly.area
            metrics["area_ratio"] = (
                gen_poly.area / cmr_poly.area if cmr_poly.area > 0 else 0
            )

            # Vertex counts
            metrics["cmr_vertices"] = len(cmr_poly.exterior.coords) - 1
            metrics["generated_vertices"] = len(gen_poly.exterior.coords) - 1

            # Overlap metrics
            intersection = cmr_poly.intersection(gen_poly)
            union = cmr_poly.union(gen_poly)

            metrics["intersection_area"] = intersection.area
            metrics["union_area"] = union.area
            metrics["iou"] = intersection.area / union.area if union.area > 0 else 0

            # Coverage of CMR by generated
            metrics["cmr_coverage_by_generated"] = (
                intersection.area / cmr_poly.area if cmr_poly.area > 0 else 0
            )

            # Coverage of generated by CMR
            metrics["generated_coverage_by_cmr"] = (
                intersection.area / gen_poly.area if gen_poly.area > 0 else 0
            )

            # Data coverage if points provided
            if data_points is not None and len(data_points) > 0:
                cmr_coverage = PolygonComparator._calculate_data_coverage(
                    cmr_poly, data_points
                )
                gen_coverage = PolygonComparator._calculate_data_coverage(
                    gen_poly, data_points
                )

                metrics["cmr_data_coverage"] = cmr_coverage
                metrics["generated_data_coverage"] = gen_coverage
                metrics["data_coverage_improvement"] = gen_coverage - cmr_coverage

        except Exception as e:
            metrics["error"] = str(e)

        return metrics

    @staticmethod
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
