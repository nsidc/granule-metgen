## v1.13.0 (2025-11-24)

* Add a new configuration parameter 'spatial_polygon_algorithm' to select simple or
  complex polygon methods. The new simple method is used for satellite ground tracks
  or similarly less-complex geometries.

## v1.13.0rc1 (2025-11-17)

* PSS-692: Ensure longitude values of the generated polygons stay in-bounds [-180,180].

## v1.13.0rc0 (2025-09-17)

* Issue 292: Exclude `.spo` files from polygon-generation logic, regardless of
  the value of the `spatial_polygon_enabled` flag in the `ini` file.

## v1.12.0 (2025-09-15)

* Minor version release encompassing all features in v1.12.0rc0 - v1.12.0rc3.

## v1.12.0rc3 (2025-09-12)

* Issue-247 patch of the patch: Ensure polygons generated from
 `geospatial_bounds` are counterclockwise.

## v1.12.0rc2 (2025-09-11)

* Issue-247 patch: Allow for the fact that EPSG:4326 coordinates are listed in
  (lat, lon) order in the `geospatial_bounds` WKT value.

## v1.12.0rc1 (2025-09-08)

* Issue-273: Describe the `cumulus-prod` AWS profile in the README.md.
* Issue-195: Include MetGenC version number in CNM message `trace` field.
* Issue-247: Add `ini` option to use the values in a NetCDF file's
  `geospatial_bounds` global attribute to construct the GPolygon describing the data coverage.

## v1.12.0rc0 (2025-09-02)

* Issue-255: Remove CSV reader capability (generic & SNOWEX-specific readers)
* Issue-282: Fix configuration issues with some integration tests
* Issue-272: Add a user-provided logfile directory location. Add the configuration
  file's basename and the metgenc start datetime to the logfile's name.

## v1.11.0 (2025-09-02)

 * Minor version release of all issues in v1.11.0rc1, rc2, rc3

## v1.11.0rc3 (2025-08-25)

* Issue-259: Fix white space bug in handling of `.premet` contents.

## v1.11.0rc2 (2025-08-21)

* Issue-250: Use the current date/time to populate `ProductionDateTime` in UMM-G
  output for all collections.
* Issue-251: Look for (and use if available) a `spatial_ref` attribute associated with
  a NetCDF file's grid mapping variable if the variable doesn't have a `crs_wkt` attribute.

## v1.11.0rc1 (2025-08-20)

* Issue-241 patch: Update templates to use `short_name` rather than `auth_id`.

## v1.11.0rc0 (2025-08-19)

* Issue-241: Extract Collection Metadata Reader (Pipeline Story #2)
* Issue-254: Added integration test for IPFLT1B; Simplified code that caused a bug when
  determining the granule key based on a regex.

## v1.10.2 (2025-08-19)

* Minor version release

## v1.10.2rc3 (2025-08-15)

* Version bump to address PyPI build issue.

## v1.10.2rc2 (2025-08-15)

* Issue-169 patch: Use reference data file to identify the file reader.

## v1.10.2rc1 (2025-08-14)

* Reverted regex search in version bumping; require new "unreleased" entry for
  each release.

## v1.10.2rc0 (2025-08-14)

* Issue-233: Simplified our plans for incrementally improving the processing pipeline. See
  the [Pipeline Refactoring Plan](devdocs/PIPELINE_REFACTORING_PLAN.md)

## v1.10.0rc1 (2025-08-04)
* Allow operator to specify which science (data) file should be scraped for
  metadata in the case of a granule with multiple science files. (Issue-169)
* Add regex to version bump configuration for this (`CHANGELOG.md`) file, and to update
  configuration to insert the date of the version bump.
* This release was created from branch `v1.10rc`.

## v1.10.1

* Retrieve platform/instrument/sensor information if it exists in the premet
  file and include it in UMM-G output. (Issue-227)
* Treat equivalent begin and end date/times in `premet` files as a single time
  value. (Issue-221)
* This release was created from branch `v1.10rc`, resulting in an out-of-order
  release number.

## v1.9.0

* Adds an experimental script that generates premet & spatial files for OLVIS1A granules
* Adds the ability for the operator to override the default minimum distance tolerance between points
* Fixes a regression where the flightline polygon would sometimes be mistakenly oriented clockwise
* Add optional spatial polygon generation for flightline data with optimized coverage and vertex limits. (Issue-156)
* Improves performance of flightlines that have many points (Issue-218)
* Fix UMM-G `RangeDateTimes` template error.
* Refine search for `AdditionalAttribute` values in `premet` files. (Issue-225)
* Add an integration test suite for all collections. See the [integration test README](tests/integration/README.md)
* Fix a bug which caused incorrect output file locations in some cases.

## v1.8.0

* Adds a generic reader used when `metgenc` processes granules with an unknown
  file-type. It uses spatial metadata from `spatial` files or collection metadata. (Issue-199)
* Add `.ini` option to use collection temporal extent information to describe each granule. (Issue-139)
* Refine README presentation of geometry logic. (Issue-157)

## v1.7.0

* Refactor logic for identifying granule spatial representation. (Issue-159)
* End processing if UMM-C metadata can't be retrieved and/or do not contain a
  `GranuleSpatialRepresentation` element.
* Add support for bounding rectangles. (Issue-157)
* Add `.ini` option to use collection spatial extent information to describe each granule. (Issue-140)

## v1.6.1

* Fix oversight which made additional attributes required, not optional.
  (Issue-200)
* Parse `AdditionalAttributes` from `.premet` file and include them in UMM-G
  output. (Issue-162, Issue-186)
* Rename template files with `.txt` extension.

## v1.5.0

* Add support for reading IRWIS2 CSV files (Issue-154)
* Store `GranuleSpatialRepresentation` value from CMR collection metadata in the
  `Collection` object. (Issue-163)
* Read temporal extents from `premet` files if they exist. (Issue-160)
* Read spatial information from `spatial` files if they exist. (Issue-161)
* Read spatial information from `spo` files and reverse point order to create a
  counter-clockwise polygon definition. Close polygon if necessary. (Issue-158)
* Note successful collection metadata harvest details in the log, not to `stdout`.
* Skip remaining pipeline operations if a step fails.
* Move `netcdf_reader` to `readers` module.

## v1.4.0

* Add a CSV reader to process [SNOWEX](https://nsidc.org/data/snex23_ssa/versions/1) granules. (Issue-108)
* Handle a bug in `xarray` when processing NSIDC-0630 v2 granules. (Issue-152)
* Support creating release-candidates of MetGenC (v1.4.0rc1, 1.4.0rc2, ...) (Issue-128)
* Refine regex handling for multi-data-file granules. (Issue-103)
* Add optional paths for `premet` and `spatial` files to `ini` file. (Issue-155)
* Add CLI `--version` option

## v1.3.0

* Adds browse file names to CNM content and stages them to Cumulus if they
  exist. (Issue-61)

## v1.2.1

* Adds support for Earthdata login and retrieval of collection-level metadata
  from CMR. (Issue-15)

## v1.1.0

* Extends `ini` file to include values for attributes missing from a minimal,
  CF-compliant netCDF file. (Issue-104)

## v1.0.2

* Fixes bug with JSON output validation

## v1.0.1

* Creates and publishes documentation to
  [ReadTheDocs](https://granule-metgen.readthedocs.io/en/latest/)
* Internal updates to no longer rely on a deprecated Python function
* Fixes instructions to set the AWS environment

## v1.0.0

* Adds command-line options to:
  * Validate the generated CNM message against the JSON schema
  * Validate the generated UMM-G metadata against the JSON schema
  * Skip staging the UMM-G files and sending the CNM message
  * Overwrite any existing UMM-G files for granules it is processing
* Adds code linting and formatting checks
* Adds a new release process for the project
* Releases are published to [PyPI](https://pypi.org/project/nsidc-metgenc/)

## v0.6.0

This is the Minimum Viable Product (MVP) release of MetGenC. The
features include:

  * A prompt-driven means of creating a configuration file used to control
    MetGenC's metadata generation and file staging steps.
  * Creation of UMM-G compliant metadata for each source granule,
    including temporal and spatial bounds.
  * Cumulus Notification Message (CNM) output for each granule,
    containing a unique identifier (UUID), submission time, and a list
    of associated files with unique checksums.
  * Staging of science data files and their UMM-G metadata in
    a configurable S3 bucket location.
  * Posting of CNM messages to a configurable Kinesis stream in
    order to trigger a Cumulus workflow.
  * Command-line validation options for CNM JSON content.
  * A `--dry-run` command-line option for testing without S3/Kinesis access.
  * Automatic build and deploy of the application to PyPI.
