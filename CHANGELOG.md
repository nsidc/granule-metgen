## v1.9.0rc3

* Adds the ability for the operator to override the default minimum distance tolerance between points
* Fixes a regression where the flightline polygon would sometimes be mistakenly oriented clockwise
* Add optional spatial polygon generation for flightline data with optimized coverage and vertex limits. (Issue-156)
* Fix UMM-G `RangeDateTimes` template error.
* Refine search for `AdditionalAttribute` values in `premet` files.
* Add an integration test suite for all collections. See the [integration test README](tests/integration/README.md)
* Fix a bug which caused incorrect output file locations in some cases

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
