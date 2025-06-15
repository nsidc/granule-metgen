# Inferred Current State of Geometry Handling in MetGenC

This document summarizes the inferred current state of geometry handling within the MetGenC codebase (`src/metgen/*.py` and `src/metgen/readers/*.py`), based on analysis of `README.md` and the `geometry_resolver_implementation_plan.md`. This summary is intended to guide the refactoring process.

## Overview

The current geometry handling in MetGenC likely involves several components and modules, with decision logic potentially distributed across the application. The primary goal of the refactoring effort is to centralize this decision logic.

## Key Components and Functionality

1.  **Configuration-Driven Behavior (`ini` file parsing):**
    *   **Location:** Likely in a module responsible for parsing the `ini` configuration file (e.g., `metgen/configuration.py`) or within the main processing script (e.g., `metgen/main.py` or `metgen/processor.py`).
    *   **Functionality:**
        *   Reads `collection_geometry_override: bool` (influences primary geometry source).
        *   Reads `spatial_dir: Optional[str]` (for `.spo` and `.spatial` files).
        *   Reads `pixel_size: Optional[str]` (potentially for polygon padding/extents from NetCDF).
        *   `GranuleSpatialRepresentation` (GSR) determination might be implicit or based on collection metadata.

2.  **Collection Metadata Retrieval and Usage:**
    *   **Location:** A module for CMR interaction (e.g., `metgen/cmr.py` or `metgen/metadata_retriever.py`), used by main processing logic.
    *   **Functionality:**
        *   Fetches collection-level UMM-C metadata.
        *   Extracts `BoundingRectangles` (used for override or fallback).
        *   Potentially extracts default `GranuleSpatialRepresentation` for the collection.

3.  **Sidecar File Readers (`.spo`, `.spatial`):**
    *   **Location:** Likely in `metgen/readers/` (e.g., `metgen/readers/spatial_readers.py`) or as utility functions.
    *   **Functionality:**
        *   Constructs paths to `.spo` or `.spatial` files using `spatial_dir`.
        *   **`.spo` file reader:**
            *   Parses point coordinates.
            *   Counts points.
            *   Likely directly attempts to form UMM-G `GPolygon` or flags errors based on GSR and point count.
        *   **`.spatial` file reader:**
            *   Parses point coordinates.
            *   Counts points.
            *   Likely contains `if/elif` logic based on point count and GSR to create UMM-G `Point`, `BoundingRectangle`, or `GPolygon`, or flags errors.

4.  **Data File Geometry Extraction (especially NetCDF):**
    *   **Location:** Within a NetCDF-specific reader (e.g., `metgen/readers/netcdf_reader.py`) or a general data file reader.
    *   **Functionality (NetCDF):**
        *   Uses libraries like `netCDF4` or `xarray`.
        *   Extracts global attributes (e.g., `time_coverage_start`, min/max lon/lat for Cartesian BR).
        *   Identifies grid mapping variable (`grid_mapping_name`).
        *   Extracts `crs_wkt` and `GeoTransform`.
        *   Identifies coordinate variables (`projection_x_coordinate`, `projection_y_coordinate`).
        *   **Reprojection:** Uses `pyproj` to reproject coordinates to EPSG:4326 (lon/lat).
        *   **Polygon/BR Calculation:**
            *   For Geodetic GSR (gridded, >=3 points): Calculates perimeter from reprojected x/y coordinates, possibly using `GeoTransform` or `pixel_size` for padding.
            *   For Cartesian GSR: Derives Bounding Rectangle from min/max reprojected coordinates or global attributes.
        *   Decision logic for Point, Polygon, or BR based on point count and GSR is likely embedded here or in the calling processor.
    *   **Functionality (Non-NetCDF):**
        *   Specific readers for other formats if supported.
        *   Generic handler might apply "data file (some collection of points)" rules, requiring a method to extract points.

5.  **Granule Spatial Representation (GSR) Determination:**
    *   **Location:** Main processor or a utility function.
    *   **Functionality:** GSR for each granule is determined, potentially from:
        *   Collection metadata (default).
        *   `ini` file (if collection-wide).
        *   README Note 4 ("always associate GEODETIC... with point data") might act as an override.

6.  **Core Geometry Decision Logic (The "Table Rules"):**
    *   **Location:** Most likely within the main granule processing pipeline/module (e.g., `metgen/processor.py` or `metgen/geometry_utils.py`).
    *   **Functionality:** Implements the rules from the "Geometry logic" table in `README.md`, likely as a sequence of `if/elif/else` statements considering:
        1.  `collection_geometry_override` flag.
        2.  Presence/content of `.spo` files.
        3.  Presence/content of `.spatial` files.
        4.  Geometry derived from the data file.
        5.  Fallback to collection metadata `BoundingRectangles`.
        *   Checks number of points and GSR for each case.
        *   Directly constructs the UMM-G `Geometry` dictionary or flags errors.
        *   Error handling for invalid combinations is likely part of these conditional blocks.

7.  **UMM-G Output Assembly:**
    *   **Location:** Main processing pipeline.
    *   **Functionality:** The chosen geometry dictionary (`Point`, `BoundingRectangle`, or `GPolygon`) is inserted into the UMM-G record under `HorizontalSpatialDomain.Geometry`.

## Summary of Expected Current Structure

The current system likely features:
*   Readers for specific file types (`.spo`, `.spatial`, NetCDF) that extract raw coordinate data and attributes, potentially performing reprojection.
*   Logic to fetch and parse collection-level metadata for bounding boxes and possibly GSR.
*   A central processing section that orchestrates these inputs, applies `collection_geometry_override`, determines GSR, and then uses conditional statements (mimicking the README geometry table) to decide on the final UMM-G geometry and construct its dictionary representation.
*   Error handling is likely intertwined with this decision logic.

The refactoring plan aims to decouple data extraction/parsing (which will populate new input dataclasses like `SpoData`, `DataFileGeometry`) from decision-making (which will be centralized in `resolve_ummg_geometry`).
