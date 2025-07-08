# Integration Guide for MetGenC Spatial Module

This guide explains how to integrate the spatial polygon generation module into the main MetGenC codebase.

## Overview

The spatial module has been simplified to use a single, optimized polygon generation approach that combines concave hull generation with intelligent buffering to achieve 98%+ data coverage with minimal vertices.

## 1. Configuration Integration

Add spatial polygon options to MetGenC's configuration schema:

### In `src/nsidc/metgen/config.py`:

```python
# Add to configuration schema
SPATIAL_SCHEMA = {
    'enabled': {'type': 'boolean', 'default': False},
    'target_coverage': {'type': 'float', 'default': 0.98, 'min': 0.80, 'max': 1.0},
    'max_vertices': {'type': 'integer', 'default': 100, 'min': 10, 'max': 200}
}
```

### In configuration `.ini` files:

```ini
[spatial]
enabled = true
target_coverage = 0.98
max_vertices = 100
```

## 2. Reader Integration

Modify readers to generate spatial polygons:

### In `src/nsidc/metgen/readers/NetCDFReader.py`:

```python
from nsidc.metgen.spatial import create_flightline_polygon

class NetCDFReader(Reader):
    def get_spatial_extent(self, filename):
        """Get spatial extent using optimized polygon generation."""
        
        if self.config.get('spatial', {}).get('enabled', False):
            # Extract coordinates from NetCDF
            lon = self.dataset.variables['longitude'][:]
            lat = self.dataset.variables['latitude'][:]
            
            # Generate optimized polygon
            polygon, metadata = create_flightline_polygon(lon, lat)
            
            # Convert to GeoJSON for UMM-G
            return {
                "HorizontalSpatialDomain": {
                    "Geometry": {
                        "GPolygons": [{
                            "Boundary": {
                                "Points": [
                                    {"Longitude": coord[0], "Latitude": coord[1]}
                                    for coord in polygon.exterior.coords[:-1]  # Exclude duplicate last point
                                ]
                            }
                        }]
                    }
                }
            }
        else:
            # Fall back to existing bounding box method
            return super().get_spatial_extent(filename)
```

## 3. CLI Integration

Add polygon comparison command to MetGenC CLI:

### In `src/nsidc/metgen/cli.py`:

```python
from nsidc.metgen.spatial.polygon_driver import PolygonComparisonDriver

@cli.command()
@click.argument('collection')
@click.option('-n', '--number', default=5, help='Number of granules to process')
@click.option('-p', '--provider', help='Data provider')
@click.option('--token-file', help='Path to EDL bearer token file')
@click.option('-o', '--output', default='polygon_comparisons', help='Output directory')
@click.option('-w', '--workers', default=1, help='Number of parallel workers')
def compare_polygons(collection, number, provider, token_file, output, workers):
    """Compare generated polygons with CMR polygons for a collection."""
    
    # Load token if provided
    token = None
    if token_file:
        with open(token_file, 'r') as f:
            token = f.read().strip()
    
    # Run comparison
    driver = PolygonComparisonDriver(output_dir=output, token=token, max_workers=workers)
    driver.process_collection(
        short_name=collection,
        provider=provider,
        n_granules=number
    )
```

## 4. Testing Integration

Add tests for spatial polygon generation:

### Create `tests/test_spatial_polygon.py`:

```python
import pytest
import numpy as np
from nsidc.metgen.spatial import create_flightline_polygon

def test_polygon_generation():
    """Test basic polygon generation."""
    # Create test data
    lon = np.array([-120, -119.5, -119, -118.5])
    lat = np.array([35, 35.1, 35.2, 35.3])
    
    polygon, metadata = create_flightline_polygon(lon, lat)
    
    assert polygon is not None
    assert metadata['vertices'] >= 3
    assert metadata['method'] == 'concave_hull'
    assert metadata['final_data_coverage'] >= 0.90

def test_large_dataset():
    """Test polygon generation with large datasets."""
    # Create large test data
    t = np.linspace(0, 10, 10000)
    lon = -120 + 0.1 * t
    lat = 35 + 0.05 * t
    
    polygon, metadata = create_flightline_polygon(lon, lat)
    
    assert metadata['vertices'] <= 150  # Should be manageable
    assert metadata['final_data_coverage'] >= 0.95
    assert 'subsampling_used' in metadata

def test_antimeridian_crossing():
    """Test handling of antimeridian crossing."""
    # Create data that crosses antimeridian
    lon = np.array([179, 179.5, -179.5, -179])
    lat = np.array([60, 60.1, 60.2, 60.3])
    
    polygon, metadata = create_flightline_polygon(lon, lat)
    
    assert polygon is not None
    assert polygon.is_valid
    assert metadata['vertices'] >= 3
```

## 5. Documentation Updates

Update MetGenC documentation to include spatial polygon generation:

### In main README.md:

```markdown
## Spatial Polygon Generation

MetGenC includes optimized polygon generation capabilities for creating
spatial coverage polygons from point data, particularly useful for 
LIDAR flightline data (LVIS, ILVIS2).

### Features
- Single optimized algorithm combining concave hull + intelligent buffering
- Achieves 98%+ data coverage with minimal vertices
- Handles antimeridian crossing for global datasets
- Automatic subsampling for large datasets
- CMR polygon comparison and validation

### Usage
Enable in your configuration:
```ini
[spatial]
enabled = true
target_coverage = 0.98
```

Compare with CMR:
```bash
metgenc compare-polygons LVISF2 -n 10 --token-file ~/.edl_token
```
```

## 6. Dependencies

Add required dependencies to `pyproject.toml`:

```toml
[tool.poetry.dependencies]
shapely = "^2.0"
geopandas = "^0.14"
matplotlib = "^3.7"
concave-hull = "^0.0.3"
requests = "^2.31"
```

## Complete Integration Example

Here's how a complete integration might look in a MetGenC workflow:

```python
# In metgen.py process_granule function
def process_granule(config, granule_file):
    """Process a single granule with optional polygon generation."""
    
    # Existing processing...
    reader = get_reader(config, granule_file)
    metadata = reader.extract_metadata()
    
    # Add spatial polygon if enabled
    if config.get('spatial', {}).get('enabled', False):
        from nsidc.metgen.spatial import create_flightline_polygon
        
        # Get coordinates from reader
        coords = reader.get_coordinates()
        
        # Generate polygon
        polygon, poly_metadata = create_flightline_polygon(
            coords['longitude'],
            coords['latitude']
        )
        
        # Update metadata with polygon
        metadata['SpatialExtent'] = convert_polygon_to_ummg(polygon)
        metadata['ProcessingInformation']['PolygonGeneration'] = poly_metadata
    
    # Continue with existing workflow...
    return metadata
```

## Key Simplifications Made

1. **Single Algorithm**: Replaced multiple generation methods with one optimized approach
2. **Removed Classes**: Eliminated `PolygonGenerator` class in favor of simple function
3. **Consolidated Modules**: Combined functionality into `polygon_generator.py`
4. **Removed Complexity**: Eliminated iterative simplification and adaptive method selection
5. **Focused Approach**: Optimized specifically for LIDAR flightline data patterns

This simplified integration maintains high performance while reducing code complexity and maintenance overhead.