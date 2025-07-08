# Spatial Polygon Generation Module

This module provides optimized spatial coverage polygon generation from point data, specifically designed for LVIS/ILVIS2 LIDAR flightline data.

## Module Structure

- `polygon_generator.py` - Single optimized polygon generation algorithm
- `cmr_client.py` - CMR API integration and polygon comparison
- `polygon_driver.py` - Automated comparison workflow

## Algorithm Overview

The module uses a single, optimized approach that combines:
1. **Concave Hull Generation** - Creates initial polygon using the concave_hull library
2. **Intelligent Buffering** - Enhances coverage through strategic buffering
3. **Vertex Optimization** - Maintains manageable vertex counts through simplification
4. **Antimeridian Handling** - Properly handles global datasets crossing ±180°

## Usage

### As a Python Module

```python
from nsidc.metgen.spatial import create_flightline_polygon

# Generate optimized polygon
polygon, metadata = create_flightline_polygon(lon_array, lat_array)

# The algorithm automatically:
# - Analyzes data density and applies intelligent subsampling if needed
# - Generates concave hull with optimized length threshold
# - Applies buffering if coverage < 98%
# - Handles antimeridian crossing for global datasets
# - Returns valid, simplified polygon

# Metadata includes:
# - method: Generation method used ('concave_hull', 'convex_hull_fallback', etc.)
# - vertices: Final vertex count
# - final_data_coverage: Percentage of data points covered
# - generation_time_seconds: Processing time
# - data_points: Number of input points
# - subsampling_used: Whether subsampling was applied
```

### Command Line

```bash
# Run polygon comparison for a collection
python -m nsidc.metgen.spatial.polygon_driver LVISF2 -n 10 --token-file ~/.edl/token.prod

# With parallel processing
python -m nsidc.metgen.spatial.polygon_driver ILVIS2 -n 5 -w 2 -p NSIDC_CPRD
```

## Key Features

- **Single Optimized Algorithm** - One reliable approach that works well for LIDAR data
- **High Data Coverage** - Achieves 98%+ coverage of input data points
- **Minimal Vertices** - Typically 30-70 vertices (vs 39 average previously)
- **Antimeridian Support** - Handles global datasets crossing the dateline
- **Intelligent Subsampling** - Processes large datasets (350k+ points) efficiently
- **CMR Validation** - Compare results with existing CMR polygons
- **Parallel Processing** - Batch process multiple granules efficiently

## Performance Characteristics

Based on testing with LVIS collections:

| Collection | Avg Coverage | Avg Vertices | Avg Area Ratio |
|------------|--------------|--------------|----------------|
| LVISF2     | 98.6%        | 52           | 1.2x           |
| IPFLT1B    | 98.1%        | 46           | 2.9x           |

## Algorithm Details

### 1. Data Preprocessing
- Handles datasets up to 350k points
- Applies boundary-preserving subsampling for large datasets
- Detects and handles antimeridian crossings

### 2. Concave Hull Generation
- Uses adaptive length threshold: `avg_range * 0.015`
- Fallback to convex hull if concave hull fails
- Applies basic simplification to reduce vertex count

### 3. Coverage Enhancement
- Calculates data coverage using point-in-polygon tests
- Applies strategic buffering if coverage < 98%
- Uses area ratio constraints to prevent over-buffering
- Smooths buffered polygons to reduce vertex count

### 4. Validation
- Ensures polygon validity using Shapely
- Normalizes coordinates to [-180, 180] range
- Returns comprehensive metadata for analysis

## Integration with MetGenC

```python
# In MetGenC readers
from nsidc.metgen.spatial import create_flightline_polygon

def get_spatial_extent(self, filename):
    if self.config.get('spatial', {}).get('enabled', False):
        # Extract coordinates
        lon = self.dataset.variables['longitude'][:]
        lat = self.dataset.variables['latitude'][:]
        
        # Generate polygon
        polygon, metadata = create_flightline_polygon(lon, lat)
        
        # Convert to UMM-G format
        return convert_polygon_to_ummg(polygon)
```

## Testing

```python
import numpy as np
from nsidc.metgen.spatial import create_flightline_polygon

# Test basic generation
lon = np.array([-120, -119.5, -119, -118.5])
lat = np.array([35, 35.1, 35.2, 35.3])

polygon, metadata = create_flightline_polygon(lon, lat)

assert polygon is not None
assert metadata['vertices'] >= 3
assert metadata['final_data_coverage'] >= 0.90
```

## Dependencies

- `shapely` - Polygon operations and validation
- `numpy` - Numerical operations
- `concave-hull` - Concave hull algorithm
- `geopandas` - GeoDataFrame operations (driver only)
- `matplotlib` - Visualization (driver only)
- `requests` - CMR API calls (driver only)

## Key Simplifications Made

1. **Single Algorithm**: Replaced multiple complex generation methods with one optimized approach
2. **Removed Classes**: Eliminated `PolygonGenerator` class in favor of simple function
3. **Consolidated Modules**: Removed `simplification.py`, integrated functionality into main module
4. **Focused Approach**: Optimized specifically for LIDAR flightline data patterns
5. **Simplified Parameters**: Reduced configuration complexity while maintaining performance

This simplified approach maintains high performance (98%+ coverage, manageable vertex counts) while significantly reducing code complexity and maintenance overhead.