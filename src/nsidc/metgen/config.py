"""
Provides functions for reading, parsing, and validating the application
configuration values.
"""

import configparser
import dataclasses
import logging
import os.path
from pathlib import Path
from typing import Optional

from nsidc.metgen import aws, constants


class ValidationError(Exception):
    errors: list[str]

    def __init__(self, errors):
        self.errors = errors


@dataclasses.dataclass
class Config:
    environment: str
    data_dir: str
    auth_id: str
    version: str
    provider: str
    local_output_dir: str
    ummg_dir: str
    kinesis_stream_name: str
    staging_bucket_name: str
    write_cnm_file: bool
    overwrite_ummg: bool
    checksum_type: str
    number: int
    dry_run: bool
    premet_dir: Optional[str] = None
    spatial_dir: Optional[str] = None
    collection_geometry_override: Optional[bool] = False
    collection_temporal_override: Optional[bool] = False
    time_start_regex: Optional[str] = None
    time_coverage_duration: Optional[str] = None
    pixel_size: Optional[int] = None
    browse_regex: Optional[str] = None
    granule_regex: Optional[str] = None
    reference_file_regex: Optional[str] = None
    spatial_polygon_enabled: Optional[bool] = False
    spatial_polygon_target_coverage: Optional[float] = None
    spatial_polygon_max_vertices: Optional[int] = None
    spatial_polygon_cartesian_tolerance: Optional[float] = None

    def show(self):
        # TODO: add section headings in the right spot
        #       (if we think we need them in the output)
        LOGGER = logging.getLogger(constants.ROOT_LOGGER)
        LOGGER.info("")
        LOGGER.info("Using configuration:")
        for k, v in self.__dict__.items():
            LOGGER.info(f"  + {k}: {v}")

        if self.dry_run:
            LOGGER.info("")
            LOGGER.info(
                "Note: The dry-run option was included, so no files will be \
staged and no CNM messages published."
            )
            LOGGER.info("")

    def ummg_path(self):
        return Path(self.local_output_dir, self.ummg_dir)

    def cnm_path(self):
        return Path(self.local_output_dir, "cnm")


def config_parser_factory(configuration_file):
    """
    Returns a ConfigParser by reading the specified file.
    """
    if configuration_file is None or not os.path.exists(configuration_file):
        raise ValueError(f"Unable to find configuration file {configuration_file}")
    cfg_parser = configparser.ConfigParser(
        interpolation=configparser.ExtendedInterpolation()
    )
    # If the config parser gets no value (empty string), interpret it as False
    cfg_parser.BOOLEAN_STATES |= [("", False)]
    cfg_parser.read(configuration_file)
    return cfg_parser


def _get_configuration_value(
    environment, section, name, value_type, config_parser, overrides
):
    """
    Returns a value from the provided config parser; any value for the key that
    is provided in the 'overrides' dictionary will take precedence.
    """
    # Check overrides first
    if overrides.get(name) is not None:
        return overrides.get(name)

    vars = {"environment": environment}

    # Helper function to get typed value from a section
    def get_typed_value(section_name):
        if value_type is bool:
            return config_parser.getboolean(section_name, name)
        elif value_type is int:
            return config_parser.getint(section_name, name)
        elif value_type is float:
            return config_parser.getfloat(section_name, name)
        else:
            return config_parser.get(section_name, name, vars=vars)

    # Try to get from specified section first
    try:
        return get_typed_value(section)
    except Exception:
        # If we can't get the value (missing section or option), try DEFAULT
        try:
            return get_typed_value("DEFAULT")
        except Exception:
            return None


def configuration(
    config_parser, overrides, environment=constants.DEFAULT_CUMULUS_ENVIRONMENT
):
    """
    Returns a valid Config object that is populated from the provided config
    parser based on the 'environment', and with values overriden with anything
    provided in 'overrides'.
    """
    config_parser["DEFAULT"] = {
        "kinesis_stream_name": constants.DEFAULT_STAGING_KINESIS_STREAM,
        "staging_bucket_name": constants.DEFAULT_STAGING_BUCKET_NAME,
        "write_cnm_file": constants.DEFAULT_WRITE_CNM_FILE,
        "overwrite_ummg": constants.DEFAULT_OVERWRITE_UMMG,
        "checksum_type": constants.DEFAULT_CHECKSUM_TYPE,
        "number": constants.DEFAULT_NUMBER,
        "dry_run": constants.DEFAULT_DRY_RUN,
        "browse_regex": constants.DEFAULT_BROWSE_REGEX,
        "collection_geometry_override": constants.DEFAULT_COLLECTION_GEOMETRY_OVERRIDE,
        "collection_temporal_override": constants.DEFAULT_COLLECTION_TEMPORAL_OVERRIDE,
        "spatial_polygon_enabled": constants.DEFAULT_SPATIAL_POLYGON_ENABLED,
        "spatial_polygon_target_coverage": constants.DEFAULT_SPATIAL_POLYGON_TARGET_COVERAGE,
        "spatial_polygon_max_vertices": constants.DEFAULT_SPATIAL_POLYGON_MAX_VERTICES,
        "spatial_polygon_cartesian_tolerance": constants.DEFAULT_SPATIAL_POLYGON_CARTESIAN_TOLERANCE,
    }
    try:
        return Config(
            environment,
            _get_configuration_value(
                environment, "Source", "data_dir", str, config_parser, overrides
            ),
            _get_configuration_value(
                environment, "Collection", "auth_id", str, config_parser, overrides
            ),
            _get_configuration_value(
                environment, "Collection", "version", int, config_parser, overrides
            ),
            _get_configuration_value(
                environment, "Collection", "provider", str, config_parser, overrides
            ),
            _get_configuration_value(
                environment,
                "Destination",
                "local_output_dir",
                str,
                config_parser,
                overrides,
            ),
            _get_configuration_value(
                environment, "Destination", "ummg_dir", str, config_parser, overrides
            ),
            _get_configuration_value(
                environment,
                "Destination",
                "kinesis_stream_name",
                str,
                config_parser,
                overrides,
            ),
            _get_configuration_value(
                environment,
                "Destination",
                "staging_bucket_name",
                str,
                config_parser,
                overrides,
            ),
            _get_configuration_value(
                environment,
                "Destination",
                "write_cnm_file",
                bool,
                config_parser,
                overrides,
            ),
            _get_configuration_value(
                environment,
                "Destination",
                "overwrite_ummg",
                bool,
                config_parser,
                overrides,
            ),
            _get_configuration_value(
                environment, "Settings", "checksum_type", str, config_parser, overrides
            ),
            _get_configuration_value(
                environment, "Settings", "number", int, config_parser, overrides
            ),
            _get_configuration_value(
                environment, "Settings", "dry_run", bool, config_parser, overrides
            ),
            _get_configuration_value(
                environment, "Source", "premet_dir", str, config_parser, overrides
            ),
            _get_configuration_value(
                environment, "Source", "spatial_dir", str, config_parser, overrides
            ),
            _get_configuration_value(
                environment,
                "Source",
                "collection_geometry_override",
                bool,
                config_parser,
                overrides,
            ),
            _get_configuration_value(
                environment,
                "Source",
                "collection_temporal_override",
                bool,
                config_parser,
                overrides,
            ),
            _get_configuration_value(
                environment,
                "Collection",
                "time_start_regex",
                str,
                config_parser,
                overrides,
            ),
            _get_configuration_value(
                environment,
                "Collection",
                "time_coverage_duration",
                str,
                config_parser,
                overrides,
            ),
            _get_configuration_value(
                environment,
                "Collection",
                "pixel_size",
                int,
                config_parser,
                overrides,
            ),
            _get_configuration_value(
                environment,
                "Collection",
                "browse_regex",
                str,
                config_parser,
                overrides,
            ),
            _get_configuration_value(
                environment,
                "Collection",
                "granule_regex",
                str,
                config_parser,
                overrides,
            ),
            _get_configuration_value(
                environment,
                "Collection",
                "reference_file_regex",
                str,
                config_parser,
                overrides,
            ),
            _get_configuration_value(
                environment,
                "Spatial",
                "spatial_polygon_enabled",
                bool,
                config_parser,
                overrides,
            ),
            _get_configuration_value(
                environment,
                "Spatial",
                "spatial_polygon_target_coverage",
                float,
                config_parser,
                overrides,
            ),
            _get_configuration_value(
                environment,
                "Spatial",
                "spatial_polygon_max_vertices",
                int,
                config_parser,
                overrides,
            ),
            _get_configuration_value(
                environment,
                "Spatial",
                "spatial_polygon_cartesian_tolerance",
                float,
                config_parser,
                overrides,
            ),
        )
    except Exception as e:
        raise Exception("Unable to read the configuration file", e)


def validate(configuration):
    """
    Validates each value in the configuration.
    """
    validations = [
        [
            "data_dir",
            lambda dir: os.path.exists(dir),
            "The data_dir does not exist.",
        ],
        [
            "premet_dir",
            lambda dir: os.path.exists(dir) if dir else True,
            "The premet_dir does not exist.",
        ],
        [
            "spatial_dir",
            lambda dir: os.path.exists(dir) if dir else True,
            "The spatial_dir does not exist.",
        ],
        [
            "local_output_dir",
            lambda dir: os.path.exists(dir),
            "The local_output_dir does not exist.",
        ],
        # TODO: validate "local_output_dir/ummg_dir" as part of issue-71
        # [
        #     "ummg_dir",
        #     lambda dir: os.path.exists(dir),
        #     "The ummg_dir does not exist."
        # ],
        [
            "kinesis_stream_name",
            lambda name: aws.kinesis_stream_exists(name)
            if not configuration.dry_run
            else lambda _: True,
            "The kinesis stream does not exist.",
        ],
        [
            "staging_bucket_name",
            lambda name: aws.staging_bucket_exists(name)
            if not configuration.dry_run
            else lambda _: True,
            "The staging bucket does not exist.",
        ],
        [
            "number",
            lambda number: 0 < number,
            "The number of granules to process must be positive.",
        ],
        [
            "spatial_polygon_target_coverage",
            lambda coverage: 0.80 <= coverage <= 1.0,
            "The spatial polygon target coverage must be between 0.80 and 1.0.",
        ],
        [
            "spatial_polygon_max_vertices",
            lambda vertices: 10 <= vertices <= 1000,
            "The spatial polygon max vertices must be between 10 and 1000.",
        ],
        [
            "spatial_polygon_cartesian_tolerance",
            lambda tolerance: 0.00001 <= tolerance <= 0.01
            if tolerance is not None
            else True,
            "The spatial polygon cartesian tolerance must be between 0.00001 and 0.01 degrees.",
        ],
    ]
    errors = [
        msg for name, fn, msg in validations if not fn(getattr(configuration, name))
    ]
    if len(errors) == 0:
        return True
    else:
        raise ValidationError(errors)


def validate_spatial_source(configuration):
    if configuration.spatial_dir and configuration.collection_geometry_override:
        raise ValidationError(
            [
                "Cannot declare both spatial_dir and collection_geometry_override in ini file."
            ]
        )
    return True
