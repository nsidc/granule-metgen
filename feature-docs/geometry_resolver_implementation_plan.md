# Geometry Resolver Implementation Plan

This document outlines the steps to implement the geometry determination logic for UMM-G metadata generation in MetGenC.

## Phase 1: Setup and Basic Data Structures

The goal of this phase is to lay the groundwork by defining the necessary data structures and the skeleton of our resolver.

*   **Step 1.1: Create `geometry_resolver.py` and Core Enums/Error**
    *   **Action**:
        *   Create a new file: `/Users/kwb/projects/granule-metgen/metgen/geometry_resolver.py`.
        *   Define `GeometrySourceType(Enum)`, `GranuleSpatialRepresentation(Enum)`, and `GeometryResolutionError(ValueError)` in this file.
    *   **Unit Tests (e.g., in `tests/unit/test_geometry_resolver.py`)**:
        *   Test that `geometry_resolver.py` can be imported.
        *   Test that enums have the expected members (e.g., `GranuleSpatialRepresentation.GEODETIC`).
        *   Test that `GeometryResolutionError` can be raised and caught.

*   **Step 1.2: Define UMM-G Output Dataclasses**
    *   **Action**: In `metgen/geometry_resolver.py`, define the dataclasses for UMM-G geometry:
        *   `UMMGPoint`
        *   `UMMGBoundingRectangle`
        *   `UMMGPolygonPoint`
        *   `UMMGPolygonBoundary`
        *   `UMMGPolygon`
        *   `UMMGHorizontalSpatialDomainGeometry = Union[UMMGPoint, UMMGBoundingRectangle, UMMGPolygon]`
        *   Implement a `to_dict()` method for each of these that produces the UMM-G JSON structure.
    *   **Unit Tests**:
        *   For each dataclass:
            *   Test successful instantiation.
            *   Test that `to_dict()` produces the correct dictionary structure and values.

*   **Step 1.3: Define Input Dataclasses (Initial Shells)**
    *   **Action**: In `metgen/geometry_resolver.py`, define basic shells for input data:
        *   `SpoData` (e.g., `points: Optional[List[Tuple[float, float]]] = None`)
        *   `SpatialFileData` (e.g., `points: Optional[List[Tuple[float, float]]] = None`)
        *   `DataFileGeometry` (e.g., `is_netcdf: bool = False`, `bounding_box: Optional[Tuple[float, float, float, float]] = None`, `points: Optional[List[Tuple[float, float]]] = None`)
        *   `CollectionMetadataGeometry` (e.g., `bounding_rectangles: Optional[List[Tuple[float, float, float, float]]] = None`)
        *   `GranuleGeometryInputs` dataclass to hold instances of the above, plus `granule_spatial_representation: GranuleSpatialRepresentation` and `collection_geometry_override_flag: bool`.
    *   **Unit Tests**:
        *   Test instantiation of `GranuleGeometryInputs` with various combinations of `None` and minimal data for its members.

*   **Step 1.4: Skeleton `resolve_ummg_geometry` Function**
    *   **Action**: In `metgen/geometry_resolver.py`, create the main function:
        ```python
        def resolve_ummg_geometry(inputs: GranuleGeometryInputs) -> UMMGHorizontalSpatialDomainGeometry:
            # Initially, we can make it very simple
            raise NotImplementedError("Geometry resolution logic not yet fully implemented.")
        ```
    *   **Unit Tests**:
        *   Write a test that calls `resolve_ummg_geometry` with dummy `GranuleGeometryInputs` and asserts that `NotImplementedError` (or `GeometryResolutionError` if you prefer to start with that) is raised.

---

## Phase 2: Implement Geometry Rules Incrementally

We'll go rule by rule (or by groups of related rules) from the `README.md` table, implementing the logic in `resolve_ummg_geometry` and adding specific tests for each.

*   **Step 2.1: Implement "Collection Geometry Override" Rule**
    *   **Action**:
        *   Modify `resolve_ummg_geometry` to handle the `collection_geometry_override_flag`.
        *   If `True`, check `inputs.collection_metadata_geometry` and `inputs.granule_spatial_representation`.
        *   Implement logic for:
            *   Cartesian GSR + 1 Collection BR -> `UMMGBoundingRectangle`.
            *   Cartesian GSR + >=2 Collection BRs -> `GeometryResolutionError`.
            *   Geodetic GSR + Collection BRs -> `GeometryResolutionError`.
            *   No suitable collection geometry -> `GeometryResolutionError`.
    *   **Unit Tests**:
        *   Test case: Override `True`, Cartesian GSR, 1 Collection BR (e.g., `[[10.0, 20.0, 30.0, 40.0]]`) -> verify correct `UMMGBoundingRectangle`.
        *   Test case: Override `True`, Cartesian GSR, 2 Collection BRs -> verify `GeometryResolutionError`.
        *   Test case: Override `True`, Geodetic GSR, 1 Collection BR -> verify `GeometryResolutionError`.
        *   Test case: Override `True`, `collection_metadata_geometry` is `None` or has no `bounding_rectangles` -> verify `GeometryResolutionError`.
        *   Test case: Override `False` -> (for now) verify it falls through (e.g., still raises `NotImplementedError` or a specific error if no other rules are met).

*   **Step 2.2: Implement ".spo" File Rules**
    *   **Action**:
        *   Flesh out `SpoData` if needed (e.g., ensure `points` attribute is `List[Tuple[float, float]]`).
        *   In `resolve_ummg_geometry` (after the override check if `False`):
            *   If `inputs.spo_data` is present:
                *   Cartesian GSR -> `GeometryResolutionError`.
                *   Geodetic GSR, <= 2 points -> `GeometryResolutionError`.
                *   Geodetic GSR, > 2 points -> `UMMGPolygon`. (Ensure polygon closure: first and last points are identical).
    *   **Unit Tests**:
        *   Test case: SPO data present, Cartesian GSR -> `GeometryResolutionError`.
        *   Test case: SPO data present (1 point), Geodetic GSR -> `GeometryResolutionError`.
        *   Test case: SPO data present (2 points), Geodetic GSR -> `GeometryResolutionError`.
        *   Test case: SPO data present (3 points, e.g., `[(0,0), (1,1), (0,1)]`), Geodetic GSR -> verify correct `UMMGPolygon` (ensure `[(0,0), (1,1), (0,1), (0,0)]` points).
        *   Test case: SPO data present (4 points already closed), Geodetic GSR -> verify correct `UMMGPolygon`.

*   **Step 2.3: Implement ".spatial" File Rules**
    *   **Action**:
        *   Flesh out `SpatialFileData` if needed.
        *   In `resolve_ummg_geometry` (after SPO check if no SPO data):
            *   If `inputs.spatial_file_data` is present:
                *   **Geodetic GSR**:
                    *   1 point -> `UMMGPoint`.
                    *   `>= 2` points -> `UMMGPolygon` (calculated to enclose all points; for now, assume points form a sequence, ensure closure).
                *   **Cartesian GSR**:
                    *   1 point -> `GeometryResolutionError` (per table, considering Note 4 later).
                    *   2 points -> `UMMGBoundingRectangle` (define how 2 Cartesian points form a BR, e.g., points are `(W,S)` and `(E,N)` or min/max of coordinates. Assume WGS84 for now).
                    *   `> 2` points -> `GeometryResolutionError`.
    *   **Unit Tests**:
        *   Spatial data, Geodetic GSR, 1 point `(10,20)` -> `UMMGPoint(Longitude=10, Latitude=20)`.
        *   Spatial data, Geodetic GSR, 3 points -> `UMMGPolygon`.
        *   Spatial data, Cartesian GSR, 1 point -> `GeometryResolutionError`.
        *   Spatial data, Cartesian GSR, 2 points `[(0,0), (10,10)]` -> `UMMGBoundingRectangle(W=0,S=0,E=10,N=10)`. (Adjust based on how you define the 2 points).
        *   Spatial data, Cartesian GSR, 3 points -> `GeometryResolutionError`.

*   **Step 2.4: Implement "Data File" Rules (NetCDF)**
    *   **Action**:
        *   Flesh out `DataFileGeometry` (e.g., `is_netcdf: bool`, `bounding_box: Optional[Tuple[float,float,float,float]]`, `points: Optional[List[Tuple[float,float]]]`).
        *   In `resolve_ummg_geometry` (after spatial check if no spatial data):
            *   If `inputs.data_file_geometry` is present and `is_netcdf` is `True`:
                *   **Cartesian GSR**:
                    *   Requires `bounding_box` in `DataFileGeometry` -> `UMMGBoundingRectangle`.
                    *   No `bounding_box` -> `GeometryResolutionError`.
                *   **Geodetic GSR**:
                    *   1 point in `DataFileGeometry.points` -> `UMMGPoint`.
                    *   `>= 2` points (for gridded perimeter or collection) -> `UMMGPolygon` (ensure closure).
                    *   Otherwise (e.g., 0 points, or not enough for polygon) -> `GeometryResolutionError`.
    *   **Unit Tests**:
        *   Data file (NetCDF), Cartesian GSR, `bounding_box=(0,0,10,10)` -> `UMMGBoundingRectangle`.
        *   Data file (NetCDF), Cartesian GSR, no `bounding_box` -> `GeometryResolutionError`.
        *   Data file (NetCDF), Geodetic GSR, 1 point `(10,20)` -> `UMMGPoint`.
        *   Data file (NetCDF), Geodetic GSR, 3 points -> `UMMGPolygon`.
        *   Data file (NetCDF), Geodetic GSR, 0 points -> `GeometryResolutionError`.

*   **Step 2.5: Implement "Data File" Rules (Non-NetCDF)**
    *   **Action**:
        *   In `resolve_ummg_geometry`:
            *   If `inputs.data_file_geometry` is present and `is_netcdf` is `False`:
                *   Cartesian GSR (any number of points) -> `GeometryResolutionError`.
                *   **Geodetic GSR**:
                    *   1 point -> `UMMGPoint`.
                    *   `>= 2` points -> `UMMGPolygon`.
                    *   Otherwise -> `GeometryResolutionError`.
    *   **Unit Tests**:
        *   Data file (Non-NetCDF), Cartesian GSR, 2 points -> `GeometryResolutionError`.
        *   Data file (Non-NetCDF), Geodetic GSR, 1 point `(10,20)` -> `UMMGPoint`.
        *   Data file (Non-NetCDF), Geodetic GSR, 3 points -> `UMMGPolygon`.

*   **Step 2.6: Implement "Collection Metadata" as Fallback Source Rules**
    *   **Action**:
        *   In `resolve_ummg_geometry` (after data file check if no geometry from data file):
            *   If `inputs.collection_metadata_geometry` and its `bounding_rectangles` are present:
                *   **Cartesian GSR**:
                    *   1 BR -> `UMMGBoundingRectangle`.
                    *   `>= 2` BRs -> `GeometryResolutionError`.
                *   **Geodetic GSR** -> `GeometryResolutionError`.
    *   **Unit Tests**:
        *   No prior geom, Collection BR `[[0,0,10,10]]`, Cartesian GSR -> `UMMGBoundingRectangle`.
        *   No prior geom, Collection BRs `[[0,0,10,10], [1,1,11,11]]`, Cartesian GSR -> `GeometryResolutionError`.
        *   No prior geom, Collection BR `[[0,0,10,10]]`, Geodetic GSR -> `GeometryResolutionError`.

*   **Step 2.7: Final Fallback and Default Error**
    *   **Action**:
        *   Ensure that if no rules are matched (e.g., `collection_geometry_override` is `False`, and no `.spo`, `.spatial`, `data_file`, or fallback `collection_metadata` geometry is applicable/valid), the function raises a clear `GeometryResolutionError` (e.g., "Unable to determine granule geometry: No applicable rule matched or no source provided valid geometry.").
        *   Replace the initial `NotImplementedError` with this more specific error if it's still the fall-through.
    *   **Unit Tests**:
        *   Test case: `GranuleGeometryInputs` with all geometry sources as `None` (and override `False`) -> verify the specific "Unable to determine" `GeometryResolutionError`.

---

## Phase 3: Integration and Helper Function Implementation

This phase focuses on connecting the resolver to your pipeline and implementing the actual data extraction.

*   **Step 3.1: Create Placeholder Parsing/Extraction Functions**
    *   **Action**: In your `metgen` module (wherever parsing happens, or create new helper files), define stub functions like:
        *   `def parse_spo_file(file_path: str) -> Optional[SpoData]: return None`
        *   `def parse_spatial_file(file_path: str) -> Optional[SpatialFileData]: return None`
        *   `def extract_geometry_from_data_file(granule_data_content: Any, is_netcdf: bool) -> Optional[DataFileGeometry]: return None`
        *   `def extract_geometry_from_collection_metadata(collection_meta: dict) -> Optional[CollectionMetadataGeometry]: return None`
        *   `def determine_granule_spatial_representation(collection_meta: dict, granule_specific_info: Any) -> GranuleSpatialRepresentation: return GranuleSpatialRepresentation.GEODETIC # or some default`
    *   **Tests**: No direct unit tests for these stubs, but they are prerequisites for the next step.

*   **Step 3.2: Integrate `resolve_ummg_geometry` into the Processing Pipeline**
    *   **Action**:
        *   In your main granule processing logic in `metgen`:
            1.  Call your new stub functions to gather/prepare data for `GranuleGeometryInputs`.
            2.  Call `determine_granule_spatial_representation`.
            3.  Read `collection_geometry_override` from config.
            4.  Instantiate `GranuleGeometryInputs`.
            5.  Call `resolve_ummg_geometry(geometry_inputs)`.
            6.  Wrap the call in a `try...except GeometryResolutionError as e:` block. Log errors.
            7.  If successful, take the returned UMM-G geometry object, call its `to_dict()` method, and integrate this dictionary into the UMM-G record being built for the granule (e.g., under `HorizontalSpatialDomain.Geometry`).
    *   **Integration Tests**:
        *   Run your `metgenc process` (perhaps with a dry-run or limited number of granules) with different configurations/input files that would trigger various paths in `resolve_ummg_geometry` (even if they result in errors due to stubbed parsers).
        *   Verify that the resolver is called, errors are logged, and (if a rule could be met with `None` inputs) that the UMM-G output (or a log of it) reflects an attempt to set geometry.

*   **Step 3.3: Implement Actual Parsing/Extraction Functions (Iteratively)**
    *   **Action**: One by one, replace the stub functions from Step 3.1 with real implementations.
        *   For each function (e.g., `parse_spo_file`):
            *   Implement the logic to read the file/data.
            *   Extract relevant points or attributes.
            *   **Crucially, if coordinates are not WGS84, implement reprojection here.**
            *   Populate and return the corresponding data class (`SpoData`, `SpatialFileData`, etc.).
    *   **Unit Tests (for each parsing/extraction function)**:
        *   Mock file I/O or input data.
        *   Test correct parsing of different file contents/data structures.
        *   Test correct population of the output dataclass.
        *   Test handling of missing files or malformed data (e.g., returning `None` or raising an appropriate error).
        *   If reprojection is involved, test it with sample coordinates.

---

## Phase 4: Refinements and Advanced Considerations

*   **Step 4.1: Thorough Review of Coordinate Systems and Reprojection**
    *   **Action**: Double-check all points where coordinates are read (`.spo`, `.spatial`, data files). Ensure that if they are not WGS84 lat/lon, they are correctly reprojected before being used by `resolve_ummg_geometry`. This might involve integrating `pyproj`.
    *   **Tests**: Add more specific tests for reprojection logic within the parsing functions, covering edge cases or different source CRSs if applicable.

*   **Step 4.2: Complex GPolygon Calculation (If Needed)**
    *   **Action**: If the "GPolygon(s) calculated to enclose all points" (for `.spatial` or data files with Geodetic GSR) requires more than just using the points in sequence (e.g., convex hull for a scattered set of points), implement this. This might involve a library like `shapely`.
    *   **Unit Tests**:
        *   Test cases with scattered points that require a convex hull to form the enclosing GPolygon.
        *   Test cases that might result in multiple GPolygons (if supported by UMM-G and your requirements).

*   **Step 4.3: Re-evaluate README Note 4 ("always associate GEODETIC... with point data")**
    *   **Action**:
        *   Discuss with stakeholders/data curators the exact meaning of Note 4.
        *   Does it mean:
            1.  If source data has 1 point and GSR is Cartesian, it's an error (current table interpretation)?
            2.  If source data has 1 point and GSR is Cartesian, the GSR should be *treated as if it were Geodetic* for this granule, and a `UMMGPoint` produced?
            3.  Something else?
        *   Adjust the logic in `resolve_ummg_geometry` for `.spatial | 1 | cartesian` and `data file | 1 | cartesian` based on this clarification.
    *   **Unit Tests**:
        *   Update/add tests for 1-point Cartesian scenarios to reflect the clarified interpretation.

*   **Step 4.4: Final Code Review and Documentation**
    *   **Action**:
        *   Review all new code for clarity, efficiency, and adherence to style guides.
        *   Add comments and docstrings where necessary, especially for `resolve_ummg_geometry` and the parsing functions.
        *   Update any relevant project documentation.
    *   **Tests**: Ensure all tests pass and coverage is good.