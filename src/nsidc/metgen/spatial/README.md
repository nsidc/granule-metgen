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

# Generate a polygon - algorithm automatically selects optimal method
generator = PolygonGenerator()
polygon, metadata = generator.create_flightline_polygon(lon_array, lat_array)

# The algorithm automatically:
# - Analyzes data characteristics (density, linearity, spacing)
# - Selects the optimal generation method
# - Determines appropriate parameters (buffer size, target vertices)
# - Generates and optimizes the polygon
# - Ensures high data coverage with minimal non-data area

# Metadata includes:
# - method: Selected generation method
# - points: Number of input points  
# - vertices: Final vertex count
# - data_coverage: Percentage of data covered
# - generation_time_seconds: Total processing time
# - data_analysis: Characteristics that drove method selection

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

- **Automatic method selection** - Analyzes data characteristics to choose optimal approach
- **Multiple polygon generation methods** - beam sampling, union buffer, line buffer
- **Adaptive parameter tuning** - Buffer sizes, vertex targets, and coverage thresholds automatically determined
- **Iterative simplification** - Reduces vertices while maintaining data coverage
- **Comprehensive metrics** - Data coverage, area ratio, non-data area, processing time
- **Parallel processing** - Batch process multiple granules efficiently

## How It Works

The algorithm follows these steps:

1. **Data Analysis** - Examines point density, spatial distribution, linearity, and spacing regularity
2. **Method Selection** - Chooses between:
   - `union_buffer` - For sparse or highly irregular data
   - `line_buffer` - For linear, regular flightlines
   - `beam` methods - For moderate cases
3. **Parameter Optimization** - Determines buffer sizes and target vertices based on data characteristics
4. **Polygon Generation** - Creates initial polygon using selected method
5. **Iterative Simplification** - Reduces vertices while maintaining coverage requirements

## Integration with MetGenC

This module can be integrated into MetGenC's configuration:

```ini
[spatial]
enabled = true
```

Then use in MetGenC processing:

```python
from nsidc.metgen.spatial import PolygonGenerator

# In your reader or processor
if config.spatial.enabled:
    generator = PolygonGenerator()
    spatial_polygon, metadata = generator.create_flightline_polygon(
        data['longitude'], 
        data['latitude']
    )
    
    # Log the results
    print(f"Generated {metadata['vertices']} vertex polygon using {metadata['method']} method")
    print(f"Data coverage: {metadata.get('data_coverage', 'N/A')}")
```