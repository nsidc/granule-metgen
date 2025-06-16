# Geometry Resolution Implementation

## Overview

This document describes the functional programming approach implemented for geometry resolution in the MetGenC pipeline. The implementation follows the geometry rules defined in the README.md and provides a clean, extensible solution for determining geometry sources and transforming them into UMM-G compliant formats.

## Architecture

### 1. Geometry Resolver Module (`src/nsidc/metgen/geometry_resolver.py`)

The geometry resolver implements a rule-based system using functional programming principles:

#### Key Components

- **`GeometryContext`**: An immutable dataclass containing all information needed for geometry resolution
  - GSR (Granule Spatial Representation)
  - Available geometry sources (spo file, spatial file, data file, collection)
  - Configuration flags (collection_geometry_override)
  - Point counts for validation

- **`GeometryDecision`**: The result of geometry resolution
  - Source to use (SPO_FILE, SPATIAL_FILE, DATA_FILE, COLLECTION, NONE)
  - Expected geometry type (POINT, BOUNDING_RECTANGLE, GPOLYGON)
  - Error message if the combination is invalid

- **Rule Functions**: Pure functions that evaluate a context and return a decision
  - Each rule handles one specific case from the README geometry table
  - Rules return `None` if they don't apply, allowing the next rule to be tried
  - Rules are ordered by priority (collection override → spo → spatial → data → collection fallback)

#### Example Rule

```python
def rule_spo_geodetic_valid(context: GeometryContext) -> Optional[GeometryDecision]:
    """Rule: .spo files with GEODETIC GSR and >2 points produce GPolygon."""
    if (context.has_spo_file and 
        context.gsr == GEODETIC and 
        context.point_count is not None and 
        context.point_count > 2):
        return GeometryDecision(
            source=GeometrySource.SPO_FILE,
            geometry_type=GeometryType.GPOLYGON
        )
    return None
```

### 2. Geometry Extractor Module (`src/nsidc/metgen/geometry_extractor.py`)

The geometry extractor handles the actual extraction and transformation of geometry data:

#### Key Functions

- **Source-specific extractors**:
  - `extract_spo_geometry()`: Reads and processes SPO files
  - `extract_spatial_geometry()`: Reads spatial files
  - `extract_data_file_geometry()`: Uses data readers to extract geometry
  - `extract_collection_geometry()`: Gets bounding rectangle from collection metadata

- **Transformation functions**:
  - `transform_to_point()`: Converts single point to UMM-G format
  - `transform_to_bounding_rectangle()`: Converts two points to bounding rectangle
  - `transform_to_gpolygon()`: Ensures polygon is closed and properly formatted

- **Main orchestrator**:
  - `extract_geometry()`: Delegates to appropriate extractor based on source
  - `transform_geometry()`: Applies appropriate transformation based on geometry type

### 3. Pipeline Integration

The geometry resolution is integrated into the processing pipeline through two operations:

#### `read_geometry()` Operation
1. Creates a `GeometryContext` from the granule and configuration
2. Reads spatial files to get point counts if needed
3. Applies the geometry rules to get a `GeometryDecision`
4. Stores the decision in the granule for later use

#### `write_geometry()` Operation
1. Uses the geometry decision from `read_geometry()`
2. Extracts geometry from the determined source
3. Validates the extracted geometry matches expectations
4. Transforms the geometry to UMM-G format
5. Stores the formatted geometry in the granule

#### `create_ummg()` Update
The UMM-G creation function now checks for geometry data from the pipeline:
- If `granule.geometry_data` exists, uses the pre-processed geometry
- Otherwise, falls back to the original geometry extraction logic

## Design Principles

### 1. Functional Programming
- **Immutable data structures**: `GeometryContext` and `GeometryDecision` are frozen dataclasses
- **Pure functions**: Rules don't modify state, they return new values
- **Function composition**: Complex behavior emerges from combining simple functions

### 2. Separation of Concerns
- **Resolution logic**: Determines *which* geometry source to use
- **Extraction logic**: Handles *how* to read geometry from each source
- **Transformation logic**: Converts geometry to UMM-G format

### 3. Extensibility
- New geometry rules can be added by creating a new rule function and adding it to `GEOMETRY_RULES`
- New geometry sources can be supported by adding extractors
- New geometry types can be added with corresponding transformers

### 4. Error Handling
- Invalid geometry combinations are detected early in the resolution phase
- Clear error messages indicate why a geometry configuration is invalid
- Validation ensures extracted geometry matches expected format

## Implementation Benefits

1. **Clarity**: The rules directly map to the README geometry table
2. **Testability**: Pure functions are easy to unit test
3. **Maintainability**: Each rule is self-contained and documented
4. **Debugging**: Clear decision trail shows why a particular geometry source was chosen
5. **Type Safety**: Enums and type hints prevent common errors

## Testing

Comprehensive test suites were created:

- `tests/test_geometry_resolver.py`: Tests all geometry resolution rules and edge cases
- `tests/test_geometry_extractor.py`: Tests geometry transformation functions

## Future Enhancements

1. **Point count determination**: Currently stubbed out, needs implementation to read actual files
2. **Complex polygon support**: Add convex hull calculation for irregular polygons
3. **Coordinate system transformation**: Handle reprojection between different CRS
4. **Performance optimization**: Add caching for repeated file reads
5. **Enhanced validation**: Check for self-intersecting polygons, valid coordinate ranges

## Usage Example

```python
# In the processing pipeline
granule = read_geometry(config, granule)  # Determines geometry source
granule = write_geometry(config, granule)  # Extracts and transforms geometry

# The geometry is now available as:
# granule.geometry_decision - The resolution decision
# granule.geometry_data - The formatted geometry ready for UMM-G
```

This implementation provides a solid foundation for geometry handling that aligns with the complex rules defined in the README while maintaining code clarity and extensibility.