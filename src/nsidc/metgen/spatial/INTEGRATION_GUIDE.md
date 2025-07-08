# Integration Guide for MetGenC Spatial Module

This guide explains how to integrate the spatial polygon generation module into the main MetGenC codebase.

## Overview

The spatial module has been simplified to use a single, optimized polygon generation approach that combines concave hull generation with intelligent buffering to achieve 98%+ data coverage with minimal vertices.

## 1. Configuration Integration ✅ COMPLETED

Add spatial polygon options to MetGenC's configuration schema:

### Configuration Changes Implemented:

1. **Added to `src/nsidc/metgen/constants.py`:**
```python
# Spatial polygon defaults
DEFAULT_SPATIAL_POLYGON_ENABLED = True
DEFAULT_SPATIAL_POLYGON_TARGET_COVERAGE = 0.98
DEFAULT_SPATIAL_POLYGON_MAX_VERTICES = 100
```

2. **Added to `src/nsidc/metgen/config.py` Config dataclass:**
```python
spatial_polygon_enabled: Optional[bool] = False
spatial_polygon_target_coverage: Optional[float] = None
spatial_polygon_max_vertices: Optional[int] = None
```

3. **Added validation rules in `config.py`:**
- `spatial_polygon_target_coverage` must be between 0.80 and 1.0
- `spatial_polygon_max_vertices` must be between 10 and 1000

### In configuration `.ini` files:

```ini
[Spatial]
spatial_polygon_enabled = true
spatial_polygon_target_coverage = 0.98
spatial_polygon_max_vertices = 100
```

Note: The section name is capitalized as `[Spatial]` to maintain consistency with other configuration sections like `[Source]`, `[Collection]`, etc. The default for `spatial_polygon_enabled` is `True`.

## 2. Spatial Processor Integration ✅ COMPLETED

The spatial polygon generation has been integrated directly into the UMM-G creation process by enhancing the existing `populate_spatial()` function.

### Implementation Details:

The integration has been implemented by enhancing the existing `populate_spatial()` function in `src/nsidc/metgen/metgen.py`:

#### Modified Function Signature:
```python
def populate_spatial(
    spatial_representation: str, 
    spatial_values: list, 
    configuration: config.Config = None, 
    spatial_content: list = None
) -> str:
```

#### Key Integration Logic:
- **Polygon generation is triggered only when**:
  - `configuration.spatial_polygon_enabled` is `True`
  - `spatial_content` is not `None` (indicating data came from `.spatial` file)
  - `spatial_representation` is `GEODETIC`
  - `len(spatial_values) >= 3` (minimum points for polygon)

- **Fallback behavior**: If any condition is not met or polygon generation fails, the function falls back to the original MetGenC spatial processing

#### Integration Point:
```python
# In create_ummg() function:
summary["spatial_extent"] = populate_spatial(gsr, summary["geometry"], configuration, spatial_content)
```

This approach ensures:
- ✅ Polygon generation only occurs for `.spatial` files
- ✅ Existing behavior preserved for all other cases
- ✅ No breaking changes to the API
- ✅ Graceful fallback on errors

### Current Status:
- ✅ **Configuration integration** completed
- ✅ **Spatial polygon generation** integrated into UMM-G creation
- ✅ **Conditional processing** ensures polygon generation only for `.spatial` files
- ✅ **Backward compatibility** maintained for existing workflows

## 3. CLI Integration ✅ COMPLETED

A standalone CLI tool has been created for polygon operations:

### Standalone CLI: `metgenc-polygons`

Created `src/nsidc/metgen/spatial_cli.py` with a dedicated CLI for spatial polygon operations:

#### Installation:
The CLI is automatically available after installing the package:
```bash
poetry install
# or
pip install nsidc-metgenc
```

#### Usage Examples:
```bash
# Show available commands
metgenc-polygons --help

# Compare 10 random LVISF2 granules with CMR
metgenc-polygons compare LVISF2 -n 10 --provider NSIDC_CPRD

# Compare specific granule with authentication
metgenc-polygons compare LVISF2 --granule "GRANULE_NAME" --token-file ~/.edl_token

# Use custom output directory
metgenc-polygons compare ILVIS2 -n 20 -o /tmp/polygon_analysis

# Validate a polygon file
metgenc-polygons validate my_polygon.geojson --check-coverage --points-file points.csv

# Show tool information
metgenc-polygons info
```

#### Available Commands:
- **`compare`**: Compare generated polygons with CMR polygons for collections
- **`validate`**: Validate polygon files and check data coverage
- **`info`**: Display tool information and usage

#### Benefits of Standalone CLI:
- ✅ **Separation of concerns**: Polygon tools are separate from main MetGenC workflow
- ✅ **Clean interface**: No cluttering of main `metgenc` command
- ✅ **Focused functionality**: All polygon-related operations in one place
- ✅ **Easy to discover**: `metgenc-polygons --help` shows all polygon operations

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
[Spatial]
spatial_polygon_enabled = true
spatial_polygon_target_coverage = 0.98
spatial_polygon_max_vertices = 100
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

## Configuration Schema Integration ✅ COMPLETED

The spatial configuration has been fully integrated into MetGenC's configuration system:

```python
# Configuration fields in Config dataclass:
spatial_polygon_enabled: Optional[bool] = False  # Default handled via constants
spatial_polygon_target_coverage: Optional[float] = None  # Default: 0.98
spatial_polygon_max_vertices: Optional[int] = None  # Default: 100

# Constants defined in constants.py:
DEFAULT_SPATIAL_POLYGON_ENABLED = True
DEFAULT_SPATIAL_POLYGON_TARGET_COVERAGE = 0.98
DEFAULT_SPATIAL_POLYGON_MAX_VERTICES = 100

# Validation rules:
- spatial_polygon_target_coverage: 0.80 <= value <= 1.0
- spatial_polygon_max_vertices: 10 <= value <= 1000
```

The configuration follows MetGenC's existing patterns:
- Uses capitalized section name `[Spatial]`
- Defaults are defined in constants.py
- Config dataclass uses None/False for optional fields
- Validation is performed in the validate() function
- Full test coverage for all configuration scenarios

## Key Simplifications Made

1. **Single Algorithm**: Replaced multiple complex generation methods with one optimized approach
2. **Removed Classes**: Eliminated `PolygonGenerator` class in favor of simple function
3. **Consolidated Modules**: Combined functionality into `polygon_generator.py`
4. **Removed Complexity**: Eliminated iterative simplification and adaptive method selection
5. **Focused Approach**: Optimized specifically for LIDAR flightline data patterns
6. **Simplified Parameters**: Reduced configuration options to essential settings

This simplified integration maintains high performance while reducing code complexity and maintenance overhead. The single function approach makes integration straightforward and reliable.