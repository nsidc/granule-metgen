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

## 2. Spatial Processor Integration

The recommended approach is to integrate polygon generation at the UMM-G creation stage using a `SpatialProcessor`, not at the reader level. This provides better separation of concerns and follows project rules.

### Create `src/nsidc/metgen/spatial_processor.py`:

The `SpatialProcessor` class handles spatial polygon generation during UMM-G metadata creation, applying the rules defined in the project README:

- `.spatial` files with >= 2 geodetic points → GPolygon(s) calculated to enclose all points
- Data files with >= 2 geodetic points → GPolygon(s) calculated to enclose all points  
- NetCDF gridded data with >= 3 geodetic points → GPolygon calculated from grid perimeter
- Collections like LVISF2, IPFLT1B, ILVIS2 → Apply polygon generation automatically

### In `src/nsidc/metgen/metgen.py`:

Replace the `populate_spatial` function call with the spatial processor:

```python
from nsidc.metgen.spatial_processor import process_spatial_extent_with_polygon_generation

# In the granule processing function, replace:
# summary["spatial_extent"] = populate_spatial(gsr, summary["geometry"])

# With:
summary["spatial_extent"] = process_spatial_extent_with_polygon_generation(
    config=config,
    spatial_representation=gsr,
    spatial_values=summary["geometry"],
    collection_name=config.get('global', {}).get('auth_id', ''),
    data_file_path=granule_file,
    coordinate_data=coordinate_data  # If available from reader
)
```

### Reader Modifications (Optional Enhancement):

Readers can optionally provide full coordinate data for better polygon generation:

```python
# In NetCDFReader or CSVReader
def get_coordinate_data(self):
    """Provide full coordinate arrays for spatial processing."""
    try:
        if hasattr(self, 'dataset'):
            # NetCDF case
            return {
                'longitude': self.dataset.variables['longitude'][:],
                'latitude': self.dataset.variables['latitude'][:]
            }
        elif hasattr(self, 'dataframe'):
            # CSV case  
            return {
                'longitude': self.dataframe['longitude'].values,
                'latitude': self.dataframe['latitude'].values
            }
    except Exception:
        return None
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
@click.option('--granule', help='Process specific granule instead of random selection')
def compare_polygons(collection, number, provider, token_file, output, workers, granule):
    """Compare generated polygons with CMR polygons for a collection."""
    
    # Load token if provided
    token = None
    if token_file:
        try:
            with open(token_file, 'r') as f:
                token = f.read().strip()
            print(f"Loaded EDL bearer token from {token_file}")
        except Exception as e:
            print(f"Warning: Could not read token file {token_file}: {e}")
    
    # Create driver with parallel processing support
    driver = PolygonComparisonDriver(
        output_dir=output, 
        token=token, 
        max_workers=workers
    )
    
    if granule:
        # Process specific granule
        driver.process_specific_granule(
            short_name=collection,
            granule_ur=granule,
            provider=provider
        )
    else:
        # Process random granules from collection
        driver.process_collection(
            short_name=collection,
            provider=provider,
            n_granules=number
        )
```

## 4. Testing Integration

Add tests for spatial polygon generation:

### Create `tests/test_spatial_integration.py`:

```python
import pytest
import numpy as np
from nsidc.metgen.spatial import create_flightline_polygon

class TestSpatialIntegration:
    """Integration tests for spatial polygon generation."""

    def test_basic_polygon_generation(self):
        """Test basic polygon generation."""
        # Create test data
        lon = np.array([-120, -119.5, -119, -118.5])
        lat = np.array([35, 35.1, 35.2, 35.3])
        
        polygon, metadata = create_flightline_polygon(lon, lat)
        
        assert polygon is not None
        assert metadata['vertices'] >= 3
        assert metadata['method'] in ['concave_hull', 'convex_hull_fallback']
        assert metadata['final_data_coverage'] >= 0.90

    def test_large_dataset_handling(self):
        """Test handling of large datasets."""
        # Create large test data
        t = np.linspace(0, 100, 15000)
        lon = -120 + 0.1 * t + 0.01 * np.random.randn(15000)
        lat = 35 + 0.05 * t + 0.01 * np.random.randn(15000)
        
        polygon, metadata = create_flightline_polygon(lon, lat)
        
        assert polygon is not None
        assert metadata.get('subsampling_used', False) == True
        assert metadata['final_data_coverage'] >= 0.90
        assert metadata['vertices'] <= 150  # Should be manageable

    def test_antimeridian_crossing(self):
        """Test antimeridian crossing handling."""
        # Create data that crosses antimeridian
        lon = np.array([179, 179.5, -179.5, -179, -178.5])
        lat = np.array([60, 60.1, 60.2, 60.3, 60.4])
        
        polygon, metadata = create_flightline_polygon(lon, lat)
        
        assert polygon is not None
        assert polygon.is_valid
        assert metadata['vertices'] >= 3

    def test_edge_cases(self):
        """Test edge cases."""
        # Empty data
        polygon, metadata = create_flightline_polygon([], [])
        assert polygon is None or polygon.is_empty
        
        # Single point
        polygon, metadata = create_flightline_polygon([-120], [35])
        assert polygon is not None
        assert metadata['method'] == 'simple_buffer'
        
        # Two points
        polygon, metadata = create_flightline_polygon([-120, -119], [35, 35.5])
        assert polygon is not None
        assert metadata['method'] == 'simple_buffer'

    def test_performance(self):
        """Test performance characteristics."""
        # Medium dataset
        t = np.linspace(0, 10, 1000)
        lon = -120 + 0.1 * t
        lat = 35 + 0.05 * t
        
        polygon, metadata = create_flightline_polygon(lon, lat)
        
        # Should complete quickly
        assert metadata['generation_time_seconds'] < 1.0
        assert metadata['final_data_coverage'] >= 0.95
        assert metadata['vertices'] <= 100
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
- Automatic subsampling for large datasets (350k+ points)
- Parallel processing for batch operations
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

Process specific granule:
```bash
metgenc compare-polygons LVISF2 --granule "GRANULE_NAME.TXT" -p NSIDC_CPRD
```
```

## 6. Dependencies

Add required dependencies to `pyproject.toml`:

```toml
[tool.poetry.dependencies]
shapely = "^2.0"
geopandas = "^1.1"
matplotlib = "^3.7"
concave-hull = "^0.0.9"
requests = "^2.31"
numpy = "^1.24"
```

## Complete Integration Example

Here's how the complete integration looks in the MetGenC workflow:

```python
# In metgen.py
from nsidc.metgen.spatial_processor import SpatialProcessor

def process_granule(config, granule_file):
    """Process a single granule with automatic spatial polygon generation."""
    
    # Existing processing...
    reader = get_reader(config, granule_file)
    summary = extract_granule_metadata(reader, granule_file, config)
    
    # Get spatial representation and geometry from existing logic
    gsr = determine_granule_spatial_representation(reader, config)
    geometry = extract_spatial_geometry(reader, config)
    
    # NEW: Use SpatialProcessor for spatial extent generation
    processor = SpatialProcessor(config)
    
    # Get coordinate data from reader if available for enhanced polygon generation
    coordinate_data = None
    if hasattr(reader, 'get_coordinate_data'):
        coordinate_data = reader.get_coordinate_data()
    
    # Process spatial extent with automatic polygon generation when appropriate
    summary["spatial_extent"] = processor.process_spatial_extent(
        spatial_representation=gsr,
        spatial_values=geometry,
        collection_name=config.get('global', {}).get('auth_id', ''),
        data_file_path=granule_file,
        coordinate_data=coordinate_data
    )
    
    # Continue with existing UMM-G generation...
    return generate_ummg_metadata(summary, config)

# Alternative: Simple drop-in replacement
def process_granule_simple(config, granule_file):
    """Simple integration using convenience function."""
    
    # Existing processing...
    summary = extract_granule_metadata_existing_way()
    
    # Replace this line:
    # summary["spatial_extent"] = populate_spatial(gsr, summary["geometry"])
    
    # With this:
    from nsidc.metgen.spatial_processor import process_spatial_extent_with_polygon_generation
    
    summary["spatial_extent"] = process_spatial_extent_with_polygon_generation(
        config=config,
        spatial_representation=gsr, 
        spatial_values=summary["geometry"],
        collection_name=config.get('global', {}).get('auth_id', ''),
        data_file_path=granule_file
    )
    
    return summary
```

### Rules-Based Processing

The SpatialProcessor automatically applies project rules:

```python
# Example rule evaluation for different scenarios:

# LVISF2 collection with 1000 geodetic points → Polygon generated
# MODIS collection with 4 cartesian points → Bounding rectangle (no polygon)  
# Generic collection with 50 geodetic points → Polygon generated
# Collection with 1 geodetic point → Point geometry (no polygon)
# .spatial file with 5 geodetic points → Polygon generated

# Configuration controls overall enable/disable:
config = {
    'spatial': {
        'enabled': True,        # Master switch
        'target_coverage': 0.98 # Coverage goal for generated polygons
    }
}
```

## Error Handling

```python
def safe_polygon_generation(lon, lat):
    """Safely generate polygon with error handling."""
    try:
        from nsidc.metgen.spatial import create_flightline_polygon
        
        if len(lon) < 3:
            print("Warning: Insufficient points for polygon generation")
            return None, None
            
        polygon, metadata = create_flightline_polygon(lon, lat)
        
        if metadata['final_data_coverage'] < 0.80:
            print(f"Warning: Low data coverage ({metadata['final_data_coverage']:.1%})")
            
        return polygon, metadata
        
    except Exception as e:
        print(f"Error in polygon generation: {e}")
        return None, None
```

## Configuration Schema Integration

```python
# Complete spatial configuration schema
SPATIAL_CONFIG_SCHEMA = {
    'type': 'object',
    'properties': {
        'enabled': {'type': 'boolean', 'default': False},
        'target_coverage': {
            'type': 'number',
            'minimum': 0.8,
            'maximum': 1.0,
            'default': 0.98
        },
        'max_vertices': {
            'type': 'integer', 
            'minimum': 10,
            'maximum': 200,
            'default': 100
        },
        'longitude_column': {'type': 'string', 'default': 'longitude'},
        'latitude_column': {'type': 'string', 'default': 'latitude'},
        'enable_parallel': {'type': 'boolean', 'default': True},
        'max_workers': {'type': 'integer', 'minimum': 1, 'maximum': 8, 'default': 4}
    },
    'additionalProperties': False
}
```

## Key Simplifications Made

1. **Single Algorithm**: Replaced multiple complex generation methods with one optimized approach
2. **Removed Classes**: Eliminated `PolygonGenerator` class in favor of simple function
3. **Consolidated Modules**: Combined functionality into `polygon_generator.py`
4. **Removed Complexity**: Eliminated iterative simplification and adaptive method selection
5. **Focused Approach**: Optimized specifically for LIDAR flightline data patterns
6. **Simplified Parameters**: Reduced configuration options to essential settings

This simplified integration maintains high performance while reducing code complexity and maintenance overhead. The single function approach makes integration straightforward and reliable.