## v1.2.1

* Adds support for Earthdata login and retrieval of collection-level metadata
  from CMR. (Issue-15)

## v1.1.0

* Extend `ini` file to include values for attributes missing from a minimal,
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
