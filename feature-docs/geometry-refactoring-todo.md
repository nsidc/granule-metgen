# Geometry Refactoring TODO

## Current State

The new geometry pipeline (geometry_resolver.py and geometry_extractor.py) has been implemented but the codebase is in a transitional state with both old and new approaches coexisting.

## Code That Should Be Retained

### 1. Geometry Formatting Functions (metgen.py)
These functions format geometry for UMM-G output and are still needed:
- `populate_spatial()` - Main dispatcher for geometry formatting
- `populate_bounding_rectangle()` - Formats bounding rectangles
- `populate_point_or_polygon()` - Formats points and polygons

### 2. Data Reader Geometry Extraction
- NetCDF reader's geometry interpolation code for extracting geometry from data files
- This is referenced but not replaced by the new pipeline

## Code in Transition

### 1. Utility Functions (utilities.py)
Currently, the new `geometry_extractor.py` wraps these functions rather than replacing them:

| Function | Current Usage | Recommendation |
|----------|---------------|----------------|
| `external_spatial_values()` | - Used as fallback in metgen.py<br>- Determines geometry source | Should be removed once pipeline is fully integrated |
| `points_from_spatial()` | Used by geometry_extractor.py | Move implementation into geometry_extractor.py |
| `parse_spo()` | Used by geometry_extractor.py | Move implementation into geometry_extractor.py |
| `raw_points()` | Used by parse_spo and points_from_spatial | Move as private function in geometry_extractor.py |
| `closed_polygon()` | Used by parse_spo | Move as private function in geometry_extractor.py |
| `points_from_collection()` | Used by external_spatial_values | Move implementation into geometry_extractor.py |
| `valid_spatial_config()` | Validates spatial configurations | Replace with geometry_resolver validation |

### 2. Test Files
- `tests/test_utilities.py` - Contains tests for the above utility functions
- These tests should be migrated to test the new geometry pipeline instead

## Refactoring Steps

### Phase 1: Complete the New Pipeline Implementation
1. **Update geometry_extractor.py** to include the actual implementations instead of calling utilities.py:
   ```python
   # Instead of:
   points = utilities.parse_spo(filepath)
   
   # Implement directly:
   def extract_spo_geometry(filepath: Path) -> Tuple[GeometryPoints, int]:
       # Move parse_spo implementation here
       # Including raw_points and closed_polygon logic
   ```

2. **Remove the fallback in create_ummg()**:
   ```python
   # Remove this fallback:
   else:
       # Fall back to the old method
       spatial_content = utilities.external_spatial_values(...)
   ```

### Phase 2: Update Tests
1. **Create comprehensive tests** for the integrated pipeline in test_metgen.py
2. **Migrate test cases** from test_utilities.py to test the new modules
3. **Remove obsolete tests** once the old functions are no longer used

### Phase 3: Clean Up
1. **Remove obsolete functions** from utilities.py
2. **Update imports** throughout the codebase
3. **Update documentation** to reflect the new geometry pipeline

## Testing Strategy

Before removing old code, ensure:
1. All existing tests pass with the new pipeline
2. Integration tests cover all geometry source combinations from the README
3. Performance is comparable or better than the old implementation

## Benefits of Completion

1. **Single source of truth** for geometry logic
2. **Clearer separation of concerns** between resolution and extraction
3. **Easier to maintain** with functional approach
4. **Better testability** with pure functions
5. **Improved error handling** with explicit geometry decisions

## Risk Mitigation

1. Keep the old code during transition
2. Use feature flags if needed to switch between implementations
3. Run both old and new code in parallel during testing phase
4. Ensure comprehensive test coverage before removing old code

## Current Integration Points

The new geometry pipeline is integrated at these points:
- `read_geometry()` - Determines geometry source (new)
- `write_geometry()` - Extracts and transforms geometry (new)
- `create_ummg()` - Uses geometry_data if available, falls back to old method
- `populate_spatial()` and related - Still used for final formatting

## Next Steps

1. **Immediate**: Test the new pipeline with real data
2. **Short term**: Move utility function implementations into geometry_extractor.py
3. **Medium term**: Remove fallback logic and old geometry functions
4. **Long term**: Full integration with enhanced validation and error handling