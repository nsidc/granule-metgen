#!/usr/bin/env python3
"""
Integration test runner for MetGenC.

This script automates the process of:
1. Downloading sample data from the staging server
2. Running metgenc with pre-configured INI files
3. Validating the generated output
"""

import argparse
import logging
import shutil
import sys
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class IntegrationTestRunner:
    """Runs integration tests for MetGenC collections."""

    BASE_URL = (
        "http://staging-http.apps.int.nsidc.org/staging/SAMPLE_DATA/DUCk_project/"
    )

    def __init__(self, work_dir: Optional[Path] = None):
        """Initialize the test runner.

        Args:
            work_dir: Working directory for tests (default workspace if not specified)
        """
        if work_dir:
            self.work_dir = work_dir
        else:
            # Use default workspace directory
            self.work_dir = Path(__file__).parent / "workspace"

        self.work_dir.mkdir(exist_ok=True)
        self.configs_dir = Path(__file__).parent / "configs"

    def list_available_collections(self) -> List[str]:
        """List all available collections based on INI files in configs directory."""
        if not self.configs_dir.exists():
            return []
        return [f.stem for f in self.configs_dir.glob("*.ini")]

    def download_collection_data(
        self, collection_name: str, output_dir: Path, force_download: bool = False
    ) -> List[Path]:
        """Download all files for a collection from the staging server.

        Args:
            collection_name: Name of the collection
            output_dir: Directory to save downloaded files
            force_download: If True, re-download even if files exist

        Returns:
            List of downloaded file paths
        """
        collection_url = urljoin(self.BASE_URL, f"{collection_name}/")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Check if data already exists
        if not force_download and output_dir.exists():
            existing_files = []
            for pattern in ["*.nc", "*.csv", "*.TXT", "*.JPG", "*.jpeg", "*.png"]:
                existing_files.extend(output_dir.glob(pattern))

            # Check subdirectories too
            for subdir in ["premet", "spatial"]:
                subdir_path = output_dir / subdir
                if subdir_path.exists():
                    for pattern in ["*"]:
                        existing_files.extend(subdir_path.glob(pattern))

            if existing_files:
                logger.info(
                    f"Found {len(existing_files)} existing files for {collection_name}, skipping download"
                )
                logger.info("Use --force-download to re-download")
                return existing_files

        logger.info(f"Downloading data from {collection_url}")
        downloaded_files = []

        try:
            response = requests.get(collection_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Parse directory listing
            for link in soup.find_all("a"):
                href = link.get("href", "")

                # Skip parent directory, query parameters, and empty hrefs
                if (
                    not href
                    or href.startswith("../")
                    or href.startswith("?")
                    or href.startswith("#")
                ):
                    continue

                # Check if it's a subdirectory we need to handle
                if href.endswith("/"):
                    subdir_name = href.rstrip("/")
                    if subdir_name in ["premet", "spatial"]:
                        # Download subdirectory contents to subdirectory
                        subdir_files = self._download_subdirectory(
                            collection_url + href,
                            output_dir / subdir_name,
                            force_download,
                        )
                        downloaded_files.extend(subdir_files)
                    elif subdir_name == "data":
                        # Download data subdirectory contents to root output directory
                        subdir_files = self._download_subdirectory(
                            collection_url + href, output_dir, force_download
                        )
                        downloaded_files.extend(subdir_files)
                    continue

                # Download regular file
                file_url = urljoin(collection_url, href)
                file_path = output_dir / href

                # Skip if file exists and not forcing download
                if not force_download and file_path.exists():
                    logger.info(f"  Skipping {href} (already exists)")
                    downloaded_files.append(file_path)
                    continue

                logger.info(f"  Downloading {href}...")
                file_response = requests.get(file_url, timeout=60)
                file_response.raise_for_status()

                file_path.write_bytes(file_response.content)
                downloaded_files.append(file_path)

        except requests.RequestException as e:
            logger.error(f"Error downloading data: {e}")
            raise

        logger.info(f"Downloaded {len(downloaded_files)} files")
        return downloaded_files

    def _download_subdirectory(
        self, subdir_url: str, output_dir: Path, force_download: bool = False
    ) -> List[Path]:
        """Download all files from a subdirectory.

        Args:
            subdir_url: URL of the subdirectory
            output_dir: Directory to save downloaded files
            force_download: If True, re-download even if files exist

        Returns:
            List of downloaded file paths
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        downloaded_files = []

        try:
            response = requests.get(subdir_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            for link in soup.find_all("a"):
                href = link.get("href", "")

                # Skip parent directory, query parameters, directories, and empty hrefs
                if (
                    not href
                    or href.startswith("../")
                    or href.startswith("?")
                    or href.startswith("#")
                    or href.endswith("/")
                ):
                    continue

                file_url = urljoin(subdir_url, href)
                file_path = output_dir / href

                # Skip if file exists and not forcing download
                if not force_download and file_path.exists():
                    logger.info(f"  Skipping {output_dir.name}/{href} (already exists)")
                    downloaded_files.append(file_path)
                    continue

                logger.info(f"  Downloading {output_dir.name}/{href}...")
                file_response = requests.get(file_url, timeout=60)
                file_response.raise_for_status()

                file_path.write_bytes(file_response.content)
                downloaded_files.append(file_path)

        except requests.RequestException as e:
            logger.error(f"Error downloading subdirectory: {e}")
            raise

        return downloaded_files

    def prepare_ini_file(self, collection_name: str, test_dir: Path) -> Path:
        """Prepare INI file for testing by copying and updating paths.

        Args:
            collection_name: Name of the collection
            test_dir: Test directory containing downloaded data

        Returns:
            Path to prepared INI file
        """
        source_ini = self.configs_dir / f"{collection_name}.ini"
        if not source_ini.exists():
            raise FileNotFoundError(f"INI file not found: {source_ini}")

        # Copy INI file to test directory
        dest_ini = test_dir / f"{collection_name}.ini"

        # Read and update INI file
        import configparser

        config = configparser.ConfigParser()
        config.read(source_ini)

        # Update paths to point to test directory
        if "Source" in config:
            config["Source"]["data_dir"] = str(test_dir / "data")
            if "premet_dir" in config["Source"]:
                config["Source"]["premet_dir"] = str(test_dir / "data" / "premet")
            if "spatial_dir" in config["Source"]:
                config["Source"]["spatial_dir"] = str(test_dir / "data" / "spatial")

        if "Destination" in config:
            config["Destination"]["local_output_dir"] = str(test_dir / "output")

        # Write updated INI file
        with open(dest_ini, "w") as f:
            config.write(f)

        return dest_ini

    def run_metgenc(
        self, ini_file: Path, environment: str = "uat"
    ) -> Tuple[bool, Optional[str]]:
        """Run metgenc process command.

        Args:
            ini_file: Path to INI configuration file
            environment: Environment to use (uat, sit, prod)

        Returns:
            Tuple of (success, output_or_error)
        """
        import subprocess

        cmd = [
            "metgenc",
            "process",
            "--config",
            str(ini_file),
            "-e",
            environment,
            "--dry-run",
            "--overwrite",
        ]

        logger.info(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)

            if result.returncode == 0:
                logger.info("MetGenC completed successfully")
                return True, result.stdout
            else:
                logger.error(f"MetGenC failed with exit code {result.returncode}")
                logger.error(f"Error output: {result.stderr}")
                return False, result.stderr

        except Exception as e:
            logger.error(f"Error running metgenc: {e}")
            return False, str(e)

    def validate_output(
        self, config_file: Path, output_dir: Path
    ) -> Tuple[bool, List[str]]:
        """Validate generated output files using metgenc validate.

        Args:
            config_file: Path to the INI configuration file
            output_dir: Directory containing output files

        Returns:
            Tuple of (success, list_of_issues)
        """
        import subprocess

        issues = []

        # Check if output directory exists
        if not output_dir.exists():
            issues.append("Output directory does not exist")
            return False, issues

        cnm_dir = output_dir / "cnm"
        ummg_dir = output_dir / "ummg"

        # Check for at least one output type
        if not cnm_dir.exists() and not ummg_dir.exists():
            issues.append("No CNM or UMM-G output directories found")
            return False, issues

        # Validate CNM files using metgenc validate
        if cnm_dir.exists():
            cnm_files = list(cnm_dir.glob("*.json"))
            logger.info(f"Found {len(cnm_files)} CNM files")

            if cnm_files:
                logger.info("Validating CNM files...")
                cmd = [
                    "metgenc",
                    "validate",
                    "--config",
                    str(config_file),
                    "--type",
                    "cnm",
                ]
                try:
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=60
                    )
                    if result.returncode != 0:
                        issues.append(f"CNM validation failed: {result.stderr}")
                        logger.error(f"CNM validation output: {result.stdout}")
                    else:
                        logger.info("CNM validation passed")
                except Exception as e:
                    issues.append(f"CNM validation error: {e}")
            else:
                issues.append("CNM directory exists but contains no JSON files")

        # Validate UMM-G files using metgenc validate
        if ummg_dir.exists():
            ummg_files = list(ummg_dir.glob("*.json"))
            logger.info(f"Found {len(ummg_files)} UMM-G files")

            if ummg_files:
                logger.info("Validating UMM-G files...")
                cmd = [
                    "metgenc",
                    "validate",
                    "--config",
                    str(config_file),
                    "--type",
                    "ummg",
                ]
                try:
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=60
                    )
                    if result.returncode != 0:
                        issues.append(f"UMM-G validation failed: {result.stderr}")
                        logger.error(f"UMM-G validation output: {result.stdout}")
                    else:
                        logger.info("UMM-G validation passed")
                except Exception as e:
                    issues.append(f"UMM-G validation error: {e}")
            else:
                issues.append("UMM-G directory exists but contains no JSON files")

        return len(issues) == 0, issues

    def run_test(
        self,
        collection_name: str,
        environment: str = "uat",
        keep_files: bool = False,
        force_download: bool = False,
    ) -> bool:
        """Run integration test for a single collection.

        Args:
            collection_name: Name of the collection to test
            environment: Environment to use
            keep_files: If True, don't cleanup test files
            force_download: If True, re-download even if files exist

        Returns:
            True if test passed
        """
        test_dir = self.work_dir / collection_name
        test_dir.mkdir(exist_ok=True)

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Testing collection: {collection_name}")
        logger.info(f"{'=' * 60}")

        try:
            # Download sample data
            data_dir = test_dir / "data"
            downloaded_files = self.download_collection_data(
                collection_name, data_dir, force_download
            )

            if not downloaded_files:
                logger.error(f"No files downloaded for {collection_name}")
                return False

            # Prepare INI file
            ini_file = self.prepare_ini_file(collection_name, test_dir)

            # Create output directory and subdirectories
            output_dir = test_dir / "output"
            output_dir.mkdir(exist_ok=True)
            (output_dir / "cnm").mkdir(exist_ok=True)
            (output_dir / "ummg").mkdir(exist_ok=True)

            # Run metgenc
            success, output = self.run_metgenc(ini_file, environment)
            if not success:
                logger.error(f"MetGenC failed: {output}")
                return False

            # Validate output
            valid, issues = self.validate_output(ini_file, test_dir / "output")
            if not valid:
                logger.error("Output validation failed:")
                for issue in issues:
                    logger.error(f"  - {issue}")
                return False

            logger.info(f"✓ Test passed for {collection_name}")
            return True

        except Exception as e:
            logger.error(f"Test failed with exception: {e}")
            import traceback

            logger.debug(traceback.format_exc())
            return False

        finally:
            if not keep_files:
                logger.info(f"Cleaning up test files for {collection_name}")
                shutil.rmtree(test_dir, ignore_errors=True)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run MetGenC integration tests",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test a single collection
  %(prog)s irtit3duck

  # Test all collections
  %(prog)s all

  # Test with different environment
  %(prog)s snexduck -e sit

  # Keep test files for debugging
  %(prog)s modscg --keep-files

  # Force re-download of sample data
  %(prog)s snexduck --force-download
""",
    )

    parser.add_argument(
        "collection", help="Collection name to test (or 'all' for all collections)"
    )
    parser.add_argument(
        "-e",
        "--environment",
        default="uat",
        choices=["uat", "sit", "prod"],
        help="Environment to use (default: uat)",
    )
    parser.add_argument(
        "--keep-files",
        action="store_true",
        help="Don't cleanup test files after completion",
    )
    parser.add_argument(
        "--force-download",
        action="store_true",
        help="Re-download sample data even if files already exist",
    )
    parser.add_argument(
        "-w",
        "--work-dir",
        help="Working directory for tests (default: tests/integration/workspace)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Initialize runner
    work_dir = Path(args.work_dir) if args.work_dir else None
    runner = IntegrationTestRunner(work_dir=work_dir)

    # Get available collections
    available = runner.list_available_collections()

    if not available:
        logger.error("No collection configurations found in configs directory")
        logger.error(
            "Please ensure INI files are present in tests/integration/configs/"
        )
        sys.exit(1)

    # Determine which collections to test
    if args.collection == "all":
        collections_to_test = available
    else:
        if args.collection not in available:
            logger.error(f"Unknown collection: {args.collection}")
            logger.info(f"Available collections: {', '.join(sorted(available))}")
            sys.exit(1)
        collections_to_test = [args.collection]

    # Run tests
    results = {}
    for collection in collections_to_test:
        results[collection] = runner.run_test(
            collection, args.environment, args.keep_files, args.force_download
        )

    # Print summary
    print(f"\n{'=' * 60}")
    print("INTEGRATION TEST SUMMARY")
    print(f"{'=' * 60}")

    for collection, passed in sorted(results.items()):
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{collection:<20} {status}")

    passed_count = sum(1 for p in results.values() if p)
    failed_count = len(results) - passed_count

    print(
        f"\nTotal: {len(results)} tests, {passed_count} passed, {failed_count} failed"
    )

    if failed_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
