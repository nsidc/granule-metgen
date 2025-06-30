# Spatial Polygon Generation Module

This module provides functionality for generating optimized spatial coverage polygons from point data, particularly for LVIS/ILVIS2 LIDAR flightline data.

## Module Structure

- `polygon_generator.py` - Core polygon generation algorithms
- `cmr_client.py` - CMR API integration and polygon comparison
- `simplification.py` - Iterative polygon simplification algorithm
- `polygon_driver.py` - Automated comparison workflow
- `polygon_cli.py` - Command-line interface wrapper

## Usage

### As a Python Module

```python
from nsidc.metgen.spatial import PolygonGenerator, CMRClient

# Generate a polygon
generator = PolygonGenerator()
polygon, metadata = generator.create_flightline_polygon(
    lon_array, lat_array,
    method='adaptive_beam',
    iterative_simplify=True,
    target_vertices=8
)

# Compare with CMR
client = CMRClient(token='your-bearer-token')
cmr_polygon = client.get_granule_polygon('concept-id')
```

### Command Line

```bash
# Run the polygon comparison driver
python -m nsidc.metgen.spatial.polygon_cli LVISF2 -n 10 --token-file ~/.edl_token

# Or use the standalone CLI
python polygon_cli.py ILVIS2 -n 5
```

## Key Features

- Multiple polygon generation methods (convex, concave, alpha shapes, beam methods)
- Adaptive buffer sizing based on data density
- Iterative simplification to match CMR polygon characteristics
- Comprehensive comparison metrics (IoU, area ratio, coverage)
- Automated workflow for batch processing

## Configuration

The module uses optimized default settings:
- Method: adaptive_beam
- Target vertices: 8
- Minimum IoU: 0.70
- Minimum coverage: 0.90

These can be overridden via function parameters or command-line arguments.

## Integration with MetGenC

This module can be integrated into MetGenC's configuration:

```ini
[spatial]
enabled = true
method = adaptive_beam
simplify = true
target_vertices = 8
```

Then use in MetGenC processing:

```python
from nsidc.metgen.spatial import PolygonGenerator

# In your reader or processor
if config.spatial.enabled:
    generator = PolygonGenerator()
    spatial_polygon = generator.create_flightline_polygon(
        data['longitude'], 
        data['latitude'],
        **config.spatial.params
    )
```