MetGenC Changelog

## v0.5.0

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

