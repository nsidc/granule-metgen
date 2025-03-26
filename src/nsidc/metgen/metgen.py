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
from functools import cache
from pathlib import Path
from string import Template
from typing import Optional

import earthaccess
import jsonschema
from earthaccess.exceptions import LoginAttemptFailure, LoginStrategyUnavailable
from funcy import all, filter, first, notnone, partial, rcompose, take
from pyfiglet import Figlet
from returns.maybe import Maybe
from rich.prompt import Confirm, Prompt

from nsidc.metgen import aws, config, constants, csv_reader, netcdf_reader

# -------------------------------------------------------------------
CONSOLE_FORMAT = "%(message)s"
LOGFILE_FORMAT = "%(asctime)s|%(levelname)s|%(name)s|%(message)s"

# -------------------------------------------------------------------
# Top-level functions which expose operations to the CLI
# -------------------------------------------------------------------


def init_logging(configuration: config.Config):
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
            default=constants.DEFAULT_WRITE_CNM_FILE,
        ),
    )
    cfg_parser.set(
        constants.DESTINATION_SECTION_NAME,
        "overwrite_ummg",
        Prompt.ask(
            "Overwrite existing UMM-G files? (True/False)",
            default=constants.DEFAULT_OVERWRITE_UMMG,
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
class Collection:
    """
    Collection metadata relevant to generating UMM-G content

    spatial_extent and temporal_extent currently contain the relevant
    JSON structure from the collection metadata (if it exists).
    Additional work is still needed to parse out the relevant fields.
    """

    auth_id: str
    version: int
    spatial_extent: Optional[dict] = None
    temporal_extent: Optional[dict] = None


@dataclasses.dataclass
class Granule:
    """Granule to ingest"""

    producer_granule_id: str
    collection: Maybe[Collection] = Maybe.empty
    data_filenames: list[str] = dataclasses.field(default_factory=list)
    browse_filenames: list[str] = dataclasses.field(default_factory=list)
    ummg_filename: Maybe[str] = Maybe.empty
    submission_time: Maybe[str] = Maybe.empty
    uuid: Maybe[str] = Maybe.empty
    cnm_message: Maybe[str] = Maybe.empty
    data_reader: Callable[[str], dict] = Maybe.empty


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

    # Ordered list of operations to perform on each granule
    operations = [
        granule_collection,
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
            data_reader=data_reader(data_files),
        )
        for name, data_files, browse_files in grouped_granule_files(configuration)
    ]
    granules = take(configuration.number, candidate_granules)
    results = [pipeline(g) for g in granules]

    summarize_results(results)


def data_reader(data_files: list[str]) -> Callable[[str], dict]:
    """
    Determine which file reader to use for the given data files. This currently
    is limited to handling one data file type, and one reader. In a future
    issue, we may handle granules with multiple data file types per granule.
    In that future work this needs to be refactored to handle this case.
    """
    readers = {
        ".nc": netcdf_reader.extract_metadata,
        ".csv": csv_reader.extract_metadata,
    }

    _, extension = os.path.splitext(data_files[0])

    return readers[extension]


# -------------------------------------------------------------------


def recorder(fn: Callable[[Granule], Granule], ledger: Ledger) -> Ledger:
    """
    Higher-order function that, given a granule operation function and a
    Ledger, will execute the function on the Ledger's granule, record the
    results, and return the resulting new Ledger.
    """
    # Execute the operation and record the result
    successful = True
    message = ""
    start = dt.datetime.now()
    new_granule = None
    try:
        new_granule = fn(ledger.granule)
    except Exception as e:
        successful = False
        message = str(e)
    end = dt.datetime.now()

    # Store the result in the Ledger
    new_actions = ledger.actions.copy()
    fn_name = fn.func.__name__ if hasattr(fn, "func") else fn.__name__
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


def null_operation(configuration: config.Config, granule: Granule) -> Granule:
    return granule


def edl_login(environment):
    """
    Authenticate with Earthdata using user name and password retrieved
    from environment variables.
    """

    logger = logging.getLogger(constants.ROOT_LOGGER)
    try:
        earthaccess.login(
            strategy="environment", system=getattr(earthaccess, environment)
        )
        auth = True
    except LoginStrategyUnavailable:
        logger.info(
            "Environment variables EARTHDATA_USERNAME and EARTHDATA_PASSWORD \
are missing."
        )
        auth = False
    except LoginAttemptFailure as e:
        logger.info(e)
        auth = False

    return auth


def ummc_content(umm: list, key: str):
    val = None

    if not umm:
        return val

    # if more than one response, log error, use first one?
    if not isinstance(umm[0], dict):
        return val

    logger = logging.getLogger(constants.ROOT_LOGGER)
    try:
        val = umm[0]["umm"][key]
        logger.info(f"Found {key} information in umm-c response from CMR.")
    except KeyError:
        logger.info(f"No {key} information in umm-c response from CMR.")

    return val


def edl_environment(environment):
    """
    Map a cumulus ingest environment to the environment string needed for
    Earthdata login via earthaccess.
    """
    if environment.lower() != "prod":
        environment = "uat"

    return environment.upper()


def edl_provider(environment):
    return (
        constants.CMR_PROD_PROVIDER
        if environment.lower() == "prod"
        else constants.CMR_UAT_PROVIDER
    )


@cache
def collection_from_cmr(environment: str, auth_id: str, version: int):
    """
    Retrieve collection metadata in UMM-C format if it exists.
    """

    logger = logging.getLogger(constants.ROOT_LOGGER)

    # Setting has_granules to None should find collections both with and
    # without associated granules.
    if edl_login(edl_environment(environment)):
        logger.info("Earthdata login succeeded.")
        ummc = earthaccess.search_datasets(
            short_name=auth_id,
            version=version,
            has_granules=None,
            provider=edl_provider(environment),
        )
    else:
        logger.info("Earthdata login failed, UMM-C metadata will not be used.")
        ummc = []

    # FYI: data format (e.g. NetCDF) is available in the umm-c response in
    # ArchiveAndDistributionInformation should we decide to use it.
    return Collection(
        auth_id,
        version,
        ummc_content(ummc, "SpatialExtent"),
        ummc_content(ummc, "TemporalExtents"),
    )


def grouped_granule_files(configuration: config.Config) -> list[tuple]:
    """
    Identify data file(s) and browse file(s) related to each granule.
    """
    file_list = [p for p in Path(configuration.data_dir).glob("*")]
    granule_keys = find_granule_keys(configuration, file_list)

    return [
        granule_tuple(
            granule_key,
            configuration.granule_regex or f"({granule_key})",
            configuration.browse_regex,
            file_list,
        )
        for granule_key in granule_keys
    ]


def find_granule_keys(configuration: config.Config, file_list: list[Path]) -> set[str]:
    if configuration.granule_regex:
        return granule_keys_from_regex(configuration.granule_regex, file_list)
    else:
        return granule_keys_from_filename(configuration.browse_regex, file_list)


def granule_keys_from_regex(granule_regex: str, file_list: list) -> set:
    """
    Identify granules based on a "granuleid" regex match group
    """
    pipeline = rcompose(
        partial(re.search, granule_regex),
        lambda match: match.group("granuleid") if match is not None else None,
    )
    results = [pipeline(f.name) for f in file_list]
    return set(filter(notnone, results))


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
    granule_key: str, granule_regex: str, browse_regex: str, file_list: list
) -> tuple:
    """
    Important! granule_regex argument must include a captured match group

    Return a tuple representing a granule:
        - A string used as the "identifier" (in UMMG output) and "name" (in CNM output).
          This is the granule file name in the case of a single data file granule,
          otherwise the common name elements of all files related to a granule.
        - A set of one or more full paths to data file(s)
        - A set of zero or more full paths to associated browse file(s)
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
        data_file_paths,
        browse_file_paths,
    )


def derived_granule_name(granule_regex: str, data_file_paths: set) -> str:
    a_file_path = first(data_file_paths)
    if a_file_path is None:
        return ""
    print("*** " + a_file_path)

    if len(data_file_paths) > 1:
        m = re.search(granule_regex, a_file_path)
        return "".join(m.groups()) if m else ""
    else:
        return os.path.basename(a_file_path)


def granule_collection(configuration: config.Config, granule: Granule) -> Granule:
    """
    Associate collection information with the Granule.
    """
    return dataclasses.replace(
        granule,
        collection=collection_from_cmr(
            configuration.environment, configuration.auth_id, configuration.version
        ),
    )


def prepare_granule(configuration: config.Config, granule: Granule) -> Granule:
    """
    Prepare the Granule for creating metadata and submitting it.
    """
    return dataclasses.replace(
        granule,
        submission_time=dt.datetime.now(dt.timezone.utc).isoformat(),
        uuid=str(uuid.uuid4()),
    )


def find_existing_ummg(configuration: config.Config, granule: Granule) -> Granule:
    ummg_filename = configuration.ummg_path().joinpath(
        granule.producer_granule_id + ".json"
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

    ummg_file_path = configuration.ummg_path().joinpath(
        granule.producer_granule_id + ".json"
    )

    # Populated metadata_details dict looks like:
    # {
    #   data_file: {
    #       'size_in_bytes' => integer,
    #       'production_date_time'  => iso datetime string,
    #       'temporal' => an array of one (data represent a single point in time)
    #                     or two (data cover a time range) datetime strings
    #       'geometry' => { 'points': a string representation of one or more
    #                                 lat/lon pairs }
    #   }
    # }
    metadata_details = {}
    for data_file in granule.data_filenames:
        metadata_details[data_file] = granule.data_reader(data_file, configuration)

    # Collapse information about (possibly) multiple files into a granule summary.
    summary = metadata_summary(metadata_details)
    summary["spatial_extent"] = populate_spatial(summary["geometry"])
    summary["temporal_extent"] = populate_temporal(summary["temporal"])
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
    stuff = granule.data_filenames + [granule.ummg_filename] + granule.browse_filenames
    for fn in stuff:
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
            "auth_id": granule.collection.auth_id,
            "version": granule.collection.version,
            "uuid": granule.uuid,
        }
    )
    return prefix + filename


# size is a sum of all associated data file sizes.
# all other attributes use the values from the first data file entry.
def metadata_summary(details):
    default = list(details.values())[0]

    return {
        "size_in_bytes": sum([x["size_in_bytes"] for x in details.values()]),
        "production_date_time": default["production_date_time"],
        "temporal": default["temporal"],
        "geometry": default["geometry"],
    }


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


# TODO: Use the GranuleSpatialRepresentation value in the collection metadata
# to determine the expected spatial type. See Issue #15. For now, use either
# GPolygon or Points, depending on how many points are in the spatial values.
def populate_spatial(spatial_values):
    # spatial_values is a dict suitable for use in template substitution, like:
    # { 'points': string representation of an array of {lon: lat:} dicts }
    if len(spatial_values["points"]) == 1:
        return ummg_spatial_point_template().safe_substitute(
            {"points": json.dumps(spatial_values["points"])}
        )

    # Default is a polygon
    return ummg_spatial_gpolygon_template().safe_substitute(
        {"points": json.dumps(spatial_values["points"])}
    )


def populate_temporal(datetime_values):
    if len(datetime_values) > 1:
        return ummg_temporal_range_template().safe_substitute(
            {"begin_date_time": datetime_values[0], "end_date_time": datetime_values[1]}
        )
    else:
        return ummg_temporal_single_template().safe_substitute(
            {"date_time": datetime_values[0]}
        )


def ummg_body_template():
    return initialize_template(constants.UMMG_BODY_TEMPLATE)


def ummg_temporal_single_template():
    return initialize_template(constants.UMMG_TEMPORAL_SINGLE_TEMPLATE)


def ummg_temporal_range_template():
    return initialize_template(constants.UMMG_TEMPORAL_RANGE_TEMPLATE)


def ummg_spatial_gpolygon_template():
    return initialize_template(constants.UMMG_SPATIAL_GPOLYGON_TEMPLATE)


def ummg_spatial_point_template():
    return initialize_template(constants.UMMG_SPATIAL_POINT_TEMPLATE)


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
        except jsonschema.exceptions.ValidationError as err:
            logger.error(
                f"""Validation failed for "{err.validator}"\
                in {json_file}: {err.validator_value}"""
            )

    return True
