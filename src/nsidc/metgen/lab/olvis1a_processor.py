"""
OLVIS1A Granule Processor

This script downloads OLVIS1A granules and generates premet and spatial files.
"""

from datetime import datetime
from pathlib import Path

import earthaccess
import numpy as np


class OLVIS1AProcessor:
    """Process OLVIS1A granules to generate premet and spatial files."""

    # Constants
    CMR_URL = "https://cmr.earthdata.nasa.gov"
    COLLECTION = "OLVIS1A"
    VERSION = "1"
    PROVIDER = "NSIDC_ECS"

    def __init__(self, output_dir="olvis1a_output"):
        """
        Initialize the processor.

        Parameters:
        -----------
        output_dir : str
            Base output directory
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        print(
            f"OLVIS1A Processor: {self.COLLECTION} v{self.VERSION} from {self.PROVIDER}"
        )

        # Authenticate with earthaccess
        try:
            # Try environment authentication first, then netrc
            auth = earthaccess.login(strategy="environment")
            if not auth:
                auth = earthaccess.login(strategy="netrc")

            if auth:
                print("Earthdata login succeeded.")
            else:
                print("Warning: Earthdata login failed.")
                print("Set EARTHDATA_USERNAME/PASSWORD or configure .netrc")
        except Exception as e:
            print(f"Warning: Could not authenticate with Earthdata: {e}")

        # Create session for downloads using earthaccess session
        self.session = earthaccess.get_requests_https_session()

    def get_sequential_granules(self, count=10):
        """
        Get granules sequentially from CMR.

        Parameters:
        -----------
        count : int
            Number of granules to retrieve

        Returns:
        --------
        list : List of granule results
        """
        try:
            print(f"Querying CMR for {count} granules...")

            # Use earthaccess to search for granules
            results = earthaccess.search_data(
                short_name=self.COLLECTION,
                version=self.VERSION,
                provider=self.PROVIDER,
                count=count,
                sort_key="-start_date",  # Most recent first
            )

            print(f"Found {len(results)} granules")
            return results

        except Exception as e:
            print(f"Error querying CMR: {e}")
            return []

    def process_granules(self, n_granules=5):
        """
        Download and process n OLVIS1A granules.

        Parameters:
        -----------
        n_granules : int
            Number of granules to process
        """
        print(f"Processing {n_granules} {self.COLLECTION} granules")
        print("=" * 80)

        # Get granules sequentially
        granules = self.get_sequential_granules(n_granules)

        if not granules:
            print(f"No granules found for {self.COLLECTION}")
            return

        print(f"Retrieved {len(granules)} granules to process\n")

        # Process each granule
        for i, granule in enumerate(granules, 1):
            print(f"\nProcessing granule {i}/{len(granules)}")
            print("-" * 60)
            self.process_single_granule(granule)

    def process_single_granule(self, granule_result):
        """
        Process a single granule.

        Parameters:
        -----------
        granule_result : earthaccess.results.DataGranule
            Earthaccess granule result
        """
        # Extract granule info from earthaccess result
        granule_ur = granule_result.get("meta", {}).get("native-id", "Unknown")

        print(f"Granule: {granule_ur}")

        try:
            # Get UMM-G metadata using earthaccess result
            print("  Getting UMM-G metadata...")
            umm_json = granule_result.get("umm", {})

            # Get data links directly from earthaccess result
            data_links = granule_result.data_links(access="external")

            # Filter for image files
            image_extensions = [".JPG", ".jpg", ".jpeg", ".JPEG"]
            data_url = None
            for link in data_links:
                if any(link.lower().endswith(ext.lower()) for ext in image_extensions):
                    data_url = link
                    break

            if not data_url:
                print(f"  Warning: No JPG image file found for {granule_ur}")
                return

            print(f"  Data URL: {data_url}")

            # Create data directory
            data_dir = self.output_dir / "data"
            data_dir.mkdir(exist_ok=True)

            # Download data file
            data_file = self.download_data_file(data_url, data_dir)
            if not data_file:
                return

            # Get coordinates from UMM-G metadata
            lon, lat = self.extract_coordinates_from_ummg(umm_json)

            if lon is None or len(lon) == 0:
                print("  Error: Could not extract coordinates from metadata")
                return

            print(f"  Generated {len(lon)} coordinate points")

            # Generate premet file
            self.generate_premet_file(data_file, umm_json)

            # Generate spatial file
            self.generate_spatial_file(data_file, lon, lat)

            print(f"  ✓ Successfully processed {granule_ur}")

        except Exception as e:
            print(f"  Error processing granule: {e}")

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
            print(f"  Using cached file: {filename}")
            return output_path

        try:
            print(f"  Downloading: {filename}")

            # Download with redirects using the existing session
            response = self.session.get(url, stream=True, allow_redirects=True)

            # Check if we ended up at an OAuth page
            if "urs.earthdata.nasa.gov" in response.url and "oauth" in response.url:
                print(
                    "  Authentication required. Please set EARTHDATA_USERNAME and EARTHDATA_PASSWORD."
                )
                return None

            response.raise_for_status()

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            print(f"  Downloaded {output_path.stat().st_size / 1024:.1f} KB")
            return output_path

        except Exception as e:
            print(f"  Error downloading file: {e}")
            if "401" in str(e) or "Unauthorized" in str(e):
                print(
                    "  Authentication failed. Check EARTHDATA_USERNAME and EARTHDATA_PASSWORD."
                )
            elif "403" in str(e) or "Forbidden" in str(e):
                print("  Access forbidden. Check data access permissions.")
            return None

    def extract_coordinates_from_ummg(self, umm_json):
        """
        Extract coordinates from UMM-G metadata.

        Parameters:
        -----------
        umm_json : dict
            UMM-G metadata

        Returns:
        --------
        tuple : (lon_array, lat_array) or (None, None)
        """
        try:
            # Handle both direct UMM-G and wrapped format
            if "umm" in umm_json:
                umm_json = umm_json["umm"]

            spatial_extent = umm_json.get("SpatialExtent", {})
            horizontal_extent = spatial_extent.get("HorizontalSpatialDomain", {})
            geometry = horizontal_extent.get("Geometry", {})

            # Try GPolygons first
            gpolygons = geometry.get("GPolygons", [])
            if gpolygons:
                # Use first polygon
                boundary = gpolygons[0].get("Boundary", {})
                points = boundary.get("Points", [])

                if len(points) >= 3:
                    # Extract coordinates from polygon
                    lons = [p["Longitude"] for p in points]
                    lats = [p["Latitude"] for p in points]

                    print(f"    Found polygon with {len(points)} vertices")
                    return np.array(lons), np.array(lats)

            # Try BoundingRectangles
            bounding_rects = geometry.get("BoundingRectangles", [])
            if bounding_rects:
                rect = bounding_rects[0]
                west = rect.get("WestBoundingCoordinate")
                east = rect.get("EastBoundingCoordinate")
                north = rect.get("NorthBoundingCoordinate")
                south = rect.get("SouthBoundingCoordinate")

                if all(v is not None for v in [west, east, north, south]):
                    print(
                        f"    Found bounding box: [{west:.4f}, {south:.4f}] to [{east:.4f}, {north:.4f}]"
                    )

                    # Create corner points of the bounding rectangle
                    lons = [west, east, east, west, west]  # Close the polygon
                    lats = [south, south, north, north, south]

                    return np.array(lons), np.array(lats)

            # Try Points
            points = geometry.get("Points", [])
            if points:
                lons = [p["Longitude"] for p in points]
                lats = [p["Latitude"] for p in points]

                if lons and lats:
                    print(f"    Found {len(points)} individual points")
                    return np.array(lons), np.array(lats)

            print("    No spatial geometry found in UMM-G metadata")
            return None, None

        except Exception as e:
            print(f"    Error extracting coordinates: {e}")
            return None, None

    def generate_premet_file(self, data_file, umm_json):
        """
        Generate premet file for granule.

        Parameters:
        -----------
        data_file : Path
            Data file path
        umm_json : dict
            UMM-G metadata
        """
        # Create premet directory
        premet_dir = self.output_dir / "premet"
        premet_dir.mkdir(exist_ok=True)

        # Extract metadata from UMM-G

        # Handle both direct UMM-G and wrapped format
        if "umm" in umm_json and "TemporalExtent" not in umm_json:
            umm_json = umm_json["umm"]

        temporal_extent = umm_json.get("TemporalExtent", {})

        # Try different temporal data structures
        beginning_datetime = ""
        ending_datetime = ""

        # Try RangeDateTime first
        range_datetime = temporal_extent.get("RangeDateTime", {})
        if range_datetime:
            beginning_datetime = range_datetime.get("BeginningDateTime", "")
            ending_datetime = range_datetime.get("EndingDateTime", "")

        # Try SingleDateTime if RangeDateTime is empty
        if not beginning_datetime:
            single_datetime = temporal_extent.get("SingleDateTime", "")
            if single_datetime:
                beginning_datetime = single_datetime
                ending_datetime = single_datetime

        # Parse dates and times
        if beginning_datetime:
            try:
                begin_dt = datetime.fromisoformat(beginning_datetime.rstrip("Z"))
                begin_date = begin_dt.strftime("%Y-%m-%d")
                begin_time = begin_dt.strftime("%H:%M:%S.%f")[:-3]  # milliseconds
            except Exception as e:
                print(f"    Error parsing beginning datetime: {e}")
                begin_date = ""
                begin_time = ""
        else:
            begin_date = ""
            begin_time = ""

        if ending_datetime:
            try:
                end_dt = datetime.fromisoformat(ending_datetime.rstrip("Z"))
                end_date = end_dt.strftime("%Y-%m-%d")
                end_time = end_dt.strftime("%H:%M:%S.%f")[:-3]  # milliseconds
            except Exception as e:
                print(f"    Error parsing ending datetime: {e}")
                end_date = begin_date  # Use begin_date as fallback
                end_time = begin_time  # Use begin_time as fallback
        else:
            end_date = begin_date  # Use begin_date as fallback
            end_time = begin_time  # Use begin_time as fallback

        # Get platform/instrument info (umm_json might have been updated to inner object)
        # Re-check if we need to use the original for platforms
        platforms = umm_json.get("Platforms", [])
        platform_name = ""
        instrument_name = ""

        if platforms:
            platform_name = platforms[0].get("ShortName", "")
            instruments = platforms[0].get("Instruments", [])
            if instruments:
                instrument_name = instruments[0].get("ShortName", "")

        # Create premet content
        premet_content = f"""Data_FileName={data_file.name}
VersionID_local=001
Begin_date={begin_date}
End_date={end_date}
Begin_time={begin_time}
End_time={end_time}
Container=AdditionalAttributes
AdditionalAttributeName=CollectionShortName
ParameterValue={self.COLLECTION}
Container=AdditionalAttributes
AdditionalAttributeName=ProcessingLevel
ParameterValue=1A
Container=AssociatedPlatformInstrumentSensor
AssociatedPlatformShortName={platform_name}
AssociatedInstrumentShortName={instrument_name}
AssociatedSensorShortName={instrument_name}
"""

        # Write premet file
        premet_filename = f"{data_file.stem}.premet"
        premet_path = premet_dir / premet_filename

        with open(premet_path, "w") as f:
            f.write(premet_content)

        print(f"  Created premet file: {premet_filename}")

    def generate_spatial_file(self, data_file, lon, lat):
        """
        Generate spatial file with lon/lat coordinates.

        Parameters:
        -----------
        data_file : Path
            Data file path
        lon : array
            Longitude values
        lat : array
            Latitude values
        """
        # Create spatial directory
        spatial_dir = self.output_dir / "spatial"
        spatial_dir.mkdir(exist_ok=True)

        # Write spatial file
        spatial_filename = f"{data_file.stem}.spatial"
        spatial_path = spatial_dir / spatial_filename

        with open(spatial_path, "w") as f:
            for x, y in zip(lon, lat):
                f.write(f"{x:.6f} {y:.6f}\n")

        print(f"  Created spatial file: {spatial_filename} ({len(lon)} points)")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Download and process OLVIS1A granules"
    )
    parser.add_argument(
        "-n",
        "--number",
        type=int,
        default=5,
        help="Number of granules to process (default: 5)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="olvis1a_output",
        help="Output directory (default: olvis1a_output)",
    )

    args = parser.parse_args()

    # Create processor and run
    processor = OLVIS1AProcessor(output_dir=args.output)
    processor.process_granules(n_granules=args.number)
    print(f"\nProcessing complete. Output saved to: {processor.output_dir}")


if __name__ == "__main__":
    main()
