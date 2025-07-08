"""
CMR Integration Module for NASA Common Metadata Repository

This module provides functionality for querying CMR, retrieving UMM-G data,
extracting polygons and data URLs, and comparing polygons.
"""

import json
import os
import re
import warnings
from datetime import datetime

import geopandas as gpd
import requests

warnings.filterwarnings("ignore", category=FutureWarning)


class CMRClient:
    """Client for interacting with NASA's Common Metadata Repository."""

    def __init__(self, base_url="https://cmr.earthdata.nasa.gov", token=None):
        """
        Initialize CMR client.

        Parameters:
        -----------
        base_url : str
            Base URL for CMR API
        token : str, optional
            Bearer token for authentication
        """
        self.base_url = base_url
        self.token = token or os.getenv("CMR_TOKEN")
        self.session = requests.Session()

        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"

    def query_granules(
        self,
        short_name,
        provider=None,
        limit=2000,
        temporal=None,
        bounding_box=None,
        sort_key=None,
        page_size=100,
    ):
        """
        Query CMR for granules by collection short name.

        Parameters:
        -----------
        short_name : str
            Collection short name
        provider : str, optional
            Data provider (e.g., 'NSIDC_ECS', 'LPDAAC_ECS')
        limit : int
            Maximum number of granules to return
        temporal : tuple, optional
            (start_date, end_date) in ISO format
        bounding_box : tuple, optional
            (west, south, east, north) in decimal degrees
        sort_key : str, optional
            Sort key (e.g., '-start_date' for newest first)
        page_size : int
            Number of results per page

        Returns:
        --------
        list : List of granule entries
        """
        endpoint = f"{self.base_url}/search/granules.json"

        params = {"short_name": short_name, "page_size": min(page_size, limit)}

        if provider:
            params["provider"] = provider
        if temporal:
            params["temporal"] = f"{temporal[0]},{temporal[1]}"
        if bounding_box:
            params["bounding_box"] = (
                f"{bounding_box[0]},{bounding_box[1]},{bounding_box[2]},{bounding_box[3]}"
            )
        if sort_key:
            params["sort_key"] = sort_key

        all_granules = []
        page_num = 1

        while len(all_granules) < limit:
            params["page_num"] = page_num

            response = self.session.get(endpoint, params=params)
            response.raise_for_status()

            data = response.json()
            entries = data.get("feed", {}).get("entry", [])

            if not entries:
                break

            all_granules.extend(entries)

            # Check if we've retrieved all available granules
            total_hits = int(response.headers.get("cmr-hits", "0"))
            if len(all_granules) >= total_hits or len(entries) < page_size:
                break

            page_num += 1

        return all_granules[:limit]

    def get_umm_json(self, concept_id):
        """
        Get UMM-JSON metadata for a specific granule.

        Parameters:
        -----------
        concept_id : str
            CMR concept ID for the granule

        Returns:
        --------
        dict : UMM-G JSON document
        """
        endpoint = f"{self.base_url}/search/concepts/{concept_id}.umm_json"

        response = self.session.get(endpoint)
        response.raise_for_status()

        return response.json()

    def get_random_granules(self, short_name, provider=None, count=10):
        """
        Get random granules from a collection.

        Parameters:
        -----------
        short_name : str
            Collection short name
        provider : str, optional
            Data provider
        count : int
            Number of random granules to return

        Returns:
        --------
        list : List of randomly selected granule entries
        """
        # First get total count
        endpoint = f"{self.base_url}/search/granules.json"
        params = {"short_name": short_name, "page_size": 1}
        if provider:
            params["provider"] = provider

        response = self.session.get(endpoint, params=params)
        response.raise_for_status()

        total_hits = int(response.headers.get("cmr-hits", "0"))

        if total_hits == 0:
            return []

        print(f"Collection {short_name} has {total_hits:,} total granules")

        # For small collections (<=2000 granules), just get all and sample
        if total_hits <= 2000:
            print(
                f"Small collection detected, fetching all {total_hits} granules for sampling..."
            )
            all_granules = self.query_granules(
                short_name, provider=provider, limit=total_hits
            )
            import random

            return random.sample(all_granules, min(count, len(all_granules)))

        # For medium collections (2K-10K), use pagination-based sampling
        elif total_hits <= 10000 and count <= 50:
            print("Medium collection detected, using pagination sampling...")
            import random

            # Calculate random page offsets to sample from different parts of the collection
            max_pages = min(
                total_hits // 20, 100
            )  # 20 granules per page, max 100 pages
            random_pages = random.sample(
                range(max_pages), min(count // 5 + 1, max_pages)
            )

            sampled_granules = []
            seen_ids = set()

            for page in random_pages:
                # CMR uses page_num, not offset - calculate page number
                page_num = page + 1  # CMR pages are 1-indexed

                # Get granules from this page by using the page_num in query
                endpoint = f"{self.base_url}/search/granules.json"
                params = {
                    "short_name": short_name,
                    "page_size": 20,
                    "page_num": page_num,
                }
                if provider:
                    params["provider"] = provider

                response = self.session.get(endpoint, params=params)
                response.raise_for_status()
                data = response.json()
                page_granules = data.get("feed", {}).get("entry", [])

                for g in page_granules:
                    g_id = g.get("id", "")
                    if g_id not in seen_ids:
                        seen_ids.add(g_id)
                        sampled_granules.append(g)
                        if len(sampled_granules) >= count:
                            break

                if len(sampled_granules) >= count:
                    break

            return sampled_granules[:count]

        # For large collections, use temporal sampling
        import random

        random_granules = []
        seen_ids = set()

        # Get collection temporal extent
        first_granules = self.query_granules(
            short_name, provider=provider, limit=1, sort_key="start_date"
        )
        if not first_granules:
            return []

        last_granules = self.query_granules(
            short_name, provider=provider, limit=1, sort_key="-start_date"
        )
        if not last_granules:
            return []

        start_date = first_granules[0].get("time_start", "2000-01-01T00:00:00Z")
        end_date = last_granules[0].get("time_end", datetime.utcnow().isoformat() + "Z")

        # Sample random time windows
        from datetime import timedelta

        start_dt = datetime.fromisoformat(start_date.rstrip("Z"))
        end_dt = datetime.fromisoformat(end_date.rstrip("Z"))

        # If temporal range is too small, just get recent granules
        if (end_dt - start_dt).days < 14:
            return self.query_granules(short_name, provider=provider, limit=count)

        # More efficient approach: Use larger time windows with higher limits
        # and sample from the results, reducing the number of API calls

        total_days = (end_dt - start_dt).days

        if total_days > 365:
            # For collections spanning multiple years, use monthly sampling
            window_days = 30
            granules_per_query = min(50, count * 2)  # Get more granules per query
        elif total_days > 30:
            # For collections spanning months, use weekly sampling
            window_days = 7
            granules_per_query = min(25, count * 2)
        else:
            # For short collections, use daily sampling
            window_days = 1
            granules_per_query = min(10, count * 2)

        attempts = 0
        max_attempts = min(count, 20)  # Cap max attempts to reasonable number

        print(
            f"Sampling {count} random granules from {short_name} (spanning {total_days} days)..."
        )

        while len(random_granules) < count and attempts < max_attempts:
            attempts += 1

            # Random date in range
            random_seconds = random.randint(0, int((end_dt - start_dt).total_seconds()))
            random_date = start_dt + timedelta(seconds=random_seconds)

            # Query larger window around random date
            window_start = (random_date - timedelta(days=window_days)).isoformat() + "Z"
            window_end = (random_date + timedelta(days=window_days)).isoformat() + "Z"

            granules = self.query_granules(
                short_name,
                provider=provider,
                limit=granules_per_query,
                temporal=(window_start, window_end),
            )

            # Randomly sample from returned granules to add variety
            if granules:
                import random

                sample_size = min(len(granules), count - len(random_granules))
                sampled_granules = random.sample(granules, sample_size)

                # Add unique granules
                for g in sampled_granules:
                    g_id = g.get("id", "")
                    if g_id not in seen_ids:
                        seen_ids.add(g_id)
                        random_granules.append(g)
                        if len(random_granules) >= count:
                            break

                # Progress feedback for large requests
                if count >= 20 and len(random_granules) % 10 == 0:
                    print(f"  Found {len(random_granules)}/{count} granules...")
            else:
                # No granules in this time window, try different approach
                if attempts > max_attempts // 2:
                    # After half the attempts, expand window size to increase hit rate
                    window_days = min(window_days * 2, 90)
                    granules_per_query = min(granules_per_query * 2, 100)

        # If we couldn't get enough random granules, fill with recent ones
        if len(random_granules) < count:
            remaining = count - len(random_granules)
            print(f"  Filling remaining {remaining} granules with recent ones...")

            recent = self.query_granules(
                short_name,
                provider=provider,
                limit=remaining * 2,  # Get extra to account for duplicates
                sort_key="-start_date",
            )
            for g in recent:
                g_id = g.get("id", "")
                if g_id not in seen_ids:
                    random_granules.append(g)
                    if len(random_granules) >= count:
                        break

        return random_granules[:count]


class UMMGParser:
    """Parser for extracting data from UMM-G JSON documents."""

    @staticmethod
    def extract_polygons(umm_json, granule_ur=None):
        """
        Extract spatial polygons as GeoJSON.

        Parameters:
        -----------
        umm_json : dict
            UMM-G JSON document
        granule_ur : str, optional
            Granule UR for properties

        Returns:
        --------
        dict : GeoJSON FeatureCollection
        """
        spatial_extent = umm_json.get("SpatialExtent", {})
        horizontal_extent = spatial_extent.get("HorizontalSpatialDomain", {})

        features = []

        # Extract GPolygons
        geometry = horizontal_extent.get("Geometry", {})
        gpolygons = geometry.get("GPolygons", [])

        for i, gpoly in enumerate(gpolygons):
            boundary = gpoly.get("Boundary", {})
            points = boundary.get("Points", [])

            if len(points) >= 3:
                # Convert to coordinates
                coords = [[p["Longitude"], p["Latitude"]] for p in points]

                # Ensure polygon is closed
                if coords[0] != coords[-1]:
                    coords.append(coords[0])

                feature = {
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [coords]},
                    "properties": {
                        "source": "UMM-G",
                        "type": "GPolygon",
                        "index": i,
                        "granule_ur": granule_ur
                        or umm_json.get("GranuleUR", "Unknown"),
                    },
                }
                features.append(feature)

        # Extract BoundingRectangles if no GPolygons
        if not features:
            bounding_rects = geometry.get("BoundingRectangles", [])

            for i, rect in enumerate(bounding_rects):
                west = rect.get("WestBoundingCoordinate")
                east = rect.get("EastBoundingCoordinate")
                north = rect.get("NorthBoundingCoordinate")
                south = rect.get("SouthBoundingCoordinate")

                if all(v is not None for v in [west, east, north, south]):
                    # Create rectangle
                    coords = [
                        [west, south],
                        [east, south],
                        [east, north],
                        [west, north],
                        [west, south],
                    ]

                    feature = {
                        "type": "Feature",
                        "geometry": {"type": "Polygon", "coordinates": [coords]},
                        "properties": {
                            "source": "UMM-G",
                            "type": "BoundingRectangle",
                            "index": i,
                            "granule_ur": granule_ur
                            or umm_json.get("GranuleUR", "Unknown"),
                        },
                    }
                    features.append(feature)

        return {"type": "FeatureCollection", "features": features}

    @staticmethod
    def extract_data_urls(umm_json):
        """
        Extract data file URLs from UMM-G.

        Parameters:
        -----------
        umm_json : dict
            UMM-G JSON document

        Returns:
        --------
        list : List of data URLs
        """
        urls = []

        # Check RelatedUrls
        related_urls = umm_json.get("RelatedUrls", [])
        for url_info in related_urls:
            if url_info.get("Type") == "GET DATA":
                url = url_info.get("URL", "")

                # Convert S3 URLs to HTTPS
                if url.startswith("s3://"):
                    url = url.replace("s3://", "https://s3.amazonaws.com/")
                    url = url.replace("nsidc-cumulus-prod-protected/", "")

                if url:
                    urls.append(url)

        # Check DataGranule.ArchiveAndDistributionInformation
        data_granule = umm_json.get("DataGranule", {})
        archive_info = data_granule.get("ArchiveAndDistributionInformation", [])

        for info in archive_info:
            url = info.get("DirectDistributionInformation", {}).get(
                "S3BucketAndObjectPrefixNames", [""]
            )[0]
            if url:
                # Convert S3 path to URL
                if not url.startswith("http"):
                    url = f"https://s3.amazonaws.com/{url}"
                urls.append(url)

        return urls

    @staticmethod
    def find_data_file(urls, extensions=[".TXT", ".txt", ".h5", ".HDF5", ".nc"]):
        """
        Find appropriate data file from URL list.

        Parameters:
        -----------
        urls : list
            List of URLs
        extensions : list
            Preferred file extensions

        Returns:
        --------
        str or None : Selected data file URL
        """
        for url in urls:
            for ext in extensions:
                if url.endswith(ext):
                    return url

        # Return None if no extension match
        return None


class PolygonComparator:
    """Compare polygons from different sources."""

    @staticmethod
    def compare(cmr_geojson, generated_geojson, data_points=None):
        """
        Compare CMR and generated polygons.

        Parameters:
        -----------
        cmr_geojson : dict or str
            CMR polygon as GeoJSON dict or file path
        generated_geojson : dict or str
            Generated polygon as GeoJSON dict or file path
        data_points : np.ndarray, optional
            Array of (lon, lat) data points to calculate coverage

        Returns:
        --------
        dict : Comparison metrics
        """
        # Load GeoJSON if file paths provided
        if isinstance(cmr_geojson, str):
            with open(cmr_geojson, "r") as f:
                cmr_geojson = json.load(f)

        if isinstance(generated_geojson, str):
            with open(generated_geojson, "r") as f:
                generated_geojson = json.load(f)

        # Convert to GeoDataFrames with explicit geometry column
        if cmr_geojson["features"]:
            cmr_gdf = gpd.GeoDataFrame.from_features(cmr_geojson["features"])
            cmr_geom = cmr_gdf.union_all()
        else:
            from shapely.geometry import Polygon

            cmr_geom = Polygon()  # Empty polygon

        if generated_geojson["features"]:
            generated_gdf = gpd.GeoDataFrame.from_features(
                generated_geojson["features"]
            )
            generated_geom = generated_gdf.union_all()
        else:
            from shapely.geometry import Polygon

            generated_geom = Polygon()  # Empty polygon

        # Calculate metrics
        metrics = {}

        # Areas
        cmr_area = cmr_geom.area
        generated_area = generated_geom.area
        metrics["cmr_area_deg2"] = cmr_area
        metrics["generated_area_deg2"] = generated_area
        metrics["area_ratio"] = generated_area / cmr_area if cmr_area > 0 else 0

        # Intersection over Union (IoU)
        intersection = cmr_geom.intersection(generated_geom).area
        union = cmr_geom.union(generated_geom).area
        metrics["iou"] = intersection / union if union > 0 else 0

        # Coverage percentages
        metrics["cmr_covered_by_generated"] = (
            intersection / cmr_area if cmr_area > 0 else 0
        )
        metrics["generated_covered_by_cmr"] = (
            intersection / generated_area if generated_area > 0 else 0
        )

        # Vertex counts
        if cmr_geom.is_empty:
            metrics["cmr_vertices"] = 0
        elif hasattr(cmr_geom, "exterior"):
            metrics["cmr_vertices"] = len(cmr_geom.exterior.coords) - 1
        else:
            # MultiPolygon case
            metrics["cmr_vertices"] = sum(
                len(p.exterior.coords) - 1 for p in cmr_geom.geoms
            )

        if generated_geom.is_empty:
            metrics["generated_vertices"] = 0
        elif hasattr(generated_geom, "exterior"):
            metrics["generated_vertices"] = len(generated_geom.exterior.coords) - 1
        else:
            metrics["generated_vertices"] = sum(
                len(p.exterior.coords) - 1 for p in generated_geom.geoms
            )

        # Distance metrics
        if not cmr_geom.is_empty and not generated_geom.is_empty:
            metrics["hausdorff_distance"] = cmr_geom.hausdorff_distance(generated_geom)
            metrics["centroid_distance"] = cmr_geom.centroid.distance(
                generated_geom.centroid
            )
        else:
            metrics["hausdorff_distance"] = float("inf")
            metrics["centroid_distance"] = float("inf")

        # Data coverage metrics (if data points provided)
        if data_points is not None and len(data_points) > 0:
            import numpy as np
            from shapely.geometry import Point

            # Sample if too many points for performance
            if len(data_points) > 10000:
                indices = np.random.choice(len(data_points), 10000, replace=False)
                sample_points = data_points[indices]
            else:
                sample_points = data_points

            # Calculate how many data points each polygon covers
            cmr_coverage_count = 0
            generated_coverage_count = 0

            for point in sample_points:
                pt = Point(point[0], point[1])
                if cmr_geom.contains(pt):
                    cmr_coverage_count += 1
                if generated_geom.contains(pt):
                    generated_coverage_count += 1

            total_points = len(sample_points)
            metrics["cmr_data_coverage"] = (
                cmr_coverage_count / total_points if total_points > 0 else 0
            )
            metrics["generated_data_coverage"] = (
                generated_coverage_count / total_points if total_points > 0 else 0
            )
            metrics["data_coverage_ratio"] = (
                metrics["generated_data_coverage"] / metrics["cmr_data_coverage"]
                if metrics["cmr_data_coverage"] > 0
                else 0
            )

            # Calculate non-data coverage using adaptive random sampling method
            # Use data-adaptive radius based on bounding box

            from scipy.spatial import cKDTree

            # Build KDTree for efficient nearest neighbor search
            data_tree = cKDTree(sample_points)

            # Calculate adaptive radius based on data bounding box
            data_bounds = np.array(sample_points)
            min_lon, min_lat = data_bounds.min(axis=0)
            max_lon, max_lat = data_bounds.max(axis=0)

            # Find smaller dimension of bounding box
            width = max_lon - min_lon
            height = max_lat - min_lat
            smaller_dimension = min(width, height)

            # Set radius as 2% of smaller dimension
            adaptive_radius = smaller_dimension * 0.02
            print(
                f"    Using adaptive radius: {adaptive_radius * 111000:.0f}m (2% of {smaller_dimension * 111000:.0f}m bounding box)"
            )

            # Function to estimate non-data coverage for a polygon with given parameters
            def estimate_coverage_with_params(polygon, radius, num_samples):
                # Get polygon bounds
                minx, miny, maxx, maxy = polygon.bounds

                # Generate random points within bounds
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
                    nearby_indices = data_tree.query_ball_point(rp, radius)
                    if len(nearby_indices) > 0:
                        points_with_data += 1

                # Non-data coverage is proportion of points without nearby data
                data_coverage = points_with_data / len(random_points)
                non_data_coverage = 1.0 - data_coverage

                # Debug output
                if len(random_points) >= 1000:  # Only for final calculations
                    print(
                        f"        Sampled {len(random_points)} points: {points_with_data} have data, "
                        f"{len(random_points) - points_with_data} are empty"
                    )
                    print(
                        f"        Data coverage: {data_coverage:.1%}, Non-data coverage: {non_data_coverage:.1%}"
                    )

                return non_data_coverage

            # Function to find converged parameters
            def find_converged_coverage(polygon, convergence_threshold=0.01):
                # Use the adaptive radius calculated from data bounds
                radius = adaptive_radius

                # Try different sample sizes to find convergence
                sample_sizes = [500, 1000, 2000, 4000, 8000]

                best_samples = sample_sizes[1]  # Default 1000

                # Find convergence for sample size
                prev_coverage = None
                converged = False

                for samples in sample_sizes:
                    coverage = estimate_coverage_with_params(polygon, radius, samples)

                    if prev_coverage is not None:
                        # Check if converged (difference < 1%)
                        if abs(coverage - prev_coverage) < convergence_threshold:
                            best_samples = samples
                            converged = True
                            print(
                                f"        Converged at {samples} samples (change < 1%)"
                            )
                            break
                    prev_coverage = coverage

                if not converged:
                    best_samples = sample_sizes[-1]  # Use largest if no convergence
                    print(f"        No convergence found, using {best_samples} samples")

                # Final calculation with converged parameters
                final_coverage = estimate_coverage_with_params(
                    polygon, radius, best_samples
                )

                return final_coverage, radius, best_samples

            # Calculate for both polygons with adaptive parameters
            print("    Calculating non-data coverage...")
            cmr_coverage, cmr_radius, cmr_samples = find_converged_coverage(cmr_geom)
            print(
                f"      CMR polygon: converged at {cmr_samples} samples, {cmr_radius * 111000:.0f}m radius"
            )

            gen_coverage, gen_radius, gen_samples = find_converged_coverage(
                generated_geom
            )
            print(
                f"      Generated polygon: converged at {gen_samples} samples, {gen_radius * 111000:.0f}m radius"
            )

            metrics["cmr_non_data_coverage"] = cmr_coverage
            metrics["generated_non_data_coverage"] = gen_coverage

            # Store convergence parameters for debugging
            metrics["cmr_coverage_params"] = {
                "radius_deg": cmr_radius,
                "samples": cmr_samples,
            }
            metrics["generated_coverage_params"] = {
                "radius_deg": gen_radius,
                "samples": gen_samples,
            }

        return metrics


# Utility functions
def sanitize_granule_ur(granule_ur):
    """
    Sanitize granule UR for filesystem use.

    Parameters:
    -----------
    granule_ur : str
        Granule UR from CMR

    Returns:
    --------
    str : Sanitized filename
    """
    # Replace problematic characters including spaces
    safe_name = re.sub(r'[<>:"/\\|?*\s]', "_", granule_ur)
    # Remove multiple underscores
    safe_name = re.sub(r"_+", "_", safe_name)
    # Limit length
    if len(safe_name) > 200:
        safe_name = safe_name[:200]
    return safe_name


def create_comparison_summary(granule_ur, metrics):
    """
    Create a summary of polygon comparison results.

    Parameters:
    -----------
    granule_ur : str
        Granule identifier
    metrics : dict
        Comparison metrics from PolygonComparator

    Returns:
    --------
    str : Formatted summary text
    """
    summary = f"""
Polygon Comparison Summary for {granule_ur}
{"=" * 60}

Area Comparison:
  CMR Area:       {metrics["cmr_area_deg2"]:.6f} deg²
  Generated Area: {metrics["generated_area_deg2"]:.6f} deg²
  Area Ratio:     {metrics["area_ratio"]:.3f}

Overlap Metrics:
  IoU (Intersection over Union): {metrics["iou"]:.3f}
  CMR covered by Generated:      {metrics["cmr_covered_by_generated"]:.1%}
  Generated covered by CMR:      {metrics["generated_covered_by_cmr"]:.1%}

Shape Metrics:
  CMR Vertices:       {metrics["cmr_vertices"]}
  Generated Vertices: {metrics["generated_vertices"]}
  Hausdorff Distance: {metrics["hausdorff_distance"]:.6f} deg
  Centroid Distance:  {metrics["centroid_distance"]:.6f} deg

Quality Assessment:
  {"✓" if metrics["iou"] >= 0.8 else "✗"} IoU >= 0.8
  {"✓" if 0.5 <= metrics["area_ratio"] <= 2.0 else "✗"} Area ratio between 0.5 and 2.0
  {"✓" if metrics["cmr_covered_by_generated"] >= 0.9 else "✗"} CMR coverage >= 90%
"""
    return summary
