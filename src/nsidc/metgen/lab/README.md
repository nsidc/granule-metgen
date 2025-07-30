# MetGenC Lab - Experimental Features

This package contains experimental features and tools that are under development or evaluation for potential inclusion in the main MetGenC workflow. These tools are functional but may undergo significant changes.

## Available Experimental Tools

### 1. OLVIS1A Processor
**Command**: `metgenc-lab-olvis1a`

A specialized processor for OLVIS1A (Operation IceBridge LVIS L1A Geolocated Return Energy Waveforms) granules that:
- Downloads granules from NASA CMR
- Generates premet files with temporal and collection metadata
- Creates spatial files with coordinate information

See [OLVIS1A.md](OLVIS1A.md) for detailed documentation.

### 2. Polygon Comparison Tool
**Command**: `metgenc-lab-polygons`

A diagnostic tool for comparing MetGenC-generated polygons with CMR reference polygons:
- Analyzes polygon generation quality and data coverage
- Provides visual comparisons and metrics
- Helps validate and tune polygon generation parameters

See [POLYGON_COMPARISON.md](POLYGON_COMPARISON.md) for detailed documentation.

## Usage Notes

These tools are provided as-is for experimentation and testing. They may:
- Have different authentication requirements
- Use different dependencies than the main MetGenC package
- Change significantly between releases
- Eventually be promoted to the main package or removed

## Contributing

When adding new experimental features to the lab:
1. Create a dedicated module file
2. Add appropriate CLI command in the main CLI
3. Document the feature in a separate markdown file
4. Update this README with a brief description