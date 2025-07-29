#!/usr/bin/env python3
"""
Polygon Comparison Driver

This module automatically compares generated polygons with CMR polygons
for randomly selected granules from a collection.
"""

import json
from datetime import datetime
from pathlib import Path

import earthaccess
import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import Point

# Import from spatial package
from nsidc.metgen.spatial.polygon_generator import create_flightline_polygon

from .spatial_utils import PolygonComparator, UMMGParser, sanitize_granule_ur


class PolygonComparisonDriver:
    """Driver for automated polygon comparison with CMR."""

    def __init__(self, output_dir="polygon_comparisons"):
        """
        Initialize the driver.

        Parameters:
        -----------
        output_dir : str
            Directory for output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Authenticate with earthaccess
        try:
            auth = earthaccess.login(strategy="environment")
            if not auth:
                auth = earthaccess.login(strategy="netrc")
            if auth:
                print("[PolygonDriver] Earthdata login succeeded.")
            else:
                print("[PolygonDriver] Warning: Earthdata login failed.")
        except Exception as e:
            print(f"[PolygonDriver] Warning: Could not authenticate: {e}")

        print(
            "[PolygonDriver] Using optimized polygon generation (concave hull + smart buffering)"
        )

        # Create session for downloads
        self.session = earthaccess.get_requests_https_session()

    def process_collection(
        self,
        short_name,
        provider=None,
        n_granules=5,
        data_extensions=[".TXT", ".txt", ".h5", ".nc"],
    ):
        """
        Process random granules from a collection.

        Parameters:
        -----------
        short_name : str
            Collection short name
        provider : str, optional
            Data provider
        n_granules : int
            Number of random granules to process
        data_extensions : list
            Valid data file extensions
        """
        print(
            f"\n[PolygonDriver] Processing {n_granules} random granules from {short_name}"
        )
        print("=" * 80)

        # Create collection output directory
        collection_dir = self.output_dir / sanitize_granule_ur(short_name)
        collection_dir.mkdir(exist_ok=True)

        # Get random granules using earthaccess
        try:
            # Search for more granules than needed to randomly sample
            results = earthaccess.search_data(
                short_name=short_name,
                provider=provider,
                count=min(n_granules * 5, 200),  # Get more to randomly sample from
            )

            if len(results) > n_granules:
                import random

                random.seed(42)  # For reproducibility
                granules = random.sample(results, n_granules)
            else:
                granules = results

        except Exception as e:
            print(f"[PolygonDriver] Error querying CMR: {e}")
            import traceback

            traceback.print_exc()
            return

        if not granules:
            print(f"No granules found for collection {short_name}")
            return

        print(f"[PolygonDriver] Found {len(granules)} granules to process")

        # Process granules sequentially
        print("Processing granules...")
        results = self._process_granules_sequential(
            granules, collection_dir, data_extensions
        )

        # Create collection summary
        self.create_collection_summary(collection_dir, short_name, results)

        # Return success status
        return len(results) > 0

    def _process_granules_sequential(self, granules, collection_dir, data_extensions):
        """Process granules sequentially (original method)."""
        results = []
        for i, granule in enumerate(granules, 1):
            print(f"\n{'=' * 80}")
            print(f"[PolygonDriver] Granule {i}/{len(granules)}")
            result = self.process_granule(granule, collection_dir, data_extensions)
            if result:
                results.append(result)
        return results

    def process_specific_granule(
        self,
        short_name,
        granule_ur,
        provider=None,
        data_extensions=[".TXT", ".txt", ".h5", ".nc", ".csv", ".CSV"],
    ):
        """
        Process a specific granule by name.

        Parameters:
        -----------
        short_name : str
            Collection short name
        granule_ur : str
            Specific granule name/UR to process
        provider : str, optional
            Data provider
        data_extensions : list
            Valid data file extensions
        """
        print(f"\n[PolygonDriver] Processing specific granule: {granule_ur}")
        print("=" * 80)

        # Create collection output directory
        collection_dir = self.output_dir / sanitize_granule_ur(short_name)
        collection_dir.mkdir(exist_ok=True)

        # Query CMR for the specific granule using earthaccess
        try:
            print(f"Searching CMR for granule: {granule_ur}")

            # Search by producer granule ID
            results = earthaccess.search_data(
                short_name=short_name,
                producer_granule_id=granule_ur,
                provider=provider,
                count=10,
            )

            entries = results

            if not entries:
                print(
                    f"Error: Could not find granule with producerGranuleId '{granule_ur}' in collection {short_name}"
                )
                return

            if len(entries) > 1:
                print(
                    f"Warning: Found {len(entries)} granules matching producerGranuleId '{granule_ur}'"
                )

            target_granule = entries[0]
            # Get granule UR from earthaccess result
            found_ur = target_granule.get("meta", {}).get("native-id", "Unknown")
            print(f"Found granule: {found_ur}")

            # Process the granule
            result = self.process_granule(
                target_granule, collection_dir, data_extensions
            )

            if result:
                print("\nProcessing complete!")
                print(f"Results saved to: {collection_dir}")

                # Create single-granule summary
                self.create_collection_summary(collection_dir, short_name, [result])
                return True
            else:
                print("\nProcessing failed.")
                return False

        except Exception as e:
            print(f"[PolygonDriver] Error querying CMR: {e}")
            import traceback

            traceback.print_exc()
            return False

    def process_granule(self, granule_entry, output_dir, data_extensions):
        """
        Process a single granule.

        Parameters:
        -----------
        granule_entry : earthaccess.results.DataGranule or dict
            Earthaccess granule result or CMR granule entry
        output_dir : Path
            Output directory
        data_extensions : list
            Valid data file extensions

        Returns:
        --------
        dict or None : Processing results
        """
        # Handle both earthaccess results and legacy dict format
        if hasattr(granule_entry, "get"):
            # Earthaccess result
            granule_ur = granule_entry.get("meta", {}).get("native-id", "Unknown")
            concept_id = granule_entry.get("meta", {}).get("concept-id", "")
        else:
            # Legacy dict format
            granule_ur = granule_entry.get("title", "Unknown")
            concept_id = granule_entry.get("id", "")

        print(f"\n[PolygonDriver] Processing: {granule_ur}")

        # Create granule output directory
        granule_dir = output_dir / sanitize_granule_ur(granule_ur)
        granule_dir.mkdir(exist_ok=True)

        try:
            # Get UMM-G metadata
            if hasattr(granule_entry, "get") and "umm" in granule_entry:
                # Earthaccess result already has UMM-G
                umm_json = granule_entry.get("umm", {})
            else:
                # Legacy: need to fetch UMM-G separately
                print(f"[PolygonDriver] Fetching UMM-G for concept ID: {concept_id}")
                # Use earthaccess to get the granule by concept ID
                results = earthaccess.search_data(concept_id=concept_id, count=1)
                if results:
                    umm_json = results[0].get("umm", {})
                else:
                    print(f"[PolygonDriver] Failed to get UMM-G for {granule_ur}")
                    return None

            # Extract CMR polygon
            cmr_geojson = UMMGParser.extract_polygons(umm_json, granule_ur)

            if not cmr_geojson.get("features"):
                print(
                    f"[PolygonDriver] Warning: No polygon found in CMR for {granule_ur}"
                )
                return None

            # Save CMR polygon
            cmr_polygon_file = granule_dir / "cmr_polygon.geojson"
            with open(cmr_polygon_file, "w") as f:
                json.dump(cmr_geojson, f, indent=2)

            # Extract data URLs
            if hasattr(granule_entry, "data_links"):
                # Earthaccess result - use data_links method
                data_links = granule_entry.data_links(access="external")
                # Find matching extension
                data_url = None
                for link in data_links:
                    if any(
                        link.lower().endswith(ext.lower()) for ext in data_extensions
                    ):
                        data_url = link
                        break
            else:
                # Legacy - use UMMGParser
                data_urls = UMMGParser.extract_data_urls(umm_json)
                data_url = UMMGParser.find_data_file(data_urls, data_extensions)

            if not data_url:
                print(f"[PolygonDriver] Warning: No data file found for {granule_ur}")
                return None

            print(f"[PolygonDriver] Data URL: {data_url}")

            # Download and load data
            data_file = self.download_data_file(data_url, granule_dir)
            if not data_file:
                return None

            # Load data points
            print("\n[PolygonDriver] Stage 1: Load Data")
            print(f"  File: {data_file.name}")
            lon, lat = self.load_data_points(data_file)
            if lon is None or len(lon) == 0:
                print(f"[PolygonDriver] Error: Could not load data from {data_file}")
                return None

            print(f"  Points loaded: {len(lon)}")

            # Calculate CMR data coverage to compare against
            print("\n[PolygonDriver] Stage 2: Analyze CMR Polygon")
            cmr_coverage = self._calculate_cmr_data_coverage(cmr_geojson, lon, lat)
            print(f"  CMR data coverage: {cmr_coverage:.1%}")

            # Get CMR vertex count
            cmr_vertices = 0
            for feature in cmr_geojson.get("features", []):
                if feature.get("geometry", {}).get("type") == "Polygon":
                    coords = feature["geometry"]["coordinates"][0]
                    cmr_vertices += len(coords) - 1
            print(f"  CMR vertices: {cmr_vertices}")

            # Generate polygon using optimized approach
            polygon, metadata = create_flightline_polygon(lon, lat)

            # Store CMR coverage in metadata for display
            metadata["cmr_data_coverage"] = cmr_coverage

            # Save generated polygon
            print("\n[PolygonDriver] Stage 4: Save Results")
            generated_geojson = self.create_geojson(polygon, metadata, granule_ur)
            generated_polygon_file = granule_dir / "generated_polygon.geojson"
            with open(generated_polygon_file, "w") as f:
                json.dump(generated_geojson, f, indent=2)

            # Compare polygons with data coverage
            print("\n[PolygonDriver] Stage 5: Compare Polygons")
            metrics = PolygonComparator.compare(
                cmr_geojson, generated_geojson, data_points=np.column_stack((lon, lat))
            )

            # Save metrics
            metrics_file = granule_dir / "comparison_metrics.json"
            with open(metrics_file, "w") as f:
                json.dump(metrics, f, indent=2)

            # Create visualizations
            self.create_granule_summary(
                granule_dir,
                granule_ur,
                lon,
                lat,
                cmr_geojson,
                generated_geojson,
                metrics,
                metadata,
            )

            print("\n[PolygonDriver] Results:")
            print(
                f"  Generated data coverage: {metrics.get('generated_data_coverage', 0):.1%}"
            )
            print(f"  Generated vertices: {metrics['generated_vertices']}")
            print(f"  Area ratio (generated/CMR): {metrics.get('area_ratio', 0):.3f}")
            print(
                f"  Non-data area: {metrics.get('generated_non_data_coverage', 0):.1%}"
            )

            return {
                "granule_ur": granule_ur,
                "metrics": metrics,
                "metadata": metadata,
                "data_points": len(lon),
            }

        except Exception as e:
            print(f"  Error processing granule: {e}")
            import traceback

            traceback.print_exc()
            return None

    def download_data_file(self, url, output_dir):
        """
        Download data file from URL.

        Parameters:
        -----------
        url : str
            Data file URL
        output_dir : Path
            Output directory

        Returns:
        --------
        Path or None : Downloaded file path
        """
        filename = url.split("/")[-1]
        output_path = output_dir / filename

        if output_path.exists():
            print(f"[PolygonDriver] Using cached data file: {filename}")
            return output_path

        try:
            print(f"[PolygonDriver] Downloading: {filename}")

            # Use earthaccess session which handles authentication
            response = self.session.get(url, stream=True, allow_redirects=True)

            # Check if we ended up at an OAuth page
            if "urs.earthdata.nasa.gov" in response.url and "oauth" in response.url:
                print(
                    "  Authentication required. Please ensure Earthdata login succeeded."
                )
                print("[PolygonDriver] Creating dummy data file for demonstration...")
                self._create_dummy_data_file(output_path)
                return output_path

            response.raise_for_status()

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return output_path

        except Exception as e:
            print(f"[PolygonDriver] Error downloading file: {e}")
            if "401" in str(e) or "Unauthorized" in str(e):
                print("[PolygonDriver] Creating dummy data file for demonstration...")
                self._create_dummy_data_file(output_path)
                return output_path
            return None

    def _create_dummy_data_file(self, output_path):
        """Create a dummy LVIS data file for testing."""
        import numpy as np

        # Generate dummy LVIS-like data
        n_points = 5000
        center_lon = -118.35
        center_lat = 34.32

        # Create a flight path
        t = np.linspace(0, 2 * np.pi, n_points)
        lon = center_lon + 0.1 * np.sin(3 * t) + 0.02 * np.random.randn(n_points)
        lat = center_lat + 0.1 * t / (2 * np.pi) + 0.02 * np.random.randn(n_points)

        # Write as simple text file with LVIS-like column names
        with open(output_path, "w") as f:
            f.write("# Dummy LVIS data for demonstration\n")
            f.write("# LFID SHOTNUMBER TIME LON LAT Z_SURF\n")
            for i in range(n_points):
                f.write(
                    f"{i + 1} {i + 1000} {i * 0.001:.3f} {lon[i]:.6f} {lat[i]:.6f} {100 + 10 * np.random.randn():.2f}\n"
                )

    def _calculate_cmr_data_coverage(self, cmr_geojson, lon, lat):
        """Calculate what fraction of data points the CMR polygon covers."""
        if not cmr_geojson.get("features"):
            return 0.0

        # Get CMR polygon
        cmr_gdf = gpd.GeoDataFrame.from_features(cmr_geojson["features"])
        cmr_geom = cmr_gdf.union_all()

        # Sample points if too many
        if len(lon) > 10000:
            indices = np.random.choice(len(lon), 10000, replace=False)
            sample_lon = lon[indices]
            sample_lat = lat[indices]
        else:
            sample_lon = lon
            sample_lat = lat

        # Count points inside CMR polygon
        inside_count = 0
        for x, y in zip(sample_lon, sample_lat):
            if cmr_geom.contains(Point(x, y)):
                inside_count += 1

        return inside_count / len(sample_lon) if len(sample_lon) > 0 else 0.0

    def load_data_points(self, data_file):
        """
        Load data points from file.

        Parameters:
        -----------
        data_file : Path
            Data file path

        Returns:
        --------
        tuple : (lon, lat) arrays or (None, None)
        """
        try:
            print(
                f"    Attempting to load file with suffix: {data_file.suffix.lower()}"
            )
            if data_file.suffix.lower() in [".txt", ".csv"]:
                # Check if this is a simple CSV format (like IPFLR1B or IGBTH4)
                # Read first few lines to detect format, skipping comments
                with open(data_file, "r") as f:
                    first_lines = []
                    for _ in range(10):  # Read up to 10 lines to find header
                        line = f.readline()
                        if not line:
                            break
                        first_lines.append(line)

                # Find header line - should be the last comment line before data
                header_line = None
                header_idx = 0
                last_comment_idx = -1

                # Find the last comment line before the first data line
                for i, line in enumerate(first_lines):
                    if line.strip().startswith("#"):
                        # Check if this looks like a header (has column-like structure)
                        if (
                            any(delimiter in line for delimiter in [",", "\t"])
                            or len(line.split()) > 3
                        ):
                            last_comment_idx = i
                    elif line.strip() and not line.strip().startswith("#"):
                        # Found first data line, stop
                        break

                # The header should be the last comment line
                if last_comment_idx >= 0:
                    header_line = first_lines[last_comment_idx].strip("#").strip()
                    header_idx = last_comment_idx
                    print(
                        f"    Found header at line {header_idx + 1} (last comment before data)"
                    )
                else:
                    # No comment header, check for regular header
                    for i, line in enumerate(first_lines):
                        if not line.strip().startswith("#") and line.strip():
                            header_line = line
                            header_idx = i
                            break

                print(
                    f"    Header: {header_line.strip() if header_line else 'No header found'}"
                )

                # Check if header contains lon/lat columns (any case)
                has_lon_lat = False
                if header_line:
                    header_upper = header_line.upper()
                    if "LON" in header_upper or "LAT" in header_upper:
                        has_lon_lat = True

                if has_lon_lat:
                    # Determine delimiter by checking header line
                    has_comma = "," in header_line
                    has_tab = "\t" in header_line

                    # If header was in a comment, need to parse manually
                    if header_idx < len(first_lines) and first_lines[
                        header_idx
                    ].strip().startswith("#"):
                        print("    Header is in comment line, parsing manually")
                        # Parse the header to get column names
                        if has_comma:
                            # Split by comma and clean up
                            columns = [col.strip() for col in header_line.split(",")]
                        elif has_tab:
                            columns = [col.strip() for col in header_line.split("\t")]
                        else:
                            columns = header_line.split()

                        # Clean column names - remove trailing commas and whitespace
                        columns = [
                            col.strip().rstrip(",") for col in columns if col.strip()
                        ]
                        print(f"    Column names from header: {columns}")

                        # Read data using the same delimiter as the header
                        if has_comma:
                            # For comma-delimited, also handle potential spaces after commas
                            data = pd.read_csv(
                                data_file,
                                sep=",",
                                engine="python",
                                comment="#",
                                names=columns,
                                skiprows=header_idx + 1,
                                skipinitialspace=True,
                            )
                        elif has_tab:
                            data = pd.read_csv(
                                data_file,
                                sep="\t",
                                engine="python",
                                comment="#",
                                names=columns,
                                skiprows=header_idx + 1,
                            )
                        else:
                            data = pd.read_csv(
                                data_file,
                                sep=r"\s+",
                                engine="python",
                                comment="#",
                                names=columns,
                                skiprows=header_idx + 1,
                            )
                    else:
                        # Standard format with non-comment header
                        if has_comma:
                            print(f"    Reading comma-delimited format: {data_file}")
                            data = pd.read_csv(data_file, comment="#")
                        elif has_tab:
                            print(f"    Reading tab-delimited format: {data_file}")
                            data = pd.read_csv(
                                data_file, sep="\t", engine="python", comment="#"
                            )
                        else:
                            print(
                                f"    Reading whitespace-delimited format: {data_file}"
                            )
                            data = pd.read_csv(
                                data_file, sep=r"\s+", engine="python", comment="#"
                            )

                    print(f"    Loaded {len(data)} rows, columns: {list(data.columns)}")

                # Not a lon/lat format we recognize
                else:
                    # Skip this file - not a recognized format
                    print("    File does not match expected CSV formats")
                    # Fall through to LVIS format check
                    data = None

                # Process the loaded data if we have it
                if "data" in locals() and data is not None:
                    # Get lon/lat from standardized column names (case-insensitive)
                    lon_col = None
                    lat_col = None

                    for col in data.columns:
                        col_stripped = col.strip()
                        col_lower = col_stripped.lower()
                        if col_lower == "lon" or col_lower == "longitude":
                            lon_col = col
                        elif col_lower == "lat" or col_lower == "latitude":
                            lat_col = col

                    # Also check exact uppercase matches for IGBTH4 and LVIS formats
                    if not lon_col:
                        for col in data.columns:
                            col_stripped = col.strip()
                            if col_stripped in ["LON", "HLON", "GLON", "TLON"]:
                                lon_col = col
                                break
                    if not lat_col:
                        for col in data.columns:
                            col_stripped = col.strip()
                            if col_stripped in ["LAT", "HLAT", "GLAT", "TLAT"]:
                                lat_col = col
                                break

                    if lon_col and lat_col:
                        print(f"    Using columns: {lon_col} (lon), {lat_col} (lat)")

                        # Convert to numeric, handling any non-numeric values
                        try:
                            lon = pd.to_numeric(data[lon_col], errors="coerce").values
                            lat = pd.to_numeric(data[lat_col], errors="coerce").values
                        except Exception:
                            lon = data[lon_col].values
                            lat = data[lat_col].values

                        # Convert from 0-360 to -180-180 if needed
                        lon = np.where(lon > 180, lon - 360, lon)

                        # Filter valid coordinates (including LVIS-style missing values)
                        mask = (
                            np.isfinite(lon)
                            & np.isfinite(lat)
                            & (lon != 0)
                            & (lat != 0)
                            & (lon != -999)
                            & (lat != -999)
                        )

                        valid_count = mask.sum()
                        print(
                            f"    Found {valid_count} valid coordinates out of {len(lon)}"
                        )

                        if valid_count > 0:
                            return lon[mask], lat[mask]
                        else:
                            print("    No valid coordinates found after filtering")
                            return None, None
                    else:
                        print(
                            f"    Could not find lon/lat columns. Available: {list(data.columns)}"
                        )
                        print(
                            f"    Column details: {[(col, type(col)) for col in data.columns]}"
                        )
                        return None, None

                # Otherwise, treat as LVIS text format
                print(f"    Reading LVIS text file: {data_file}")

                # First, find the header line in comments
                header_line = None
                with open(data_file, "r") as f:
                    for line in f:
                        if line.startswith("#") and any(
                            col in line
                            for col in ["HLON", "LON_LOW", "GLON", "LON", "LFID"]
                        ):
                            # This is likely the header line
                            header_line = line.strip("#").strip()
                            break

                if header_line:
                    # Parse header to get column names
                    columns = header_line.split()

                    # Now read the data, skipping comment lines
                    data = pd.read_csv(
                        data_file,
                        sep=r"\s+",
                        comment="#",
                        names=columns,
                        engine="python",
                    )
                else:
                    # Fallback: try to read without header
                    data = pd.read_csv(
                        data_file, sep=r"\s+", comment="#", engine="python"
                    )

                print(
                    f"    Loaded {len(data)} rows, columns: {list(data.columns)[:10]}"
                )

                # Find longitude and latitude columns using original logic
                # Convert column names to uppercase for case-insensitive matching
                columns_upper = {col.upper(): col for col in data.columns}

                # Find longitude column - check in order of preference
                lon_col = None
                for possible_lon in ["HLON", "LON_LOW", "GLON", "LON", "LONGITUDE"]:
                    if possible_lon in columns_upper:
                        lon_col = columns_upper[possible_lon]
                        break

                # Find latitude column - check in order of preference
                lat_col = None
                for possible_lat in ["HLAT", "LAT_LOW", "GLAT", "LAT", "LATITUDE"]:
                    if possible_lat in columns_upper:
                        lat_col = columns_upper[possible_lat]
                        break

                if lon_col and lat_col:
                    print(f"    Using columns: {lon_col} (lon), {lat_col} (lat)")
                    lon = data[lon_col].values
                    lat = data[lat_col].values

                    # Convert from 0-360 to -180-180 if needed
                    lon = np.where(lon > 180, lon - 360, lon)

                    # Filter valid coordinates
                    mask = (
                        np.isfinite(lon)
                        & np.isfinite(lat)
                        & (lon != 0)
                        & (lat != 0)
                        & (lon != -999)
                        & (lat != -999)
                    )  # LVIS uses -999 for missing

                    return lon[mask], lat[mask]
                else:
                    print(
                        f"    Could not find lon/lat columns. Available: {list(data.columns)}"
                    )
                    return None, None

            elif data_file.suffix.lower() in [".h5", ".hdf5", ".nc"]:
                # NetCDF/HDF5 format
                import xarray as xr

                ds = xr.open_dataset(data_file)

                # Find lat/lon variables
                lon = None
                lat = None

                for var in ds.variables:
                    if "lon" in var.lower():
                        lon = ds[var].values.flatten()
                    elif "lat" in var.lower():
                        lat = ds[var].values.flatten()

                if lon is not None and lat is not None:
                    mask = np.isfinite(lon) & np.isfinite(lat) & (lon != 0) & (lat != 0)
                    return lon[mask], lat[mask]

        except Exception as e:
            print(f"  Error loading data: {e}")
            import traceback

            traceback.print_exc()

        return None, None

    def create_geojson(self, polygon, metadata, granule_ur):
        """
        Create GeoJSON from polygon.

        Parameters:
        -----------
        polygon : shapely.geometry.Polygon
            Generated polygon
        metadata : dict
            Generation metadata
        granule_ur : str
            Granule identifier

        Returns:
        --------
        dict : GeoJSON FeatureCollection
        """
        if polygon is None:
            return {"type": "FeatureCollection", "features": []}

        feature = {
            "type": "Feature",
            "geometry": polygon.__geo_interface__,
            "properties": {
                "source": "Generated",
                "granule_ur": granule_ur,
                "method": metadata.get("method", "unknown"),
                "vertices": metadata.get("vertices", 0),
                "data_points": metadata.get("points", 0),
                "adaptive_buffer": metadata.get("adaptive_buffer", None),
            },
        }

        return {"type": "FeatureCollection", "features": [feature]}

    def create_granule_summary(
        self,
        output_dir,
        granule_ur,
        lon,
        lat,
        cmr_geojson,
        generated_geojson,
        metrics,
        metadata,
    ):
        """
        Create visual summary for a granule.

        Parameters:
        -----------
        output_dir : Path
            Output directory
        granule_ur : str
            Granule identifier
        lon, lat : arrays
            Data coordinates
        cmr_geojson : dict
            CMR polygon GeoJSON
        generated_geojson : dict
            Generated polygon GeoJSON
        metrics : dict
            Comparison metrics
        metadata : dict
            Generation metadata
        """
        # Create figure with subplots
        fig = plt.figure(figsize=(16, 10))

        # Title
        fig.suptitle(
            f"Polygon Comparison: {granule_ur}", fontsize=16, fontweight="bold"
        )

        # Calculate bounds for consistent framing
        all_lons = list(lon)
        all_lats = list(lat)

        # Add polygon coordinates
        for feature in cmr_geojson["features"]:
            coords = feature["geometry"]["coordinates"][0]
            all_lons.extend([c[0] for c in coords])
            all_lats.extend([c[1] for c in coords])

        for feature in generated_geojson["features"]:
            coords = feature["geometry"]["coordinates"][0]
            all_lons.extend([c[0] for c in coords])
            all_lats.extend([c[1] for c in coords])

        # Calculate bounds with padding
        lon_min, lon_max = min(all_lons), max(all_lons)
        lat_min, lat_max = min(all_lats), max(all_lats)

        lon_range = lon_max - lon_min
        lat_range = lat_max - lat_min
        padding = 0.1

        bounds = [
            lon_min - lon_range * padding,
            lon_max + lon_range * padding,
            lat_min - lat_range * padding,
            lat_max + lat_range * padding,
        ]

        # 1. Data points plot
        ax1 = plt.subplot(2, 3, 1)

        # Subsample points for visualization
        if len(lon) > 10000:
            indices = np.random.choice(len(lon), 10000, replace=False)
            plot_lon = lon[indices]
            plot_lat = lat[indices]
        else:
            plot_lon = lon
            plot_lat = lat

        ax1.scatter(plot_lon, plot_lat, c="blue", s=1, alpha=0.5)
        ax1.set_xlim(bounds[0], bounds[1])
        ax1.set_ylim(bounds[2], bounds[3])
        ax1.set_aspect("equal")
        ax1.set_title(f"Data Points (n={len(lon):,})", fontweight="bold")
        ax1.set_xlabel("Longitude")
        ax1.set_ylabel("Latitude")
        ax1.grid(True, alpha=0.3)

        # 2. CMR polygon plot
        ax2 = plt.subplot(2, 3, 2)

        # Plot CMR polygon
        for feature in cmr_geojson["features"]:
            coords = feature["geometry"]["coordinates"][0]
            x = [c[0] for c in coords]
            y = [c[1] for c in coords]
            ax2.plot(x, y, "r-", linewidth=2, label="CMR Polygon")
            ax2.fill(x, y, "red", alpha=0.2)

        # Add data points for reference
        ax2.scatter(plot_lon, plot_lat, c="blue", s=1, alpha=0.2)

        ax2.set_xlim(bounds[0], bounds[1])
        ax2.set_ylim(bounds[2], bounds[3])
        ax2.set_aspect("equal")
        ax2.set_title(
            f"CMR Polygon ({metrics['cmr_vertices']} vertices)", fontweight="bold"
        )
        ax2.set_xlabel("Longitude")
        ax2.set_ylabel("Latitude")
        ax2.grid(True, alpha=0.3)

        # 3. Generated polygon plot
        ax3 = plt.subplot(2, 3, 3)

        # Plot generated polygon
        for feature in generated_geojson["features"]:
            coords = feature["geometry"]["coordinates"][0]
            x = [c[0] for c in coords]
            y = [c[1] for c in coords]
            ax3.plot(x, y, "g-", linewidth=2, label="Generated Polygon")
            ax3.fill(x, y, "green", alpha=0.2)

        # Add data points for reference
        ax3.scatter(plot_lon, plot_lat, c="blue", s=1, alpha=0.2)

        ax3.set_xlim(bounds[0], bounds[1])
        ax3.set_ylim(bounds[2], bounds[3])
        ax3.set_aspect("equal")
        ax3.set_title(
            f"Generated Polygon ({metrics['generated_vertices']} vertices)",
            fontweight="bold",
        )
        ax3.set_xlabel("Longitude")
        ax3.set_ylabel("Latitude")
        ax3.grid(True, alpha=0.3)

        # 4. Overlay comparison
        ax4 = plt.subplot(2, 3, 4)

        # Plot both polygons
        for feature in cmr_geojson["features"]:
            coords = feature["geometry"]["coordinates"][0]
            x = [c[0] for c in coords]
            y = [c[1] for c in coords]
            ax4.plot(x, y, "r-", linewidth=2, label="CMR")
            ax4.fill(x, y, "red", alpha=0.2)

        for feature in generated_geojson["features"]:
            coords = feature["geometry"]["coordinates"][0]
            x = [c[0] for c in coords]
            y = [c[1] for c in coords]
            ax4.plot(x, y, "g-", linewidth=2, label="Generated")
            ax4.fill(x, y, "green", alpha=0.2)

        ax4.set_xlim(bounds[0], bounds[1])
        ax4.set_ylim(bounds[2], bounds[3])
        ax4.set_aspect("equal")
        ax4.set_title("Polygon Comparison", fontweight="bold")
        ax4.set_xlabel("Longitude")
        ax4.set_ylabel("Latitude")
        ax4.grid(True, alpha=0.3)
        ax4.legend()

        # 5 & 6. Combined metrics and generation info spanning two columns
        ax_combined = plt.subplot2grid((2, 3), (1, 1), colspan=2)
        ax_combined.axis("off")

        # Create two-column layout for metrics
        # Left column - Polygon Statistics (3-column comparison)
        left_table_data = [
            ["Metric", "CMR Polygon", "New Polygon"],
            [
                "Area",
                f"{metrics['cmr_area']:.6f}°²",
                f"{metrics['generated_area']:.6f}°²",
            ],
            [
                "Vertices",
                f"{metrics['cmr_vertices']}",
                f"{metrics['generated_vertices']}",
            ],
            [
                "Data Coverage",
                f"{metrics.get('cmr_data_coverage', 0):.1%}",
                f"{metrics.get('generated_data_coverage', 0):.1%}",
            ],
        ]

        # Add non-data coverage if available
        if "cmr_non_data_coverage" in metrics:
            left_table_data.append(
                [
                    "Non-data Coverage",
                    f"{metrics.get('cmr_non_data_coverage', 0):.1%}",
                    f"{metrics.get('generated_non_data_coverage', 0):.1%}",
                ]
            )

        # Right column - Optimization Goals
        right_table_data = [
            ["Goal", "Status"],
            ["Primary Goals", ""],
            [
                "100% Data Coverage",
                "✓"
                if metrics.get("generated_data_coverage", 0) >= 1.0
                else f"✗ ({metrics.get('generated_data_coverage', 0):.1%})",
            ],
            [
                "Vertices ≤ CMR",
                "✓"
                if metrics["generated_vertices"] <= metrics["cmr_vertices"]
                else f"✗ ({metrics['generated_vertices']} > {metrics['cmr_vertices']})",
            ],
            [
                "Area ≤ CMR",
                "✓"
                if metrics["area_ratio"] <= 1.0
                else f"✗ ({metrics['area_ratio']:.2f}x)",
            ],
            ["", ""],
            ["Generation Info", ""],
            ["Method", metadata.get("method", "unknown")],
            [
                "Adaptive Buffer",
                f"{metadata.get('adaptive_buffer', 'N/A'):.1f} m"
                if isinstance(metadata.get("adaptive_buffer"), (int, float))
                else "N/A",
            ],
            [
                "Generation Time",
                f"{metadata.get('generation_time_seconds', 0):.3f} s",
            ],
        ]

        # Create left table
        left_table = ax_combined.table(
            cellText=left_table_data,
            cellLoc="left",
            loc="center",
            bbox=[0.0, 0.0, 0.48, 1.0],
            colWidths=[0.4, 0.3, 0.3],
        )
        left_table.auto_set_font_size(False)
        left_table.set_fontsize(9)

        # Create right table
        right_table = ax_combined.table(
            cellText=right_table_data,
            cellLoc="left",
            loc="center",
            bbox=[0.52, 0.0, 0.48, 1.0],
            colWidths=[0.65, 0.35],
        )
        right_table.auto_set_font_size(False)
        right_table.set_fontsize(9)

        # Style both tables
        for table_idx, table in enumerate([left_table, right_table]):
            # Header row - handle different column counts
            if table_idx == 0:  # Left table has 3 columns
                for i in range(3):
                    table[(0, i)].set_facecolor("#4472C4")
                    table[(0, i)].set_text_props(weight="bold", color="white")
            else:  # Right table has 2 columns
                for i in range(2):
                    table[(0, i)].set_facecolor("#4472C4")
                    table[(0, i)].set_text_props(weight="bold", color="white")

            # Color code specific cells
            for (row_idx, col_idx), cell in table.get_celld().items():
                cell_text = cell.get_text().get_text()

                # Section headers (excluding Data Coverage which is now a regular row)
                if cell_text in ["Primary Goals", "Generation Info"]:
                    cell.set_text_props(weight="bold")
                    cell.set_facecolor("#D9E2F3")
                    # For section headers, color all cells in the row
                    if col_idx == 0:
                        # Color remaining cells in the same row
                        if (row_idx, 1) in table.get_celld():
                            table[(row_idx, 1)].set_facecolor("#D9E2F3")
                        if (row_idx, 2) in table.get_celld():
                            table[(row_idx, 2)].set_facecolor("#D9E2F3")

                # Color code quality metrics
                if col_idx == 1:  # Value column
                    if cell_text == "✓":
                        cell.set_facecolor("lightgreen")
                    elif cell_text == "✗":
                        cell.set_facecolor("lightcoral")

        # Color code specific metric values in left table
        for row_idx in range(len(left_table_data)):
            cell_key = left_table_data[row_idx][0]
            if (
                cell_key == "Data Coverage"
                and metrics.get("generated_data_coverage", 0) >= 0.9
            ):
                left_table[(row_idx, 1)].set_facecolor("lightgreen")
            elif (
                cell_key == "Data Coverage"
                and metrics.get("generated_data_coverage", 0) < 0.9
            ):
                left_table[(row_idx, 1)].set_facecolor("lightcoral")
            elif cell_key == "Area Ratio" and 0.5 <= metrics["area_ratio"] <= 2.0:
                left_table[(row_idx, 1)].set_facecolor("lightgreen")
            elif cell_key == "Area Ratio" and (
                metrics["area_ratio"] < 0.5 or metrics["area_ratio"] > 2.0
            ):
                left_table[(row_idx, 1)].set_facecolor("lightcoral")
            elif (
                cell_key == "CMR Coverage"
                and metrics["cmr_coverage_by_generated"] >= 0.9
            ):
                left_table[(row_idx, 1)].set_facecolor("lightgreen")
            elif (
                cell_key == "CMR Coverage"
                and metrics["cmr_coverage_by_generated"] < 0.9
            ):
                left_table[(row_idx, 1)].set_facecolor("lightcoral")
            elif cell_key == "Coverage Ratio" and "data_coverage_ratio" in metrics:
                if metrics["data_coverage_ratio"] >= 1.0:
                    left_table[(row_idx, 1)].set_facecolor("lightgreen")
                else:
                    left_table[(row_idx, 1)].set_facecolor("lightcoral")

        ax_combined.set_title(
            "Metrics & Generation Summary", fontweight="bold", fontsize=14, pad=20
        )

        # Adjust layout and save
        plt.tight_layout()

        # Save figure
        summary_file = output_dir / "summary.png"
        plt.savefig(summary_file, dpi=150, bbox_inches="tight")
        plt.close()

        print(f"  Summary saved to: {summary_file}")

    def create_collection_summary(self, output_dir, short_name, results):
        """
        Create summary report for entire collection.

        Parameters:
        -----------
        output_dir : Path
            Output directory
        short_name : str
            Collection short name
        results : list
            Processing results for all granules
        """
        if not results:
            print("\nNo results to summarize")
            return

        # Calculate aggregate statistics
        data_coverages = [
            r["metrics"].get("generated_data_coverage", 0) for r in results
        ]
        area_ratios = [r["metrics"]["area_ratio"] for r in results]
        cmr_coverages = [r["metrics"]["cmr_coverage_by_generated"] for r in results]
        vertex_counts = [r["metrics"]["generated_vertices"] for r in results]
        generation_times = [
            r["metadata"].get("generation_time_seconds", 0) for r in results
        ]

        # Create summary report
        summary_text = f"""# Polygon Comparison Summary for {short_name}

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Processing Summary
- Total granules processed: {len(results)}
- Generator type: standard
- Processing method: Optimized algorithms (concave hull + smart buffering)
- Iterative simplification: N/A (handled by standard algorithms)
- Target vertices: Auto-selected by algorithm

## Aggregate Metrics

### Data Coverage (Generated Polygon)
- Mean: {np.mean(data_coverages):.1%}
- Median: {np.median(data_coverages):.1%}
- Min: {np.min(data_coverages):.1%}
- Max: {np.max(data_coverages):.1%}
- Std Dev: {np.std(data_coverages):.3f}

### Area Ratio (Generated/CMR)
- Mean: {np.mean(area_ratios):.3f}
- Median: {np.median(area_ratios):.3f}
- Min: {np.min(area_ratios):.3f}
- Max: {np.max(area_ratios):.3f}

### CMR Coverage by Generated
- Mean: {np.mean(cmr_coverages):.1%}
- Median: {np.median(cmr_coverages):.1%}
- Min: {np.min(cmr_coverages):.1%}
- Max: {np.max(cmr_coverages):.1%}

### Vertex Count
- Mean: {np.mean(vertex_counts):.1f}
- Median: {np.median(vertex_counts):.0f}
- Min: {np.min(vertex_counts)}
- Max: {np.max(vertex_counts)}

### Generation Time (seconds)
- Mean: {np.mean(generation_times):.3f}
- Median: {np.median(generation_times):.3f}
- Min: {np.min(generation_times):.3f}
- Max: {np.max(generation_times):.3f}
- Total: {np.sum(generation_times):.1f}

## Quality Assessment
- Granules with data coverage >= 90%: {sum(1 for dc in data_coverages if dc >= 0.9)}/{len(data_coverages)} ({100 * sum(1 for dc in data_coverages if dc >= 0.9) / len(data_coverages):.0f}%)
- Granules with area ratio in [0.5, 2.0]: {sum(1 for ar in area_ratios if 0.5 <= ar <= 2.0)}/{len(area_ratios)} ({100 * sum(1 for ar in area_ratios if 0.5 <= ar <= 2.0) / len(area_ratios):.0f}%)
- Granules with CMR coverage >= 90%: {sum(1 for cc in cmr_coverages if cc >= 0.9)}/{len(cmr_coverages)} ({100 * sum(1 for cc in cmr_coverages if cc >= 0.9) / len(cmr_coverages):.0f}%)
- Granules with Great vertices (≤16): {sum(1 for vc in vertex_counts if vc <= 16)}/{len(vertex_counts)} ({100 * sum(1 for vc in vertex_counts if vc <= 16) / len(vertex_counts):.0f}%)
- Granules with Good vertices (≤32): {sum(1 for vc in vertex_counts if vc <= 32)}/{len(vertex_counts)} ({100 * sum(1 for vc in vertex_counts if vc <= 32) / len(vertex_counts):.0f}%)

## Individual Granule Results

| Granule | Data Coverage | Area Ratio | CMR Coverage | Vertices | Data Points | Gen Time (s) |
|---------|---------------|------------|--------------|----------|-------------|--------------|
"""

        for r in results:
            data_cov = r["metrics"].get("generated_data_coverage", 0)
            gen_time = r["metadata"].get("generation_time_seconds", 0)
            summary_text += f"| {r['granule_ur'][:50]}... | {data_cov:.1%} | {r['metrics']['area_ratio']:.3f} | {r['metrics']['cmr_coverage_by_generated']:.1%} | {r['metrics']['generated_vertices']} | {r['data_points']:,} | {gen_time:.3f} |\n"

        # Save summary
        summary_file = output_dir / "collection_summary.md"
        with open(summary_file, "w") as f:
            f.write(summary_text)

        print(f"\n[PolygonDriver] Collection summary saved to: {summary_file}")

        # Create visualization of aggregate metrics
        self.create_metrics_visualization(output_dir, results)

    def create_metrics_visualization(self, output_dir, results):
        """
        Create visualization of aggregate metrics.

        Parameters:
        -----------
        output_dir : Path
            Output directory
        results : list
            Processing results
        """
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))

        # Data coverage distribution
        ax = axes[0, 0]
        data_coverages = [
            r["metrics"].get("generated_data_coverage", 0) for r in results
        ]
        ax.hist(data_coverages, bins=20, color="skyblue", edgecolor="black", alpha=0.7)
        ax.axvline(0.9, color="red", linestyle="--", label="Target (90%)")
        ax.axvline(1.0, color="green", linestyle="--", label="Perfect (100%)")
        ax.set_xlabel("Data Coverage")
        ax.set_ylabel("Count")
        ax.set_title("Data Coverage Distribution")
        ax.legend()
        ax.grid(True, alpha=0.3)
        # Format x-axis as percentages
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x:.0%}"))

        # Area ratio distribution
        ax = axes[0, 1]
        area_ratios = [r["metrics"]["area_ratio"] for r in results]
        ax.hist(area_ratios, bins=20, color="lightgreen", edgecolor="black", alpha=0.7)
        ax.axvline(1.0, color="red", linestyle="--", label="Perfect (1.0)")
        ax.set_xlabel("Area Ratio (Generated/CMR)")
        ax.set_ylabel("Count")
        ax.set_title("Area Ratio Distribution")
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Vertex count distribution
        ax = axes[1, 0]
        vertices = [r["metrics"]["generated_vertices"] for r in results]
        cmr_vertices = [r["metrics"]["cmr_vertices"] for r in results]

        bins = range(0, max(max(vertices), max(cmr_vertices)) + 5, 2)
        ax.hist(vertices, bins=bins, alpha=0.5, label="Generated", color="green")
        ax.hist(cmr_vertices, bins=bins, alpha=0.5, label="CMR", color="red")
        ax.set_xlabel("Vertex Count")
        ax.set_ylabel("Count")
        ax.set_title("Vertex Count Distribution")
        ax.legend()
        ax.grid(True, alpha=0.3)

        # Add vertex quality zones
        ax.axvline(16, color="darkgreen", linestyle=":", alpha=0.7, label="Great (≤16)")
        ax.axvline(32, color="orange", linestyle=":", alpha=0.7, label="Good (≤32)")
        ax.axvline(127, color="red", linestyle=":", alpha=0.7, label="OK (≤127)")
        ax.legend()

        # Scatter plot: Data Coverage vs Vertices (colored by generation time)
        ax = axes[1, 1]
        generation_times = [
            r["metadata"].get("generation_time_seconds", 0) for r in results
        ]

        # Create scatter plot with color mapping for generation time
        scatter = ax.scatter(
            vertices,
            data_coverages,
            c=generation_times,
            cmap="viridis",
            alpha=0.7,
            s=100,
            edgecolors="black",
            linewidth=0.5,
        )

        # Add colorbar for timing
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label("Generation Time (seconds)", rotation=270, labelpad=15)

        ax.set_xlabel("Generated Vertices")
        ax.set_ylabel("Data Coverage")
        ax.set_title("Coverage vs Complexity vs Speed")
        ax.grid(True, alpha=0.3)
        # Format y-axis as percentages
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f"{x:.0%}"))

        # Add target lines
        ax.axhline(0.9, color="red", linestyle="--", alpha=0.7, label="90% Target")
        ax.axhline(1.0, color="white", linestyle="--", alpha=0.9, label="100% Perfect")
        ax.axvline(16, color="white", linestyle=":", alpha=0.7, label="Great (≤16)")
        ax.axvline(32, color="white", linestyle=":", alpha=0.7, label="Good (≤32)")
        ax.legend(fontsize=7, loc="lower right")

        # Add trend line for coverage vs vertices
        if len(vertices) > 1 and len(data_coverages) > 1:
            z = np.polyfit(vertices, data_coverages, 1)
            p = np.poly1d(z)
            ax.plot(sorted(vertices), p(sorted(vertices)), "r--", alpha=0.8)

        plt.suptitle("Aggregate Metrics Analysis", fontsize=16, fontweight="bold")
        plt.tight_layout()

        metrics_file = output_dir / "metrics_analysis.png"
        plt.savefig(metrics_file, dpi=150, bbox_inches="tight")
        plt.close()

        print(f"[PolygonDriver] Metrics visualization saved to: {metrics_file}")
