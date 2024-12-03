MetGenC Changelog

## UNRELEASED

This is the Minimum Viable Product (MVP) release of MetGenC. The
features include:

  * Provides a prompt-driven means of configuring MetGenC to ingest
    a new collection.
  * Processing is driven by a configuration file for control of various
    aspects of the ingest.
  * Generates a UUID and submission time for each granule.
  * Creates UMM-G compliant metadata for each source granule.
  * The UMM-G includes required attributes, including temporal and 
    spatial bounds.
  * Generates a Cumulus Notification Message (CNM) for each granule.
  * Stages the science data files and their UMM-G metadata in
    a configurable S3 bucket location.
  * Submits the CNM message to a configurable Kinesis stream in
    order to trigger a Cumulus workflow.
