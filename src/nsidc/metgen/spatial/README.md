# Spatial Polygon Generation Module

This module provides optimized spatial coverage polygon generation from point data, specifically designed for LIDAR flightline data such as LVIS/ILVIS2 collections.

## Core Function

The primary function `create_flightline_polygon(lon, lat)` generates optimized polygons using a single, reliable algorithm that:

1. **Concave Hull Generation** - Creates initial polygon using adaptive thresholds
2. **Intelligent Buffering** - Enhances coverage through strategic buffering when needed
3. **Antimeridian Handling** - Properly handles global datasets crossing ±180°
4. **Automatic Optimization** - Maintains high coverage (98%+) with minimal vertices

## Why This Implementation

The module uses a **single optimized approach** rather than multiple algorithms because:
- **Reliability**: One well-tested method reduces complexity and edge cases
- **Performance**: Achieves 98%+ data coverage with typically 30-70 vertices
- **Efficiency**: Handles large datasets (350k+ points) through intelligent subsampling
- **Simplicity**: Eliminates configuration complexity while maintaining quality

## Usage

```python
from nsidc.metgen.spatial import create_flightline_polygon

# Generate optimized polygon
polygon, metadata = create_flightline_polygon(lon_array, lat_array)

# Returns:
# - polygon: Shapely Polygon object
# - metadata: Dict with coverage, vertices, generation time, method used
```

## Module Components

- **`polygon_generator.py`** - Core polygon generation function
- **`cmr_client.py`** - CMR API integration (used by comparison tool in lab package)

**Note**: The polygon comparison diagnostic tool (`metgenc-lab-polygons`) and its associated components (`polygon_driver.py`, `spatial_cli.py`, `spatial_utils.py`) are located in the lab package as experimental features. See the [lab documentation](../lab/POLYGON_COMPARISON.md) for details.

## Algorithm Behavior

### Data Preprocessing
- Applies boundary-preserving subsampling for datasets >8000 points
- Detects antimeridian crossings automatically
- Uses conservative parameters for small datasets (<100 points)

### Coverage Enhancement
- Calculates initial data coverage using point-in-polygon tests
- Applies strategic buffering only if coverage < 98%
- Uses area ratio constraints to prevent over-buffering
- Ensures polygon validity and proper coordinate normalization

## Integration with MetGenC

The module integrates seamlessly with MetGenC's spatial processing through the
existing `populate_spatial()` function. When spatial polygon generation is
enabled and `.spatial` files are present, the optimized polygon generation
automatically replaces the basic point-to-point method.

## Dependencies

**Core**: `shapely`, `numpy`, `concave-hull`
