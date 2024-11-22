import configparser
import dataclasses
import datetime as dt
import hashlib
from importlib.resources import open_text
import json
import jsonschema
import logging
import os.path
import sys
from typing import Callable
from pathlib import Path
from string import Template
import uuid

from funcy import all, filter, partial, rcompose, take
from pyfiglet import Figlet
from returns.maybe import Maybe
from rich.prompt import Confirm, Prompt

from nsidc.metgen import aws
from nsidc.metgen import config
from nsidc.metgen import constants
from nsidc.metgen import netcdf_reader


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
    logger = logging.getLogger('metgenc')
    logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    logger.addHandler(console_handler)

    logfile_handler = logging.FileHandler("metgenc.log", "a")
    logfile_handler.setLevel(logging.DEBUG)
    logfile_handler.setFormatter(logging.Formatter(LOGFILE_FORMAT))
    logger.addHandler(logfile_handler)

def banner():
    """
    Displays the name of this utility using incredible ASCII-art.
    """
    f = Figlet(font='slant')
    return f.renderText('metgenc')

# TODO require a non-blank input for elements that have no default value
def init_config(configuration_file):
    """
    Prompts the user for configuration values and then creates a valid configuration file.
    """
    print("""This utility will create a granule metadata configuration file by prompting """
          """you for values for each of the configuration parameters.""")
    print()
    # prompt for config file name if it's not provided
    if not configuration_file:
        configuration_file = Prompt.ask("configuration file name", default="example.ini")
        # TODO check file name is safe
    else:
        print(f'Creating configuration file {configuration_file}')
        print()

    if (os.path.exists(configuration_file)):
        print(f'WARNING: The {configuration_file} already exists.')
        overwrite = Confirm.ask("Overwrite?")
        if not overwrite:
            print('Not overwriting existing file. Exiting.')
            exit(1)

    cfg_parser = configparser.ConfigParser()

    print()
    print(f'{constants.SOURCE_SECTION_NAME} Data Parameters')
    print('--------------------------------------------------')
    cfg_parser.add_section(constants.SOURCE_SECTION_NAME)
    cfg_parser.set(constants.SOURCE_SECTION_NAME, "data_dir", Prompt.ask("Data directory", default="data"))
    print()

    print()
    print(f'{constants.COLLECTION_SECTION_NAME} Parameters')
    print('--------------------------------------------------')
    cfg_parser.add_section(constants.COLLECTION_SECTION_NAME)
    cfg_parser.set(constants.COLLECTION_SECTION_NAME, "auth_id", Prompt.ask("Authoritative ID"))
    cfg_parser.set(constants.COLLECTION_SECTION_NAME, "version", Prompt.ask("Version"))
    cfg_parser.set(constants.COLLECTION_SECTION_NAME, "provider", Prompt.ask("Provider"))
    print()

    print()
    print(f'{constants.DESTINATION_SECTION_NAME} Parameters')
    print('--------------------------------------------------')
    cfg_parser.add_section(constants.DESTINATION_SECTION_NAME)
    cfg_parser.set(constants.DESTINATION_SECTION_NAME, "local_output_dir", Prompt.ask("Local output directory", default="output"))
    cfg_parser.set(constants.DESTINATION_SECTION_NAME, "ummg_dir", Prompt.ask("Local UMM-G output directory (relative to local output directory)", default="ummg"))
    cfg_parser.set(constants.DESTINATION_SECTION_NAME, "kinesis_stream_name", Prompt.ask("Kinesis stream name", default=constants.DEFAULT_STAGING_KINESIS_STREAM))
    cfg_parser.set(constants.DESTINATION_SECTION_NAME, "staging_bucket_name", Prompt.ask("Cumulus s3 bucket name", default=constants.DEFAULT_STAGING_BUCKET_NAME))
    cfg_parser.set(constants.DESTINATION_SECTION_NAME, "write_cnm_file", Prompt.ask("Write CNM messages to files? (True/False)", default=constants.DEFAULT_WRITE_CNM_FILE))
    cfg_parser.set(constants.DESTINATION_SECTION_NAME, "overwrite_ummg", Prompt.ask("Overwrite existing UMM-G files? (True/False)", default=constants.DEFAULT_OVERWRITE_UMMG))

    print()
    print(f'{constants.SETTINGS_SECTION_NAME} Parameters')
    print('--------------------------------------------------')
    cfg_parser.add_section(constants.SETTINGS_SECTION_NAME)
    cfg_parser.set(constants.SETTINGS_SECTION_NAME, "checksum_type", Prompt.ask("Checksum type", default=constants.DEFAULT_CHECKSUM_TYPE))

    print()
    print(f'Saving new configuration: {configuration_file}')
    with open(configuration_file, "tw") as file:
        cfg_parser.write(file)

    return configuration_file

def prepare_output_dirs(configuration):
    """
    Generate paths to ummg and cnm output directories.
    Remove any existing UMM-G files if needed.
    TODO: create local_output_dir, ummg_dir, and cnm subdir if they don't exist
    """
    ummg_path = Path(configuration.local_output_dir, configuration.ummg_dir)
    cnm_path = Path(configuration.local_output_dir, 'cnm')

    if configuration.overwrite_ummg:
        scrub_json_files(ummg_path)

    return (ummg_path, cnm_path)

def scrub_json_files(path):
    print(f'Removing existing files in {path}')
    for file_path in path.glob('*.json'):
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
        except Exception as e:
            print('Failed to delete %s: %s' % (file_path, e))

# -------------------------------------------------------------------
# Data structures for processing Granules and recording results
# -------------------------------------------------------------------

@dataclasses.dataclass
class Collection:
    """Collection info required to ingest a granule"""
    auth_id: str
    version: int

@dataclasses.dataclass
class Granule:
    """Granule to ingest"""
    producer_granule_id: str
    collection: Maybe[Collection] = Maybe.empty
    data_filenames: list[str] = dataclasses.field(default_factory=list)
    ummg_filename: Maybe[str] = Maybe.empty
    submission_time: Maybe[str] = Maybe.empty
    uuid: Maybe[str] = Maybe.empty
    cnm_message: Maybe[str] = Maybe.empty

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
            stage_files,
            create_cnm,
            write_cnm,
            publish_cnm,
        ]

    # Bind the configuration to each operation
    configured_operations = [partial(fn, configuration) for fn in operations]

    # Wrap each operation with a 'recorder' function
    recorded_operations = [partial(recorder, fn) for fn in configured_operations]

    # The complete pipeline of actions initializes a Ledger, performs all the
    # operations, finalizes a Ledger, and logs the details of the Ledger.
    pipeline = rcompose(
        start_ledger, 
        *recorded_operations, 
        end_ledger, 
        log_ledger
    )

    # Find all of the input granule files, limit the size of the list based
    # on the configuration, and execute the pipeline on each of the granules.
    candidate_granules = [Granule(p.name, data_filenames=[str(p)])
                          for p in Path(configuration.data_dir).glob('*.nc')]
    granules = take(configuration.number, candidate_granules)
    results = [pipeline(g) for g in granules]

    summarize_results(results)

# -------------------------------------------------------------------

def recorder(fn: Callable[[Granule], Granule], ledger: Ledger) -> Ledger:
    """
    Higher-order function that, given a granule operation function and a
    Ledger, will execute the function on the Ledger's granule, record the
    results, and return the resulting new Ledger.
    """
    # Execute the operation and record the result
    successful = True
    message = ''
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
    fn_name = fn.func.__name__ if hasattr(fn, 'func') else fn.__name__
    new_actions.append(
        Action(
            fn_name,
            successful=successful,
            message=message,
            startDatetime=start,
            endDatetime=end
        )
    )

    return dataclasses.replace(
        ledger,
        granule=new_granule if new_granule else ledger.granule,
        actions=new_actions
    )

def start_ledger(granule: Granule) -> Ledger:
    """
    Start a new Ledger of the operations on the given Granule.
    """
    return Ledger(
        granule,
        startDatetime=dt.datetime.now()
    )

def end_ledger(ledger: Ledger) -> Ledger:
    """
    Finalize the Ledger of operations on its Granule.
    """
    return dataclasses.replace(
        ledger,
        endDatetime=dt.datetime.now(),
        successful=all([a.successful for a in ledger.actions])
    )

# -------------------------------------------------------------------
# Granule Operations
# -------------------------------------------------------------------

def granule_collection(configuration: config.Config, granule: Granule) -> Granule:
    """
    Find the Granule's Collection and add it to the Granule.
    """
    # TODO: When we start querying CMR, refactor the pipeline to retrieve
    # collection information from CMR once, then associate it with each
    # granule.
    return dataclasses.replace(
        granule, 
        collection=Collection(configuration.auth_id, configuration.version)
    )

def prepare_granule(configuration: config.Config, granule: Granule) -> Granule:
    """
    Prepare the Granule for creating metadata and submitting it.
    """
    return dataclasses.replace(
        granule, 
        submission_time=dt.datetime.now(dt.timezone.utc).isoformat(),
        uuid=str(uuid.uuid4())
    )

def find_existing_ummg(configuration: config.Config, granule: Granule) -> Granule:
    ummg_filename = configuration.ummg_path().joinpath(granule.producer_granule_id + '.json')

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

    ummg_file_path = configuration.ummg_path().joinpath(granule.producer_granule_id + '.json')

    # Populated metadata_details dict looks like:
    # {
    #   data_file: {
    #       'size_in_bytes' => integer,
    #       'production_date_time'  => iso datetime string,
    #       'temporal' => an array of one (data represent a single point in time)
    #                     or two (data cover a time range) datetime strings
    #       'geometry' => { 'points': a string representation of one or more lat/lon pairs }
    #   }
    # }
    metadata_details = {}
    for data_file in granule.data_filenames:
        metadata_details[data_file] = netcdf_reader.extract_metadata(data_file)

    # Collapse information about (possibly) multiple files into a granule summary.
    summary = metadata_summary(metadata_details)
    summary['spatial_extent'] = populate_spatial(summary['geometry'])
    summary['temporal_extent'] = populate_temporal(summary['temporal'])

    # Populate the body template
    body = ummg_body_template().safe_substitute(
        dataclasses.asdict(granule) 
        | dataclasses.asdict(granule.collection) 
        | summary
    )

    # Save it all in a file.
    with open(ummg_file_path, "tw") as f:
        print(body, file=f)

    return dataclasses.replace(
        granule,
        ummg_filename=ummg_file_path
    )

def stage_files(configuration: config.Config, granule: Granule) -> Granule:
    """
    Stage a set of files for the Granule in S3.
    """
    stuff = granule.data_filenames + [granule.ummg_filename]
    for fn in stuff:
        filename = os.path.basename(fn)
        bucket_path = s3_object_path(granule, filename)
        with open(fn, 'rb') as f:
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
        'data': granule.data_filenames,
        'metadata': [granule.ummg_filename]
    }
    for type, files in granule_files.items():
        for file in files:
            populated_file_templates.append(json.loads(files_template.safe_substitute(
                cnms_file_json_parts(configuration.staging_bucket_name,
                                     granule,
                                     file,
                                     type))))

    return dataclasses.replace(
        granule,
        cnm_message = body_template.safe_substitute(
                dataclasses.asdict(granule)
                | dataclasses.asdict(granule.collection)
                | dataclasses.asdict(configuration)
                | { 'file_content': json.dumps(populated_file_templates),
                    'cnm_schema_version': constants.CNM_JSON_SCHEMA_VERSION }
                )
    )

def write_cnm(configuration: config.Config, granule: Granule) -> Granule:
    """
    Write a CNM message to a file.
    """
    if configuration.write_cnm_file:
        cnm_file = configuration.cnm_path().joinpath(granule.producer_granule_id + '.cnm.json')
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
    logger = logging.getLogger("metgenc")
    logger.info(f"Granule: {ledger.granule.producer_granule_id}")
    logger.info(f"  * UUID           : {ledger.granule.uuid}")
    logger.info(f"  * Submission time: {ledger.granule.submission_time}")
    logger.info(f"  * Start          : {ledger.startDatetime}")
    logger.info(f"  * End            : {ledger.endDatetime}")
    logger.info(f"  * Successful     : {ledger.successful}")
    logger.debug(f"  * Actions:")
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

    logger = logging.getLogger("metgenc")
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
    file_mapping['file_size'] = os.path.getsize(file)
    file_mapping['file_type'] = file_type
    file_mapping['checksum'] = checksum(file)
    file_mapping['file_name'] = file_name
    file_mapping['staging_uri'] = s3_url(staging_bucket_name, granule, file_name)

    return file_mapping

def s3_url(staging_bucket_name, granule, filename):
    """
    Returns the full s3 URL for the given file name.
    """
    object_path = s3_object_path(granule, filename)
    return f's3://{staging_bucket_name}/{object_path}'

def s3_object_path(granule, filename):
    """
    Returns the full s3 object path for the granule
    """
    prefix = Template('external/${auth_id}/${version}/${uuid}/').safe_substitute({
        'auth_id': granule.collection.auth_id,
        'version': granule.collection.version,
        'uuid': granule.uuid
    })
    return prefix + filename

# size is a sum of all associated data file sizes.
# all other attributes use the values from the first data file entry.
def metadata_summary(details):
    default = list(details.values())[0]

    return {
        'size_in_bytes': sum([x['size_in_bytes'] for x in details.values()]),
        'production_date_time': default['production_date_time'],
        'temporal': default['temporal'],
        'geometry': default['geometry']
    }

def checksum(file):
    BUF_SIZE = 65536
    sha256 = hashlib.sha256()
    with open(file, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            sha256.update(data)

    return sha256.hexdigest()

# TODO: Use the GranuleSpatialRepresentation value in the collection metadata
# to determine the expected spatial type. See Issue #15. For now, default to
# a Gpolygon.
def populate_spatial(spatial_values):
    # spatial_values is a dict suitable for use in template substitution, like:
    # { 'points': string representation of an array of {lon: lat:} dicts }
    return ummg_spatial_gpolygon_template().safe_substitute(spatial_values)

def populate_temporal(datetime_values):
    if len(datetime_values) > 1:
        return ummg_temporal_range_template().safe_substitute({
            'begin_date_time': datetime_values[0],
            'end_date_time': datetime_values[1]})
    else:
        return ummg_temporal_single_template().safe_substitute({
            'date_time': datetime_values[0]})

def ummg_body_template():
    return initialize_template(constants.UMMG_BODY_TEMPLATE)

def ummg_temporal_single_template():
    return initialize_template(constants.UMMG_TEMPORAL_SINGLE_TEMPLATE)

def ummg_temporal_range_template():
    return initialize_template(constants.UMMG_TEMPORAL_RANGE_TEMPLATE)

def ummg_spatial_gpolygon_template():
    return initialize_template(constants.UMMG_SPATIAL_GPOLYGON_TEMPLATE)

def cnms_body_template():
    return initialize_template(constants.CNM_BODY_TEMPLATE)

def cnms_files_template():
    return initialize_template(constants.CNM_FILES_TEMPLATE)

def initialize_template(resource_location):
    with open_text(*resource_location) as template_file:
        template_str = template_file.read()

    return Template(template_str)

def validate(configuration, content_type):
    """
    Validate local JSON files
    """
    output_file_path = file_type_path(configuration, content_type)
    schema_resource_location = schema_file_path(content_type)

    logger = logging.getLogger('metgenc')
    logger.info('')
    logger.info(f"Validating files in {output_file_path}...")
    with open_text(*schema_resource_location) as sf:
        schema = json.load(sf)

        # loop through all files and validate each one
        for json_file in output_file_path.glob('*.json'):
            apply_schema(schema, json_file)

    logger.info("Validations complete.")
    return True

def file_type_path(configuration, content_type):
    match content_type:
        case 'cnm':
            return configuration.cnm_path()
        case _:
            return ''

def schema_file_path(content_type):
    match content_type:
        case 'cnm':
            return constants.CNM_JSON_SCHEMA
        case _:
            return ''

def apply_schema(schema, json_file):
    logger = logging.getLogger('metgenc')
    with open(json_file) as jf:
        json_content = json.load(jf)
        try:
            jsonschema.validate(instance=json_content, schema=schema)
            logger.info(f"Validated {json_file}")
        except jsonschema.exceptions.ValidationError as err:
            logger.error(f'Validation failed for "{err.validator}" in {json_file}: {err.validator_value}')

    return True

