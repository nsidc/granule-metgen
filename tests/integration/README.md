# MetGenC Integration Tests

This directory contains an automated integration testing system for MetGenC that replaces the manual testing process.

## Overview

The integration test system:
- **Downloads sample data** from NSIDC's staging server automatically
- **Uses pre-configured INI files** (no more manual .ini creation)
- **Runs metgenc** with real data to test end-to-end functionality
- **Validates outputs** to ensure CNM and UMM-G files are generated correctly
- **Cleans up automatically** (unless debugging)

## Quick Start

### Prerequisites
Set Earthdata Login credentials (required for collection metadata retrieval):
```bash
export EARTHDATA_USERNAME=your-EDL-username
export EARTHDATA_PASSWORD=your-EDL-password
```

Be sure to be on the NSIDC VPN or on an internal network before running unless you don't
require the integration tests to download data from the test data staging site.

### Commands
```bash
# Install dependencies (one time)
poetry install

# Run all integration tests
metgenc-integration-tests all

# Run a specific collection
metgenc-integration-tests snexduck

# Run with different environment
metgenc-integration-tests irtit3duck -e sit

# Keep files for debugging
metgenc-integration-tests modscg --keep-files -v

# Force re-download of sample data
metgenc-integration-tests snexduck --force-download
```

## Available Collections

- `IRTIT3DUCk` - NetCDF thermal imagery data
- `IRWIS2DUCk` - CSV weather station data
- `LVISF2` - LiDAR text files
- `NSIDC-0081DUCk` - Sea ice concentration NetCDF
- `NSIDC-0630DUCk` - Brightness temperature NetCDF
- `OLVIS1A_DUCk` - Optical imagery (JPEG with premet/spatial)
- `SNEX23_SSADUCk` - SnowEx CSV data

## Directory Structure

```
tests/integration/
├── run_integration_tests.py    # Main test runner
├── configs/                    # INI configuration files
│   ├── IRTIT3DUCk.ini
│   ├── SNEX23_SSADUCk.ini
│   └── ...
├── workspace/                  # Test data and outputs (gitignored)
│   ├── COLLECTION_NAME/
│   │   ├── data/              # Downloaded sample files
│   │   ├── output/            # Generated JSON files
│   │   └── COLLECTION.ini     # Test configuration
│   └── ...
└── README.md                   # This file
```

## How It Works

1. **Configuration**: Each collection has a pre-configured INI file in `configs/`
2. **Data Download**: Sample files are downloaded from `http://staging-http.apps.int.nsidc.org/staging/SAMPLE_DATA/DUCk_project/`
   - **Caching**: Files are only downloaded if they don't exist (use `--force-download` to override)
3. **Processing**: MetGenC runs using the downloaded data and collection config
4. **Validation**: Generated JSON files are validated for required fields and structure
5. **Cleanup**: Test files are removed (unless `--keep-files` is used)

## Test Output

The test runner provides:
- **Progress logging** showing download, processing, and validation steps
- **Detailed error messages** when tests fail
- **Summary report** showing pass/fail status for each collection
- **File counts** for generated CNM and UMM-G outputs

## Debugging Failed Tests

When a test fails:

1. **Check the workspace directory**: `tests/integration/workspace/COLLECTION_NAME/`
2. **Use `-v`** for verbose logging
3. **Examine generated files** in the `output/` subdirectory:
   - `output/cnm/` - CNM message files
   - `output/ummg/` - UMM-G metadata files
4. **Check the generated INI file** for configuration issues
5. **Use `--keep-files`** to prevent cleanup (though files persist by default now)
6. **Compare with expected output** from manual testing

**Pro tip**: The workspace directory persists between test runs, making it easy to inspect generated files and debug issues.

## Adding New Collections

To add a new collection:

1. Create an INI file in `configs/` following the existing patterns
2. Ensure sample data is available on the staging server
3. Test manually first to verify the configuration works
4. Run the integration test to validate

## Dependencies

- `requests` - For downloading sample data
- `beautifulsoup4` - For parsing directory listings
- `metgenc` - The main application (must be installed in environment)

## Notes

- Tests require network access to download sample data
- Some collections may have subdirectories (premet, spatial) that are handled automatically
- The system validates JSON structure but not complete schema compliance
- Test files are created in temporary directories by default
