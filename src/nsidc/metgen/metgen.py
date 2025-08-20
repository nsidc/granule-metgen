"""
Implements all core functionality of the MetGenC utility: logging,
metadata generation, CNM message creation, as well as staging the
metadata and posting the notification message.
"""

import configparser
import dataclasses
import datetime as dt
import hashlib
import importlib.resources
import json
import logging
import os.path
import re
import sys
import uuid
from collections.abc import Callable
from pathlib import Path
from string import Template

import jsonschema
from funcy import (
    all,
    concat,
    filter,
    first,
    last,
    one,
    partial,
    rcompose,
    some,
    take,
)
from jsonschema.exceptions import ValidationError
from pyfiglet import Figlet
from returns.maybe import Maybe
from rich.prompt import Confirm, Prompt

from nsidc.metgen import aws, config, constants
from nsidc.metgen.collection_metadata import get_collection_metadata
from nsidc.metgen.models import CollectionMetadata
from nsidc.metgen.readers import generic, registry, utilities
from nsidc.metgen.spatial import create_flightline_polygon

# -------------------------------------------------------------------
CONSOLE_FORMAT = "%(message)s"
LOGFILE_FORMAT = "%(asctime)s|%(levelname)s|%(name)s|%(message)s"

# -------------------------------------------------------------------
# Top-level functions which expose operations to the CLI
# -------------------------------------------------------------------


def init_logging():
    """
    Initialize the logger for metgenc.
    """
    logger = logging.getLogger(constants.ROOT_LOGGER)
    logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    logger.addHandler(console_handler)

    logfile_handler = logging.FileHandler(constants.ROOT_LOGGER + ".log", "a")
    logfile_handler.setLevel(logging.DEBUG)
    logfile_handler.setFormatter(logging.Formatter(LOGFILE_FORMAT))
    logger.addHandler(logfile_handler)


def banner():
    """
    Displays the name of this utility using incredible ASCII-art.
    """
    f = Figlet(font="slant")
    return f.renderText("metgenc")


# TODO require a non-blank input for elements that have no default value
def init_config(configuration_file):
    """
    Prompts the user for configuration values and then creates a valid
    configuration file.
    """
    print(
        """This utility will create a granule metadata configuration file by prompting
        you for values for each of the configuration parameters."""
    )
    print()
    # prompt for config file name if it's not provided
    if not configuration_file:
        configuration_file = Prompt.ask(
            "configuration file name", default="example.ini"
        )
        # TODO check file name is safe
    else:
        print(f"Creating configuration file {configuration_file}")
        print()

    if os.path.exists(configuration_file):
        print(f"WARNING: The {configuration_file} already exists.")
        overwrite = Confirm.ask("Overwrite?")
        if not overwrite:
            print("Not overwriting existing file. Exiting.")
            exit(1)

    cfg_parser = configparser.ConfigParser()

    print()
    print(f"{constants.SOURCE_SECTION_NAME} Data Parameters")
    print("--------------------------------------------------")
    cfg_parser.add_section(constants.SOURCE_SECTION_NAME)
    cfg_parser.set(
        constants.SOURCE_SECTION_NAME,
        "data_dir",
        Prompt.ask("Data directory", default="data"),
    )
    cfg_parser.set(
        constants.SOURCE_SECTION_NAME,
        "premet_dir",
        Prompt.ask("Premet directory"),
    )
    cfg_parser.set(
        constants.SOURCE_SECTION_NAME,
        "spatial_dir",
        Prompt.ask("Spatial directory"),
    )
    cfg_parser.set(
        constants.SOURCE_SECTION_NAME,
        "collection_geometry_override",
        Prompt.ask(
            "Use collection geometry? (True/False)",
            default=str(constants.DEFAULT_COLLECTION_GEOMETRY_OVERRIDE),
        ),
    )
    cfg_parser.set(
        constants.SOURCE_SECTION_NAME,
        "collection_temporal_override",
        Prompt.ask(
            "Use collection temporal extent? (True/False)",
            default=str(constants.DEFAULT_COLLECTION_TEMPORAL_OVERRIDE),
        ),
    )
    print()

    print()
    print(f"{constants.COLLECTION_SECTION_NAME} Parameters")
    print("--------------------------------------------------")
    cfg_parser.add_section(constants.COLLECTION_SECTION_NAME)
    cfg_parser.set(
        constants.COLLECTION_SECTION_NAME, "auth_id", Prompt.ask("Authoritative ID")
    )
    cfg_parser.set(constants.COLLECTION_SECTION_NAME, "version", Prompt.ask("Version"))
    cfg_parser.set(
        constants.COLLECTION_SECTION_NAME, "provider", Prompt.ask("Provider")
    )
    cfg_parser.set(
        constants.COLLECTION_SECTION_NAME,
        "browse_regex",
        Prompt.ask("Browse regex", default=constants.DEFAULT_BROWSE_REGEX),
    )
    cfg_parser.set(
        constants.COLLECTION_SECTION_NAME,
        "reference_file_regex",
        Prompt.ask("Reference science file regex"),
    )
    print()

    print()
    print(f"{constants.DESTINATION_SECTION_NAME} Parameters")
    print("--------------------------------------------------")
    cfg_parser.add_section(constants.DESTINATION_SECTION_NAME)
    cfg_parser.set(
        constants.DESTINATION_SECTION_NAME,
        "local_output_dir",
        Prompt.ask("Local output directory", default="output"),
    )
    cfg_parser.set(
        constants.DESTINATION_SECTION_NAME,
        "ummg_dir",
        Prompt.ask(
            "Local UMM-G output directory (relative to local output directory)",
            default="ummg",
        ),
    )
    cfg_parser.set(
        constants.DESTINATION_SECTION_NAME,
        "kinesis_stream_name",
        Prompt.ask(
            "Kinesis stream name", default=constants.DEFAULT_STAGING_KINESIS_STREAM
        ),
    )
    cfg_parser.set(
        constants.DESTINATION_SECTION_NAME,
        "staging_bucket_name",
        Prompt.ask(
            "Cumulus s3 bucket name", default=constants.DEFAULT_STAGING_BUCKET_NAME
        ),
    )
    cfg_parser.set(
        constants.DESTINATION_SECTION_NAME,
        "write_cnm_file",
        Prompt.ask(
            "Write CNM messages to files? (True/False)",
            default=str(constants.DEFAULT_WRITE_CNM_FILE),
        ),
    )
    cfg_parser.set(
        constants.DESTINATION_SECTION_NAME,
        "overwrite_ummg",
        Prompt.ask(
            "Overwrite existing UMM-G files? (True/False)",
            default=str(constants.DEFAULT_OVERWRITE_UMMG),
        ),
    )

    print()
    print(f"{constants.SETTINGS_SECTION_NAME} Parameters")
    print("--------------------------------------------------")
    cfg_parser.add_section(constants.SETTINGS_SECTION_NAME)
    cfg_parser.set(
        constants.SETTINGS_SECTION_NAME,
        "checksum_type",
        Prompt.ask("Checksum type", default=constants.DEFAULT_CHECKSUM_TYPE),
    )

    print()
    print(f"Saving new configuration: {configuration_file}")
    with open(configuration_file, "tw") as file:
        cfg_parser.write(file)

    return configuration_file


# -------------------------------------------------------------------
# Data structures for processing Granules and recording results
# -------------------------------------------------------------------


@dataclasses.dataclass
class Granule:
    """Granule to ingest"""

    producer_granule_id: str
    collection: Maybe[CollectionMetadata] = Maybe.empty
    data_filenames: set[str] = dataclasses.field(default_factory=set)
    browse_filenames: set[str] = dataclasses.field(default_factory=set)
    premet_filename: Maybe[str] = Maybe.empty
    spatial_filename: Maybe[str] = Maybe.empty
    reference_data_filename: str = dataclasses.field(default_factory=str)
    ummg_filename: Maybe[str] = Maybe.empty
    submission_time: Maybe[str] = Maybe.empty
    uuid: Maybe[str] = Maybe.empty
    cnm_message: Maybe[str] = Maybe.empty
    data_reader: Callable[[str, str, str, config.Config], dict] = (
        lambda auth_id, cfg: dict()
    )

    def size(self):
        if not self.data_filenames:
            return 0

        return sum(os.path.getsize(data_file) for data_file in self.data_filenames)


@dataclasses.dataclass
class Action:
    """An audit of a single action performed on a Granule"""

    name: str
    successful: bool
    message: str
    startDatetime: Maybe[dt.datetime] = Maybe.empty
    endDatetime: Maybe[dt.datetime] = Maybe.empty


@dataclasses.dataclass
class Ledger:
    """An audit of the Actions performed on a Granule"""

    granule: Granule
    actions: list[Action] = dataclasses.field(default_factory=list)
    successful: bool = False
    startDatetime: Maybe[dt.datetime] = Maybe.empty
    endDatetime: Maybe[dt.datetime] = Maybe.empty


# -------------------------------------------------------------------


def process(configuration: config.Config) -> None:
    """
    Process all Granules and record the results and summary.
    """
    # TODO: Do any prep actions, like mkdir, etc

    logger = logging.getLogger(constants.ROOT_LOGGER)

    # Retrieve collection metadata once at the beginning
    logger.info(
        f"Retrieving collection metadata for {configuration.auth_id}.{configuration.version}"
    )
    collection = get_collection_metadata(
        configuration.environment, configuration.auth_id, str(configuration.version)
    )
    logger.info(f"Successfully retrieved metadata for: {collection.entry_title}")

    # Validate collection once at the beginning
    errors = validate_collection_spatial(
        configuration, collection
    ) + validate_collection_temporal(configuration, collection)
    if errors:
        raise config.ValidationError(errors)

    # Ordered list of operations to perform on each granule
    # Use optimized operations that skip individual CMR calls
    operations = [
        lambda cfg, g: associate_collection(g, collection),
        prepare_granule,
        find_existing_ummg,
        create_ummg,
        stage_files if not configuration.dry_run else null_operation,
        create_cnm,
        write_cnm,
        publish_cnm if not configuration.dry_run else null_operation,
    ]

    # Bind the configuration to each operation
    configured_operations = [partial(fn, configuration) for fn in operations]

    # Wrap each operation with a 'recorder' function
    recorded_operations = [partial(recorder, fn) for fn in configured_operations]

    # The complete pipeline of actions initializes a Ledger, performs all the
    # operations, finalizes a Ledger, and logs the details of the Ledger.
    pipeline = rcompose(start_ledger, *recorded_operations, end_ledger, log_ledger)

    # Find all of the input granule files, limit the size of the list based
    # on the configuration, and execute the pipeline on each of the granules.
    candidate_granules = [
        Granule(
            name,
            data_filenames=data_files,
            browse_filenames=browse_files,
            premet_filename=premet_file,
            spatial_filename=spatial_file,
            reference_data_filename=reference_data_file,
            data_reader=data_reader(configuration.auth_id, reference_data_file),
        )
        for name, reference_data_file, data_files, browse_files, premet_file, spatial_file in grouped_granule_files(
            configuration
        )
    ]
    granules = take(configuration.number, candidate_granules)
    results = [pipeline(g) for g in granules]

    summarize_results(results)


def data_reader(
    auth_id: str, data_file: str
) -> Callable[[str, str, str, config.Config], dict]:
    """
    Determine which file reader to use for the given data file.
    """
    _, extension = os.path.splitext(data_file)

    try:
        return registry.lookup(auth_id, extension)
    except (KeyError, Exception):
        return generic.extract_metadata


# -------------------------------------------------------------------


def recorder(fn: Callable[[Granule], Granule], ledger: Ledger) -> Ledger:
    """
    Higher-order function that, given a granule operation function and a
    Ledger, will execute the function on the Ledger's granule, record the
    results, and return the resulting new Ledger.
    """
    successful = True
    message = ""
    start = dt.datetime.now()
    new_granule = None
    new_actions = ledger.actions.copy()
    fn_name = fn.func.__name__ if hasattr(fn, "func") else fn.__name__

    # If previous operation failed, bail out.
    if previous_failure(last(new_actions)):
        successful = False
        message = "Skipped due to earlier failures."

    else:
        # Execute the operation and record the result
        try:
            new_granule = fn(ledger.granule)
        except Exception as e:
            successful = False
            message = str(e)

    end = dt.datetime.now()

    # Store the result in the Ledger
    new_actions.append(
        Action(
            fn_name,
            successful=successful,
            message=message,
            startDatetime=start,
            endDatetime=end,
        )
    )

    return dataclasses.replace(
        ledger,
        granule=new_granule if new_granule else ledger.granule,
        actions=new_actions,
    )


def previous_failure(last_action: Action) -> bool:
    """
    Determine whether errors were raised during pipeline steps thus far.
    """
    return last_action is not None and not last_action.successful


def start_ledger(granule: Granule) -> Ledger:
    """
    Start a new Ledger of the operations on the given Granule.
    """
    return Ledger(granule, startDatetime=dt.datetime.now())


def end_ledger(ledger: Ledger) -> Ledger:
    """
    Finalize the Ledger of operations on its Granule.
    """
    return dataclasses.replace(
        ledger,
        endDatetime=dt.datetime.now(),
        successful=all([a.successful for a in ledger.actions]),
    )


# -------------------------------------------------------------------
# Granule Operations
# -------------------------------------------------------------------


def null_operation(_: config.Config, granule: Granule) -> Granule:
    return granule


def grouped_granule_files(configuration: config.Config) -> list[tuple]:
    """
    Identify file(s) related to each granule.
    """
    file_list = [p for p in Path(configuration.data_dir).glob("*")]
    premet_file_list = ancillary_files(
        configuration.premet_dir, [constants.PREMET_SUFFIX]
    )
    spatial_file_list = ancillary_files(
        configuration.spatial_dir, [constants.SPATIAL_SUFFIX, constants.SPO_SUFFIX]
    )

    return [
        granule_tuple(
            granule_key,
            configuration.granule_regex or f"({granule_key})",
            configuration.browse_regex,
            configuration.reference_file_regex,
            file_list,
            premet_file_list,
            spatial_file_list,
        )
        for granule_key in granule_keys(configuration, file_list)
    ]


def ancillary_files(dir: Path, suffixes: list) -> list:
    files = None

    if not dir:
        return files

    for suffix in suffixes:
        files = [p for p in Path(dir).glob(f"*{suffix}")]
        if files:
            break

    if not files:
        raise Exception(f"No files with suffix {suffixes} in directory {dir}.")

    return files


def granule_keys(configuration: config.Config, file_list: list[Path]) -> set[str]:
    if configuration.granule_regex:
        return granule_keys_from_regex(configuration.granule_regex, file_list)
    else:
        return granule_keys_from_filename(configuration.browse_regex, file_list)


def granule_keys_from_regex(granule_regex: str, file_list: list) -> set:
    """
    Identify granules based on a "granuleid" regex match group
    """
    pattern = re.compile(granule_regex)
    return {
        match.group("granuleid") for f in file_list if (match := pattern.search(f.name))
    }


def granule_keys_from_filename(browse_regex, file_list):
    """
    Identify granules based on unique data file basenames (minus file name
    extension) in lieu of a "granuleid" regex match group.
    """
    return set(
        os.path.splitext(file.name)[0]
        for file in file_list
        if not re.search(browse_regex, file.name)
    )


def granule_tuple(
    granule_key: str,
    granule_regex: str,
    browse_regex: str,
    reference_file_regex: str,
    file_list: list,
    premet_list: list,
    spatial_list: list,
) -> tuple:
    """
    Important! granule_regex argument must include a captured match group.

    Return a tuple representing a granule:
        - A string used as the "identifier" (in UMMG output) and "name" (in CNM output).
          This is the granule file name in the case of a single data file granule,
          otherwise the common name elements of all files related to a granule.
        - The name of the data file to use as the reference file
        - A set of one or more full paths to data file(s)
        - A set of zero or more full paths to associated browse file(s)
        - Path to an associated premet file (may be None or empty string)
        - Path to an associated spatial (or spo) file (may be None or empty string)
    """
    browse_file_paths = {
        str(file)
        for file in file_list
        if re.search(granule_key, file.name) and re.search(browse_regex, file.name)
    }

    data_file_paths = {
        str(file) for file in file_list if re.search(granule_key, file.name)
    } - browse_file_paths

    return (
        derived_granule_name(granule_regex, data_file_paths),
        reference_data_file(reference_file_regex, data_file_paths),
        data_file_paths,
        browse_file_paths,
        matched_ancillary_file(granule_key, premet_list),
        matched_ancillary_file(granule_key, spatial_list),
    )


def reference_data_file(regex: str, data_files: set[Path]):
    """
    Identify the file to use as the "reference" file for purposes of
    extracting granule metadata, in the case of a multi-science-file granule.
    """
    if not data_files:
        return None

    if len(data_files) == 1:
        return first(data_files)

    # Throw error if no regex and more than one data (science) file.
    if not regex and len(data_files) > 1:
        raise Exception(
            "Granule has multiple science files but reference_file_regex is not set."
        )

    # Error if regex matches more than one file
    if not one(lambda v: re.search(regex, v), data_files):
        raise Exception("reference_file_regex does not match exactly one science file.")

    return some(lambda v: re.search(regex, v), data_files)


def matched_ancillary_file(granule_key: str, file_list: list[Path]) -> str:
    if file_list is None:
        return None

    file_matches = [
        str(file) for file in file_list if re.search(granule_key, file.name)
    ]
    if not file_matches:
        return ""

    return first(file_matches)


def derived_granule_name(granule_regex: str, data_file_paths: set) -> str:
    a_file_path = first(data_file_paths)
    if a_file_path is None:
        return ""

    if len(data_file_paths) > 1:
        basename = os.path.basename(a_file_path)
        m = re.search(granule_regex, basename)
        return "".join(m.groups()) if m else ""
    else:
        return os.path.basename(a_file_path)


def associate_collection(granule: Granule, collection: CollectionMetadata) -> Granule:
    """
    Associate pre-fetched collection information with the Granule.

    This is used when collection metadata has been fetched once at the
    beginning of processing, avoiding repeated CMR calls.
    """
    return dataclasses.replace(granule, collection=collection)


def validate_collection(configuration: config.Config, granule: Granule) -> Granule:
    """
    Confirm collection metadata meet requirements for our granule metadata generation.
    """
    errors = validate_collection_spatial(
        configuration, granule.collection
    ) + validate_collection_temporal(configuration, granule.collection)
    if errors:
        raise config.ValidationError(errors)


def validate_collection_temporal(configuration, collection):
    """
    Verify collection temporal extent information is usable if a collection
    temporal override is requested.
    """

    if not configuration.collection_temporal_override:
        # No need to worry about the collection temporal extent content!
        return []

    # Show any errors generated when we extracted temporal information from UMM-C.
    if collection.temporal_extent_error:
        return [collection.temporal_extent_error]

    return []


def validate_collection_spatial(configuration, collection):
    """
    Ensure granule spatial representation exists, and verify the collection
    geometry can be used if a collection geometry override is requested.
    """
    errors = []

    # GranuleSpatialRepresentation must exist.
    if not collection.granule_spatial_representation:
        errors.append(
            f"{constants.GRANULE_SPATIAL_REP} not available in UMM-C metadata for {collection.short_name}.{collection.version}."
        )

    # If collection spatial extent is to be applied to granules, the spatial extent may
    # only contain one bounding rectangle, and the granule spatial representation must be cartesian
    if configuration.collection_geometry_override:
        if not collection.spatial_extent:
            errors.append("Collection must include a spatial extent.")

        elif len(collection.spatial_extent) > 1:
            errors.append(
                "Collection spatial extent must only contain one bounding rectangle when collection_geometry_override is set."
            )

        if collection.granule_spatial_representation != constants.CARTESIAN:
            errors.append(
                f"Collection {constants.GRANULE_SPATIAL_REP} must be {constants.CARTESIAN} when collection_geometry_override is set."
            )

    return errors


def prepare_granule(_: config.Config, granule: Granule) -> Granule:
    """
    Prepare the Granule for creating metadata and submitting it.
    """
    return dataclasses.replace(
        granule,
        submission_time=dt.datetime.now(dt.timezone.utc).isoformat(),
        uuid=str(uuid.uuid4()),
    )


def derived_ummg_filename(ummg_path: Path, granule_id: str) -> Path:
    return ummg_path.joinpath(granule_id + ".json")


def find_existing_ummg(configuration: config.Config, granule: Granule) -> Granule:
    ummg_filename = derived_ummg_filename(
        configuration.ummg_path(), granule.producer_granule_id
    )

    if ummg_filename.exists():
        return dataclasses.replace(granule, ummg_filename=ummg_filename)
    else:
        return granule


def create_ummg(configuration: config.Config, granule: Granule) -> Granule:
    """
    Create the UMM-G file for the Granule.
    """
    # Return if we are not overwriting UMM-G and it already exists.
    if granule.ummg_filename != Maybe.empty and not configuration.overwrite_ummg:
        return granule

    ummg_file_path = derived_ummg_filename(
        configuration.ummg_path(), granule.producer_granule_id
    )

    gsr = granule.collection.granule_spatial_representation

    # Get premet content if it exists.
    premet_content = utilities.premet_values(granule.premet_filename)
    temporal_content = utilities.external_temporal_values(
        configuration.collection_temporal_override, premet_content, granule
    )

    # Get spatial coverage from spatial file if it exists
    spatial_content = utilities.external_spatial_values(
        configuration.collection_geometry_override, gsr, granule
    )

    # Populated summary dict looks like:
    # {
    #     'size_in_bytes' => integer representing the sum of the sizes of
    #                        *all* data files associated with the granule,
    #     'production_date_time'  => iso datetime string,
    #     'temporal' => an array of one (data represent a single point in time)
    #                   or two (data cover a time range) datetime strings
    #     'geometry' => an array of {'Longitude': x, 'Latitude': y} dicts
    # }

    summary = {
        "size_in_bytes": granule.size(),
        "production_date_time": granule.submission_time,
    } | granule.data_reader(
        granule.reference_data_filename,
        temporal_content,
        spatial_content,
        configuration,
        gsr,
    )

    summary["spatial_extent"] = populate_spatial(
        gsr, summary["geometry"], configuration, spatial_content
    )
    summary["temporal_extent"] = populate_temporal(summary["temporal"])
    summary["additional_attributes"] = populate_additional_attributes(
        premet_content, constants.UMMG_ADDITIONAL_ATTRIBUTES
    )
    summary["platforms"] = populate_additional_attributes(
        premet_content, constants.UMMG_PLATFORM
    )
    summary["ummg_schema_version"] = constants.UMMG_JSON_SCHEMA_VERSION

    # Populate the body template
    body = ummg_body_template().safe_substitute(
        dataclasses.asdict(granule) | dataclasses.asdict(granule.collection) | summary
    )

    # Save it all in a file.
    with open(ummg_file_path, "tw") as f:
        print(body, file=f)

    return dataclasses.replace(granule, ummg_filename=ummg_file_path)


def stage_files(configuration: config.Config, granule: Granule) -> Granule:
    """
    Stage a set of files for the Granule in S3.
    """
    all_filenames = concat(
        granule.data_filenames, {granule.ummg_filename}, granule.browse_filenames
    )
    for fn in all_filenames:
        filename = os.path.basename(fn)
        bucket_path = s3_object_path(granule, filename)
        with open(fn, "rb") as f:
            aws.stage_file(configuration.staging_bucket_name, bucket_path, file=f)

    return granule


def create_cnm(configuration: config.Config, granule: Granule) -> Granule:
    """
    Create a CNM submission message for the Granule.
    """
    files_template = cnms_files_template()
    body_template = cnms_body_template()
    populated_file_templates = []

    granule_files = {
        "data": granule.data_filenames,
        "metadata": [granule.ummg_filename],
        "browse": granule.browse_filenames,
    }
    for type, files in granule_files.items():
        for file in files:
            populated_file_templates.append(
                json.loads(
                    files_template.safe_substitute(
                        cnms_file_json_parts(
                            configuration.staging_bucket_name, granule, file, type
                        )
                    )
                )
            )

    return dataclasses.replace(
        granule,
        cnm_message=body_template.safe_substitute(
            dataclasses.asdict(granule)
            | dataclasses.asdict(granule.collection)
            | dataclasses.asdict(configuration)
            | {
                "file_content": json.dumps(populated_file_templates),
                "cnm_schema_version": constants.CNM_JSON_SCHEMA_VERSION,
            }
        ),
    )


def write_cnm(configuration: config.Config, granule: Granule) -> Granule:
    """
    Write a CNM message to a file.
    """
    if configuration.write_cnm_file:
        cnm_file = configuration.cnm_path().joinpath(
            granule.producer_granule_id + ".cnm.json"
        )
        with open(cnm_file, "tw") as f:
            print(granule.cnm_message, file=f)
    return granule


def publish_cnm(configuration: config.Config, granule: Granule) -> Granule:
    """
    Publish a CNM message to a Kinesis stream.
    """
    stream_name = configuration.kinesis_stream_name
    aws.post_to_kinesis(stream_name, granule.cnm_message)
    return granule


# -------------------------------------------------------------------
# Logging functions
# -------------------------------------------------------------------


def log_ledger(ledger: Ledger) -> Ledger:
    """Log a Ledger of the operations performed on a Granule."""
    logger = logging.getLogger(constants.ROOT_LOGGER)
    logger.info("")
    logger.info(f"Granule: {ledger.granule.producer_granule_id}")
    logger.info(f"  * UUID           : {ledger.granule.uuid}")
    logger.info(f"  * Submission time: {ledger.granule.submission_time}")
    logger.info(f"  * Start          : {ledger.startDatetime}")
    logger.info(f"  * End            : {ledger.endDatetime}")
    logger.info(f"  * Successful     : {ledger.successful}")
    logger.debug("  * Actions:")
    for a in ledger.actions:
        logger.debug(f"      + Name: {a.name}")
        logger.debug(f"        Start     : {a.startDatetime}")
        logger.debug(f"        End       : {a.endDatetime}")
        logger.debug(f"        Successful: {a.successful}")
        if not a.successful:
            logger.debug(f"        Reason    : {a.message}")
    return ledger


def summarize_results(ledgers: list[Ledger]) -> None:
    """
    Log a summary of the operations performed on all Granules.
    """
    successful_count = len(list(filter(lambda r: r.successful, ledgers)))
    failed_count = len(list(filter(lambda r: not r.successful, ledgers)))
    if len(ledgers) > 0:
        start = ledgers[0].startDatetime
        end = ledgers[-1].endDatetime
    else:
        start = dt.datetime.now()
        end = dt.datetime.now()

    logger = logging.getLogger(constants.ROOT_LOGGER)
    logger.info("Processing Summary")
    logger.info("==================")
    logger.info(f"Granules  : {len(ledgers)}")
    logger.info(f"Start     : {start}")
    logger.info(f"End       : {end}")
    logger.info(f"Successful: {successful_count}")
    logger.info(f"Failed    : {failed_count}")


# -------------------------------------------------------------------
# Utility functions
# -------------------------------------------------------------------


def cnms_file_json_parts(staging_bucket_name, granule, file, file_type):
    file_mapping = dict()
    file_name = os.path.basename(file)
    file_mapping["file_size"] = os.path.getsize(file)
    file_mapping["file_type"] = file_type
    file_mapping["checksum"] = checksum(file)
    file_mapping["file_name"] = file_name
    file_mapping["staging_uri"] = s3_url(staging_bucket_name, granule, file_name)

    return file_mapping


def s3_url(staging_bucket_name, granule, filename):
    """
    Returns the full s3 URL for the given file name.
    """
    object_path = s3_object_path(granule, filename)
    return f"s3://{staging_bucket_name}/{object_path}"


def s3_object_path(granule, filename):
    """
    Returns the full s3 object path for the granule
    """
    prefix = Template("external/${auth_id}/${version}/${uuid}/").safe_substitute(
        {
            "auth_id": granule.collection.short_name,
            "version": granule.collection.version,
            "uuid": granule.uuid,
        }
    )
    return prefix + filename


def checksum(file):
    BUF_SIZE = 65536
    sha256 = hashlib.sha256()
    with open(file, "rb") as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha256.update(data)

    return sha256.hexdigest()


def populate_spatial(
    spatial_representation: str,
    spatial_values: list,
    configuration: config.Config = None,
    spatial_content: list = None,
) -> str:
    """
    Return a string representation of a geometry (point, bounding box, gpolygon)
    Optionally generates optimized polygons when spatial files are present.
    """
    # Check if we should generate polygons for spatial file data
    if (
        configuration is not None
        and configuration.spatial_polygon_enabled
        and spatial_content is not None
        and spatial_representation == constants.GEODETIC
        and len(spatial_values) >= 3
    ):
        try:
            # Create configured polygon generator using partial application
            generate_polygon = partial(
                create_flightline_polygon,
                target_coverage=configuration.spatial_polygon_target_coverage,
                max_vertices=configuration.spatial_polygon_max_vertices,
                cartesian_tolerance=configuration.spatial_polygon_cartesian_tolerance,
            )

            # Extract lon/lat arrays from spatial_values
            lons = [point["Longitude"] for point in spatial_values]
            lats = [point["Latitude"] for point in spatial_values]

            # Generate polygon using our configured spatial module
            polygon, metadata = generate_polygon(lons, lats)

            if polygon is not None:
                # Convert shapely polygon to UMM-G format
                coords = list(polygon.exterior.coords)
                polygon_points = [
                    {"Longitude": float(lon), "Latitude": float(lat)}
                    for lon, lat in coords
                ]

                # Use the existing template system
                return ummg_spatial_gpolygon_template().safe_substitute(
                    {"points": json.dumps(polygon_points)}
                )

        except Exception as e:
            # If polygon generation fails, fall back to original behavior
            import logging

            logger = logging.getLogger(constants.ROOT_LOGGER)
            logger.warning(
                f"Polygon generation failed, using original spatial processing: {e}"
            )

    # Original behavior for all other cases
    match spatial_representation:
        case constants.CARTESIAN:
            return populate_bounding_rectangle(spatial_values)

        case constants.GEODETIC:
            return populate_point_or_polygon(spatial_values)

        case _:
            raise Exception("Unknown granule spatial representation.")


def populate_bounding_rectangle(spatial_values):
    """
    Return a string representation of a bounding rectangle
    """
    # Only two points representing (UL, LR) of a rectangle are allowed.
    if len(spatial_values) == 2:
        return ummg_spatial_rectangle_template().safe_substitute(
            {
                "west": spatial_values[0]["Longitude"],
                "north": spatial_values[0]["Latitude"],
                "east": spatial_values[1]["Longitude"],
                "south": spatial_values[1]["Latitude"],
            }
        )
    else:
        raise Exception(
            "Cartesian granule spatial representation only supports two points for a bounding rectangle."
        )


def populate_point_or_polygon(spatial_values):
    """
    Return a string representation of a point or polygon, based on the length
    of the spatial_values list.
    """
    template = ummg_spatial_gpolygon_template

    if len(spatial_values) == 1:
        template = ummg_spatial_point_template
    elif len(spatial_values) < 4:
        raise Exception("Closed polygon requires at least four points.")

    return template().safe_substitute({"points": json.dumps(spatial_values)})


def populate_temporal(datetime_values):
    """
    Return a string representation of a temporal range or single value, as appropriate.
    """
    if isinstance(datetime_values[0], dict):
        return ummg_temporal_range_template().safe_substitute(
            {"date_time_range": json.dumps(datetime_values[0])}
        )
    else:
        return ummg_temporal_single_template().safe_substitute(
            {"date_time": datetime_values[0]}
        )


def populate_additional_attributes(premet_content, ummg_key):
    """
    Return a string representation of any additional attributes or platform information
    found in a premet file.
    """
    if premet_content is None:
        return ""

    if ummg_key in premet_content:
        # This is set up as a generic key-value output in the template so the same template
        # can be used for additional attributes and platforms.
        # TODO: Should the "populate" methods be in utilities, not here?
        return ummg_additional_attributes_template().safe_substitute(
            {
                "key": ummg_key,
                "attributes": json.dumps(premet_content[ummg_key]),
            }
        )

    return ""


def ummg_body_template():
    return initialize_template(constants.UMMG_BODY_TEMPLATE)


def ummg_temporal_single_template():
    return initialize_template(constants.UMMG_TEMPORAL_SINGLE_TEMPLATE)


def ummg_temporal_range_template():
    return initialize_template(constants.UMMG_TEMPORAL_RANGE_TEMPLATE)


def ummg_spatial_gpolygon_template():
    return initialize_template(constants.UMMG_SPATIAL_GPOLYGON_TEMPLATE)


def ummg_spatial_rectangle_template():
    return initialize_template(constants.UMMG_SPATIAL_RECTANGLE_TEMPLATE)


def ummg_spatial_point_template():
    return initialize_template(constants.UMMG_SPATIAL_POINT_TEMPLATE)


def ummg_additional_attributes_template():
    return initialize_template(constants.UMMG_ADDITIONAL_ATTRIBUTES_TEMPLATE)


def cnms_body_template():
    return initialize_template(constants.CNM_BODY_TEMPLATE)


def cnms_files_template():
    return initialize_template(constants.CNM_FILES_TEMPLATE)


def _open_text(anchor, name):
    for t in importlib.resources.files(anchor).iterdir():
        if t.name == name:
            return t.read_text()
    return None


def initialize_template(resource_location):
    return Template(_open_text(*resource_location))


def validate(configuration, content_type):
    """
    Validate local CNM or UMM-G (JSON) files
    """
    output_file_path = file_type_path(configuration, content_type)
    schema_resource_location, dummy_json = schema_file_path(content_type)

    logger = logging.getLogger(constants.ROOT_LOGGER)
    logger.info("")
    logger.info(f"Validating files in {output_file_path}...")

    schema = json.loads(_open_text(*schema_resource_location))
    # loop through all files and validate each one
    for json_file in output_file_path.glob("*.json"):
        apply_schema(schema, json_file, dummy_json)

    logger.info("Validations complete.")
    return True


def file_type_path(configuration, content_type):
    """
    Return directory containing JSON files to be validated.
    """
    match content_type:
        case "cnm":
            return configuration.cnm_path()
        case "ummg":
            return configuration.ummg_path()
        case _:
            return ""


def schema_file_path(content_type):
    """
    Identify the schema to be used for validation
    """
    dummy_json = dict()
    match content_type:
        case "cnm":
            return constants.CNM_JSON_SCHEMA, dummy_json
        case "ummg":
            # We intentionally create UMM-G output with a couple of parts missing,
            # so we need to fill in the gaps with dummy values during validation.
            dummy_json["ProviderDates"] = [{"Date": "2000", "Type": "Create"}]
            dummy_json["GranuleUR"] = "FakeUR"
            return constants.UMMG_JSON_SCHEMA, dummy_json
        case _:
            return "", {}


def apply_schema(schema, json_file, dummy_json):
    """
    Apply JSON schema to generated JSON content.
    """
    logger = logging.getLogger(constants.ROOT_LOGGER)
    with open(json_file) as jf:
        json_content = json.load(jf)
        try:
            jsonschema.validate(instance=json_content | dummy_json, schema=schema)
            logger.info(f"No validation errors: {json_file}")
        except ValidationError as err:
            logger.error(
                f"""Validation failed for "{err.validator}"\
                in {json_file}: {err.validator_value}"""
            )

    return True
