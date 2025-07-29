"""
Command-line interface for MetGenC spatial polygon operations.

This module provides a standalone CLI for polygon comparison, validation,
and spatial processing tasks that are separate from the main MetGenC workflow.
"""

import logging
import sys
from pathlib import Path

import click

from nsidc.metgen import constants

LOGGER = logging.getLogger(constants.ROOT_LOGGER)


@click.group(
    name="metgenc-lab-polygons",
    epilog="For detailed help on each command, run: metgenc-lab-polygons COMMAND --help",
)
@click.version_option(package_name="nsidc-metgenc")
def cli():
    """MetGenC spatial polygon tools for comparison and validation.

    This utility provides tools for comparing generated polygons with CMR polygons,
    validating spatial coverage, and analyzing polygon generation performance.
    """
    # Set up basic logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


@cli.command(name="compare")
@click.argument("collection")
@click.option("-n", "--number", default=5, help="Number of granules to process")
@click.option("-p", "--provider", help="Data provider (e.g., NSIDC_CPRD)")
@click.option("-o", "--output", default="polygon_comparisons", help="Output directory")
@click.option("--granule", help="Process specific granule instead of random selection")
def compare_polygons(collection, number, provider, output, granule):
    """Compare generated polygons with CMR polygons for a collection.

    COLLECTION: The collection short name (e.g., LVISF2, ILVIS2)

    Examples:

    \b
    # Compare 10 random LVISF2 granules
    metgenc-lab-polygons compare LVISF2 -n 10 --provider NSIDC_CPRD

    \b
    # Compare specific granule
    metgenc-lab-polygons compare LVISF2 --granule "GRANULE_NAME"

    \b
    # Use custom output directory
    metgenc-lab-polygons compare ILVIS2 -n 20 -o /tmp/polygon_analysis
    """
    try:
        from nsidc.metgen.lab.polygon_driver import PolygonComparisonDriver
    except ImportError as e:
        click.echo(f"Error: Unable to import spatial polygon driver: {e}", err=True)
        click.echo("Make sure the spatial module dependencies are installed.", err=True)
        sys.exit(1)

    # Authentication is handled by earthaccess

    # Create output directory
    output_dir = Path(output)
    output_dir.mkdir(exist_ok=True)

    # Create driver with configuration
    driver = PolygonComparisonDriver(output_dir=str(output_dir))

    click.echo(f"Starting polygon comparison for collection: {collection}")
    click.echo(f"Output directory: {output_dir.absolute()}")

    try:
        if granule:
            # Process specific granule
            click.echo(f"Processing specific granule: {granule}")
            success = driver.process_specific_granule(
                short_name=collection, granule_ur=granule, provider=provider
            )
            if not success:
                raise click.ClickException("Failed to process granule")
        else:
            # Process random granules from collection
            click.echo(f"Processing {number} random granules")
            if provider:
                click.echo(f"Using provider: {provider}")
            success = driver.process_collection(
                short_name=collection, provider=provider, n_granules=number
            )

            if success:
                click.echo(
                    f"✓ Comparison completed! Results saved to: {output_dir.absolute()}"
                )
            else:
                click.echo(
                    f"⚠ Comparison completed with errors. Check output at: {output_dir.absolute()}"
                )
                raise click.ClickException("No granules were successfully processed")

    except Exception as e:
        click.echo(f"Error during polygon comparison: {e}", err=True)
        LOGGER.exception("Polygon comparison failed")
        sys.exit(1)


@cli.command(name="validate")
@click.argument("polygon_file")
@click.option(
    "--format",
    "file_format",
    type=click.Choice(["geojson", "wkt", "json"]),
    default="geojson",
    help="Input file format",
)
@click.option(
    "--check-coverage",
    is_flag=True,
    help="Check data coverage by comparing with points file",
)
@click.option(
    "--points-file",
    help="Points file for coverage validation (CSV with lon,lat columns)",
)
def validate_polygon(polygon_file, file_format, check_coverage, points_file):
    """Validate a spatial polygon file.

    POLYGON_FILE: Path to polygon file to validate

    Examples:

    \b
    # Validate a GeoJSON polygon
    metgenc-lab-polygons validate my_polygon.geojson

    \b
    # Validate and check coverage against source points
    metgenc-lab-polygons validate polygon.json --check-coverage --points-file points.csv
    """
    try:
        import geopandas as gpd
        import pandas as pd
        from shapely import wkt
        from shapely.geometry import Point
    except ImportError as e:
        click.echo(f"Error: Missing required dependencies: {e}", err=True)
        click.echo("Install with: pip install geopandas", err=True)
        sys.exit(1)

    polygon_path = Path(polygon_file)
    if not polygon_path.exists():
        click.echo(f"Error: Polygon file not found: {polygon_path}", err=True)
        sys.exit(1)

    click.echo(f"Validating polygon: {polygon_path}")

    try:
        # Load polygon based on format
        if file_format == "geojson":
            gdf = gpd.read_file(polygon_path)
            if len(gdf) == 0:
                click.echo("Error: No geometries found in GeoJSON file", err=True)
                sys.exit(1)
            polygon = gdf.geometry.iloc[0]

        elif file_format == "wkt":
            with open(polygon_path, "r") as f:
                wkt_string = f.read().strip()
            polygon = wkt.loads(wkt_string)

        elif file_format == "json":
            # Assume it's a JSON file with coordinates
            import json

            with open(polygon_path, "r") as f:
                data = json.load(f)
            # Handle different JSON structures
            if "coordinates" in data:
                coords = data["coordinates"]
            elif "geometry" in data and "coordinates" in data["geometry"]:
                coords = data["geometry"]["coordinates"]
            else:
                click.echo("Error: Unrecognized JSON polygon format", err=True)
                sys.exit(1)

            from shapely.geometry import Polygon

            polygon = Polygon(coords[0] if len(coords) == 1 else coords)

        # Validate polygon
        click.echo(f"Polygon type: {polygon.geom_type}")
        click.echo(f"Is valid: {polygon.is_valid}")
        click.echo(f"Area: {polygon.area:.6f} square degrees")
        click.echo(f"Vertices: {len(polygon.exterior.coords)}")

        if not polygon.is_valid:
            click.echo(f"Validation errors: {polygon.explain_validity()}", err=True)

        # Coverage check if requested
        if check_coverage:
            if not points_file:
                click.echo("Error: --points-file required for coverage check", err=True)
                sys.exit(1)

            points_path = Path(points_file)
            if not points_path.exists():
                click.echo(f"Error: Points file not found: {points_path}", err=True)
                sys.exit(1)

            # Load points
            df = pd.read_csv(points_path)
            if "lon" not in df.columns or "lat" not in df.columns:
                click.echo(
                    "Error: Points file must have 'lon' and 'lat' columns", err=True
                )
                sys.exit(1)

            # Check coverage
            points = [Point(row.lon, row.lat) for _, row in df.iterrows()]
            covered = sum(1 for point in points if polygon.contains(point))
            coverage = covered / len(points) if points else 0

            click.echo("Coverage analysis:")
            click.echo(f"  Total points: {len(points)}")
            click.echo(f"  Covered points: {covered}")
            click.echo(f"  Coverage: {coverage:.1%}")

        click.echo("✓ Validation completed!")

    except Exception as e:
        click.echo(f"Error during validation: {e}", err=True)
        LOGGER.exception("Polygon validation failed")
        sys.exit(1)


@cli.command(name="info")
def info():
    """Display information about the spatial polygon tools."""
    click.echo("MetGenC Spatial Polygon Tools")
    click.echo("=" * 40)
    click.echo()
    click.echo("This tool provides utilities for:")
    click.echo("• Comparing generated polygons with CMR reference data")
    click.echo("• Validating polygon geometry and coverage")
    click.echo("• Analyzing spatial processing performance")
    click.echo()
    click.echo("Available commands:")
    click.echo("• compare  - Compare polygons with CMR data")
    click.echo("• validate - Validate polygon files")
    click.echo("• info     - Show this information")
    click.echo()
    click.echo("For help with a specific command:")
    click.echo("  metgenc-lab-polygons COMMAND --help")


if __name__ == "__main__":
    cli()
