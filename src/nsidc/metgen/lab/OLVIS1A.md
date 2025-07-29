# OLVIS1A Processor

This script downloads OLVIS1A granules sequentially and generates premet and spatial files for them.

## Usage

```bash
# Set authentication credentials (required for downloading data)
export EARTHDATA_USERNAME=your-username
export EARTHDATA_PASSWORD=your-password

# Basic usage - process 5 granules
metgenc-lab-olvis1a

# Process a specific number of granules
metgenc-lab-olvis1a -n 10

# Specify output directory
metgenc-lab-olvis1a -o my_output_dir

# Combine options
metgenc-lab-olvis1a -n 10 -o my_output
```

## Authentication

The processor uses Earthdata Login username and password authentication:
- Set environment variables:
  - `export EARTHDATA_USERNAME=your-username`
  - `export EARTHDATA_PASSWORD=your-password`

## Configuration

The following values are hardcoded constants:
- Environment: `prod` (https://cmr.earthdata.nasa.gov)
- Collection: `OLVIS1A`
- Version: `1`
- Provider: `NSIDC_ECS`

## Output Structure

The script creates the following directory structure:

```
olvis1a_output/
├── data/          # Downloaded granule data files (JPG images)
├── premet/        # Generated premet files (.premet)
└── spatial/       # Generated spatial files (.spatial)
```

## File Formats

### Premet Files
Contains metadata in key-value format:
- Data filename
- Version ID (001)
- Begin/end dates and times
- Collection short name (OLVIS1A)
- Processing level (1A)
- Platform/instrument information

### Spatial Files
Contains longitude/latitude coordinate pairs extracted from UMM-G metadata:
- One coordinate pair per line
- Space-separated values
- 6 decimal places precision
- Coordinates come from GPolygons, BoundingRectangles, or Points in the metadata

## Granule Selection

The processor retrieves granules sequentially from CMR:
- Orders by start date (most recent first)
- Retrieves the requested number of granules
- No random sampling - always gets the same granules in the same order

## Requirements

- Earthdata Login credentials (username and password) for downloading data
- Network access to NASA CMR and data repositories
