# Integration Guide for MetGenC

This guide explains how to integrate the spatial polygon generation module into the main MetGenC codebase.

## 1. Configuration Integration

Add spatial polygon options to MetGenC's configuration schema:

### In `src/nsidc/metgen/config.py`:

```python
# Add to configuration schema
SPATIAL_SCHEMA = {
    'enabled': {'type': 'boolean', 'default': False},
    'method': {
        'type': 'string', 
        'default': 'adaptive_beam',
        'allowed': ['beam', 'adaptive_beam', 'union_buffer', 'line_buffer']
    },
    'simplify': {'type': 'boolean', 'default': True},
    'target_vertices': {'type': 'integer', 'default': 8, 'min': 4, 'max': 100},
    'min_coverage': {'type': 'float', 'default': 0.90, 'min': 0.0, 'max': 1.0}
}
```

### In configuration `.ini` files:

```ini
[spatial]
enabled = true
method = adaptive_beam
simplify = true
target_vertices = 8
min_coverage = 0.90
```

## 2. Reader Integration

Modify readers to optionally generate spatial polygons:

### In `src/nsidc/metgen/readers/NetCDFReader.py`:

```python
from nsidc.metgen.spatial import PolygonGenerator

class NetCDFReader(Reader):
    def get_spatial_extent(self, filename):
        """Get spatial extent using polygon generation if enabled."""
        
        if self.config.get('spatial', {}).get('enabled', False):
            # Extract coordinates from NetCDF
            lon = self.dataset.variables['longitude'][:]
            lat = self.dataset.variables['latitude'][:]
            
            # Generate optimized polygon
            generator = PolygonGenerator()
            polygon, metadata = generator.create_flightline_polygon(
                lon, lat,
                method=self.config['spatial'].get('method', 'adaptive_beam'),
                iterative_simplify=self.config['spatial'].get('simplify', True),
                target_vertices=self.config['spatial'].get('target_vertices', 8),
                min_coverage=self.config['spatial'].get('min_coverage', 0.90)
            )
            
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
def compare_polygons(collection, number, provider, token_file, output):
    """Compare generated polygons with CMR polygons for a collection."""
    
    # Load token if provided
    token = None
    if token_file:
        with open(token_file, 'r') as f:
            token = f.read().strip()
    
    # Run comparison
    driver = PolygonComparisonDriver(output_dir=output, token=token)
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
from nsidc.metgen.spatial import PolygonGenerator

def test_polygon_generation():
    """Test basic polygon generation."""
    # Create test data
    lon = np.array([-120, -119.5, -119, -118.5])
    lat = np.array([35, 35.1, 35.2, 35.3])
    
    generator = PolygonGenerator()
    polygon, metadata = generator.create_flightline_polygon(
        lon, lat,
        method='convex'
    )
    
    assert polygon is not None
    assert metadata['vertices'] >= 3
    assert metadata['method'] == 'convex'

def test_simplification():
    """Test polygon simplification."""
    # Create more complex test data
    t = np.linspace(0, 10, 100)
    lon = -120 + 0.1 * t
    lat = 35 + 0.05 * t
    
    generator = PolygonGenerator()
    polygon, metadata = generator.create_flightline_polygon(
        lon, lat,
        method='beam',
        iterative_simplify=True,
        target_vertices=8
    )
    
    assert metadata['vertices'] <= 20  # Should be simplified
    assert 'simplification_history' in metadata
```

## 5. Documentation Updates

Update MetGenC documentation to include spatial polygon generation:

### In main README.md:

```markdown
## Spatial Polygon Generation

MetGenC now includes advanced polygon generation capabilities for creating
optimized spatial coverage polygons from point data. This is particularly
useful for LIDAR flightline data (LVIS, ILVIS2).

### Features
- Multiple polygon generation algorithms
- Automatic simplification to match CMR standards
- CMR polygon comparison and validation

### Usage
Enable in your configuration:
```ini
[spatial]
enabled = true
method = adaptive_beam
```

Compare with CMR:
```bash
metgenc compare-polygons LVISF2 -n 10 --token-file ~/.edl_token
```
```

## 6. Dependencies

Add required dependencies to `pyproject.toml` or `requirements.txt`:

```toml
[tool.poetry.dependencies]
shapely = "^2.0"
geopandas = "^0.14"
pyproj = "^3.6"
scipy = "^1.11"
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
        from nsidc.metgen.spatial import PolygonGenerator
        
        # Get coordinates from reader
        coords = reader.get_coordinates()
        
        # Generate polygon
        generator = PolygonGenerator()
        polygon, poly_metadata = generator.create_flightline_polygon(
            coords['longitude'],
            coords['latitude'],
            **config['spatial']
        )
        
        # Update metadata with polygon
        metadata['SpatialExtent'] = convert_polygon_to_ummg(polygon)
        metadata['ProcessingInformation']['PolygonGeneration'] = poly_metadata
    
    # Continue with existing workflow...
    return metadata
```

This integration allows MetGenC to generate optimized polygons that match CMR standards while maintaining backward compatibility with existing configurations.