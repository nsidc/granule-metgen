"""
Collection metadata retrieval module.

This module provides a standalone interface for retrieving collection metadata
from NASA's Common Metadata Repository (CMR) in UMM-C format, which is then
parsed into a structured dataclass for use throughout the metgen pipeline.
"""

import logging
from typing import Optional, Union

import earthaccess

from nsidc.metgen import constants
from nsidc.metgen.models import CollectionMetadata


class CollectionMetadataReader:
    """
    Reader class for retrieving and parsing collection metadata.
    """

    def __init__(self, environment: str = "uat"):
        """
        Initialize the collection reader.

        Args:
            environment: Environment to query ("uat" or "prod")
        """
        self.environment = environment.lower()
        self.provider = self._get_provider()
        self.logger = logging.getLogger(constants.ROOT_LOGGER)

    def _get_provider(self) -> str:
        """Get the appropriate CMR provider based on environment."""
        return (
            constants.CMR_PROD_PROVIDER
            if self.environment == "prod"
            else constants.CMR_UAT_PROVIDER
        )

    def _get_earthaccess_system(self):
        """Get the Earthdata Login system object."""
        return earthaccess.PROD if self.environment == "prod" else earthaccess.UAT

    def get_collection_metadata(
        self, short_name: str, version: Union[str, int]
    ) -> CollectionMetadata:
        """
        Retrieve collection metadata from CMR.

        Args:
            short_name: Collection short name (e.g., "SNEX23_SSADUCk")
            version: Collection version (e.g., "1" or 1)

        Returns:
            CollectionMetadata object containing parsed collection metadata

        Raises:
            Exception: If Earthdata login fails or CMR query returns invalid data
        """
        version_str = str(version)

        # Attempt Earthdata login
        if not earthaccess.login(
            strategy="environment", system=self._get_earthaccess_system()
        ):
            raise Exception(
                f"Earthdata login failed, cannot retrieve UMM-C metadata for "
                f"{short_name}.{version_str}"
            )

        self.logger.info("Earthdata login succeeded.")

        # Search for collection in CMR
        cmr_response = earthaccess.search_datasets(
            short_name=short_name,
            version=version_str,
            has_granules=None,  # Find collections with or without granules
            provider=self.provider,
        )

        # Validate and parse response
        ummc = self._validate_cmr_response(cmr_response, short_name, version_str)

        return self._parse_ummc_metadata(ummc, short_name, version_str)

    def _validate_cmr_response(
        self, response: list, short_name: str, version: str
    ) -> dict:
        """
        Validate the CMR response and extract the UMM-C record.

        Args:
            response: Raw response from earthaccess
            short_name: Collection short name for error messages
            version: Collection version for error messages

        Returns:
            Validated UMM-C dictionary

        Raises:
            ValueError: If response is invalid
        """
        if not response:
            raise ValueError(
                f"Empty UMM-C response from CMR for {short_name}.{version}"
            )

        if len(response) > 1:
            raise ValueError(
                f"Multiple UMM-C records returned from CMR for {short_name}.{version}, "
                "none will be used."
            )

        # Check that the response item is a dict before extracting
        if not isinstance(response[0], dict) or "umm" not in response[0]:
            raise ValueError(
                f"No UMM-C content in CMR response for {short_name}.{version}"
            )

        # Extract the UMM-C content
        ummc = response[0].get("umm", response[0])

        if not isinstance(ummc, dict):
            raise ValueError(
                f"Invalid UMM-C format in CMR response for {short_name}.{version}"
            )

        return ummc

    def _parse_ummc_metadata(
        self, ummc: dict, short_name: str, version: str
    ) -> CollectionMetadata:
        """
        Parse UMM-C record into structured metadata.

        Args:
            ummc: UMM-C dictionary from CMR
            short_name: Collection short name
            version: Collection version

        Returns:
            Populated CollectionMetadata object
        """
        # Extract temporal extent and check for errors
        temporal_extent, temporal_error = self._parse_temporal_extent(ummc)

        # Build the metadata object
        return CollectionMetadata(
            short_name=short_name,
            version=version,
            entry_title=ummc.get("EntryTitle", f"{short_name}.{version}"),
            granule_spatial_representation=self._extract_nested_value(
                ummc, constants.GRANULE_SPATIAL_REP_PATH
            ),
            spatial_extent=self._extract_nested_value(
                ummc, constants.SPATIAL_EXTENT_PATH
            ),
            temporal_extent=temporal_extent,
            temporal_extent_error=temporal_error,
        )

    def _parse_temporal_extent(
        self, ummc: dict
    ) -> tuple[Optional[list], Optional[str]]:
        """
        Parse temporal extent from UMM-C, checking for validity.

        Returns:
            Tuple of (temporal_extent, error_message)
        """
        temporal_extent = self._extract_nested_value(
            ummc, constants.TEMPORAL_EXTENT_PATH
        )

        if not temporal_extent:
            return None, None

        # Check if there are multiple temporal extents
        if len(temporal_extent) > 1:
            return (
                temporal_extent,
                "Collection metadata must only contain one temporal extent when "
                "collection_temporal_override is set.",
            )

        # Extract temporal details from the first extent
        temporal_details = self._get_temporal_details(temporal_extent[0])

        if temporal_details and len(temporal_details) > 1:
            return (
                temporal_details,
                "Collection metadata must only contain one temporal range or a single "
                "temporal value when collection_temporal_override is set.",
            )

        return temporal_details, None

    def _get_temporal_details(self, temporal_extent: dict) -> Optional[list]:
        """
        Extract temporal range or single date from temporal extent.
        """
        # Check for single date times first
        single_dates = self._extract_nested_value(
            temporal_extent, constants.TEMPORAL_SINGLE_PATH
        )
        if single_dates:
            return single_dates

        # Otherwise check for range date times
        return self._extract_nested_value(
            temporal_extent, constants.TEMPORAL_RANGE_PATH
        )

    def _extract_nested_value(
        self, data: dict, keys: list[str]
    ) -> Optional[Union[str, list, dict]]:
        """
        Extract a value from nested dictionary using a list of keys.

        Args:
            data: Dictionary to search
            keys: List of keys representing the path to the value

        Returns:
            The value if found, None otherwise
        """
        if data is None:
            return None

        current = data

        for key in keys:
            if not isinstance(current, dict) or key not in current:
                self.logger.debug(
                    f"Key path {' -> '.join(keys)} not found in UMM-C record"
                )
                return None
            current = current[key]

        return current


def get_collection_metadata(
    environment: str, short_name: str, version: Union[str, int]
) -> CollectionMetadata:
    """
    Retrieve collection metadata for the specified collection.

    This function creates a CollectionReader instance and retrieves the metadata,
    providing a simple interface for the rest of the application.

    Args:
        environment: Environment to query ("uat" or "prod")
        short_name: Collection short name
        version: Collection version

    Returns:
        CollectionMetadata object
    """
    reader = CollectionMetadataReader(environment)
    return reader.get_collection_metadata(short_name, version)
