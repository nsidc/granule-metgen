#!/usr/bin/env python3
"""
Example usage of the spatial polygon generation module.
"""

import numpy as np
from pathlib import Path
import sys

# Add parent directories to path if running standalone
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from nsidc.metgen.spatial import PolygonGenerator, CMRClient, PolygonComparator

def example_polygon_generation():
    """Example of generating a polygon from point data."""
    
    # Create sample flightline data
    # In practice, this would come from your LVIS/ILVIS2 file
    t = np.linspace(0, 10, 1000)
    lon = -120 + 0.1 * t + 0.01 * np.sin(5 * t)
    lat = 35 + 0.05 * t + 0.01 * np.cos(3 * t)
    
    # Initialize generator
    generator = PolygonGenerator()
    
    # Generate polygon using adaptive beam method
    polygon, metadata = generator.create_flightline_polygon(
        lon, lat,
        method='adaptive_beam',
        iterative_simplify=True,
        target_vertices=8,
        min_iou=0.70
    )
    
    print(f"Generated polygon with {metadata['vertices']} vertices")
    print(f"Original data points: {metadata['points']}")
    print(f"Method used: {metadata['method']}")
    if 'adaptive_buffer' in metadata:
        print(f"Adaptive buffer size: {metadata['adaptive_buffer']:.1f} meters")
    
    return polygon, metadata


def example_cmr_comparison():
    """Example of comparing with CMR polygon."""
    
    # Generate a polygon
    polygon, metadata = example_polygon_generation()
    
    # In practice, you would get the CMR polygon from the API
    # Here we'll create a dummy comparison
    from shapely.geometry import box
    dummy_cmr_polygon = box(-120, 35, -119, 35.5)
    
    # Create GeoJSON for comparison
    generated_geojson = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": polygon.__geo_interface__,
            "properties": metadata
        }]
    }
    
    cmr_geojson = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": dummy_cmr_polygon.__geo_interface__,
            "properties": {"source": "CMR"}
        }]
    }
    
    # Compare polygons
    metrics = PolygonComparator.compare(cmr_geojson, generated_geojson)
    
    print("\nComparison Results:")
    print(f"IoU: {metrics['iou']:.3f}")
    print(f"Area ratio: {metrics['area_ratio']:.3f}")
    print(f"CMR vertices: {metrics['cmr_vertices']}")
    print(f"Generated vertices: {metrics['generated_vertices']}")


def example_cmr_query():
    """Example of querying CMR for granules."""
    
    # Initialize client (without token for public collections)
    client = CMRClient()
    
    # Query for granules
    print("\nQuerying CMR for ILVIS2 granules...")
    granules = client.query_granules(
        short_name='ILVIS2',
        provider='NSIDC_ECS',
        limit=3
    )
    
    print(f"Found {len(granules)} granules")
    for g in granules:
        print(f"  - {g.get('title', 'Unknown')}")


if __name__ == "__main__":
    print("=== Spatial Polygon Generation Examples ===\n")
    
    print("1. Generating polygon from point data:")
    print("-" * 40)
    example_polygon_generation()
    
    print("\n2. Comparing with CMR polygon:")
    print("-" * 40)
    example_cmr_comparison()
    
    print("\n3. Querying CMR:")
    print("-" * 40)
    try:
        example_cmr_query()
    except Exception as e:
        print(f"CMR query failed (expected without auth): {e}")
    
    print("\nFor full workflow with real data, use:")
    print("  python polygon_cli.py COLLECTION_NAME -n 5 --token-file ~/.edl_token")