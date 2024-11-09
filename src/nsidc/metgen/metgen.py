import configparser
import dataclasses
import datetime as dt
import hashlib
import json
import logging
import os.path
import sys
from typing import Callable
from pathlib import Path
from string import Template
import uuid

from funcy import all, decorator, filter, identity, partial, rcompose, take
from pyfiglet import Figlet
from returns.maybe import Maybe
from rich.prompt import Confirm, Prompt

from nsidc.metgen import aws
from nsidc.metgen import config
from nsidc.metgen import constants
from nsidc.metgen import netcdf_reader


CONSOLE_FORMAT = "%(message)s"
LOGFILE_FORMAT = "%(asctime)s|%(levelname)s|%(name)s|%(message)s"

def init_logging(configuration: config.Config):
    logger = logging.getLogger('metgenc')
    logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    logger.addHandler(console_handler)

    logfile_handler = logging.FileHandler("metgenc.log", "w")
    logfile_handler.setLevel(logging.DEBUG)
    logfile_handler.setFormatter(logging.Formatter(LOGFILE_FORMAT))
    logger.addHandler(logfile_handler)

@decorator
def log(call):
    logging.getLogger("metgenc").info(call._func.__name__)
    return call()

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

def fn_process(configuration):
    gs = granules(Path(configuration.data_dir))
    work = [granule_work(g) for g in gs]
    results = [process_work(w) for w in work]
    summary = summarize_results(results)

# -------------------------------------------------------------------

@dataclasses.dataclass
class Collection:
    auth_id: str
    version: int

@dataclasses.dataclass
class Granule:
    id: str
    collection: Maybe[Collection] = Maybe.empty
    data_filenames: list[str] = dataclasses.field(default_factory=list)
    ummg_filename: Maybe[str] = Maybe.empty
    submission_time: Maybe[str] = Maybe.empty
    uuid: Maybe[str] = Maybe.empty
    cnm_message: Maybe[str] = Maybe.empty

@dataclasses.dataclass
class Action:
    name: str
    successful: bool
    message: str
    startDatetime: Maybe[dt.datetime] = Maybe.empty
    endDatetime: Maybe[dt.datetime] = Maybe.empty

@dataclasses.dataclass
class Record:
    granule: Granule
    actions: list[Action] = dataclasses.field(default_factory=list)
    successful: bool = False
    startDatetime: Maybe[dt.datetime] = Maybe.empty
    endDatetime: Maybe[dt.datetime] = Maybe.empty

# -------------------------------------------------------------------

def process(configuration: config.Config) -> None:
    # TODO: Prep actions like mkdir, etc
    # ummg_path = Path(configuration.local_output_dir, configuration.ummg_dir)
    # all_existing_ummg = [os.path.basename(i) for i in ummg_path.glob('*.json')]

    # TODO: Add conditional operation to create ummg -- or is conditional in the operation?
    operations = [
            granule_collection,
            prepare_granule,
            create_ummg,
            stage_files,
            create_cnms,
            write_cnms,
            publish_cnms,
        ]

    configured_operations = [partial(fn, configuration) for fn in operations]
    recorded_operations = [partial(recorder, fn) for fn in configured_operations]
    pipeline = rcompose(
        start_record, 
        *recorded_operations, 
        end_record, 
        log_record
    )

    gs = take(configuration.number, granules(configuration.data_dir))
    results = [pipeline(Record(g)) for g in gs]

    summarize_results(results)

def granules(data_dir: str) -> list[Granule]:
    return [Granule(p.name, data_filenames=[str(p)])
            for p in Path(data_dir).glob('*.nc')]

def recorder(fn: Callable[[Granule], Granule], record: Record) -> Record:
    start = dt.datetime.now()
    new_granule = fn(record.granule)
    end = dt.datetime.now()

    new_actions = record.actions.copy()
    new_actions.append(
            Action(
                fn.func.__name__,
                successful=True,
                message=None,
                startDatetime=start,
                endDatetime=end
            )
        )

    return dataclasses.replace(
        record,
        granule=new_granule,
        actions=new_actions
    )

def start_record(record: Record) -> Record:
    return dataclasses.replace(
        record,
        startDatetime=dt.datetime.now()
    )

def end_record(record: Record) -> Record:
    return dataclasses.replace(
        record,
        endDatetime=dt.datetime.now(),
        successful=all([a.successful for a in record.actions])
    )

def granule_collection(configuration: config.Config, granule: Granule) -> Granule:
    return dataclasses.replace(
        granule, 
        collection=Collection(configuration.auth_id, configuration.version)
    )

def prepare_granule(configuration: config.Config, granule: Granule) -> Granule:
    return dataclasses.replace(
        granule, 
        submission_time=dt.datetime.now(dt.timezone.utc).isoformat(),
        uuid=str(uuid.uuid4())
    )

def create_ummg(configuration: config.Config, granule: Granule) -> Granule:
    ummg_path = Path(configuration.local_output_dir, configuration.ummg_dir)
    ummg_file = granule.id + '.json'
    ummg_file_path = os.path.join(ummg_path, ummg_file)

    metadata_details = {}

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
    stuff = granule.data_filenames + [granule.ummg_filename]
    for fn in stuff:
        filename = os.path.basename(fn)
        bucket_path = s3_object_path(granule, filename)
        with open(fn, 'rb') as f:
            aws.stage_file(configuration.staging_bucket_name, bucket_path, file=f)

    return granule

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

def create_cnms(configuration: config.Config, granule: Granule) -> Granule:
    # Break up the JSON string into its components so information about multiple files is
    # easier to add.
    body_template = cnms_body_template()
    body_content = body_template.safe_substitute(dataclasses.asdict(granule))
    body_json = json.loads(body_content)

    file_template = cnms_files_template()

    granule_files = {
        'data': granule.data_filenames,
        'metadata': [granule.ummg_filename]
    }
    for type, files in granule_files.items():
        for file in files:
            values = cnms_file_json_parts(configuration.staging_bucket_name, granule, file, type)
            file_json = file_template.safe_substitute(values)
            body_json['product']['files'].append(json.loads(file_json))

    return dataclasses.replace(
        granule,
        cnm_message=json.dumps(body_json)
    )

def cnms_file_json_parts(staging_bucket_name, granule, file, file_type):
    file_mapping = dict()
    file_name = os.path.basename(file)
    file_mapping['file_size'] = os.path.getsize(file)
    file_mapping['file_type'] = file_type
    file_mapping['checksum'] = checksum(file)
    file_mapping['file_name'] = file_name
    file_mapping['staging_uri'] = s3_url(staging_bucket_name, granule, file_name)

    return file_mapping

def write_cnms(configuration: config.Config, granule: Granule) -> Granule:
    if configuration.write_cnm_file:
        cnm_file = os.path.join(configuration.local_output_dir, 'cnm', granule.id + '.cnm.json')
        with open(cnm_file, "tw") as f:
            print(granule.cnm_message, file=f)
    return granule

def publish_cnms(configuration: config.Config, granule: Granule) -> Granule:
    if configuration.write_cnm_file:
        cnm_file = os.path.join(
            configuration.local_output_dir, 
            'cnm', 
            granule.id + '.cnm.json'
        )
        with open(cnm_file, "tw") as f:
            print(granule.cnm_message, file=f)
    stream_name = configuration.kinesis_stream_name
    aws.post_to_kinesis(stream_name, granule.cnm_message)
    return granule

def log_record(record: Record) -> Record:
    logger = logging.getLogger("metgenc")
    logger.info(f"Granule: {record.granule.id}")
    logger.info(f"  * UUID           : {record.granule.uuid}")
    logger.info(f"  * Submission time: {record.granule.submission_time}")
    logger.info(f"  * Start          : {record.startDatetime}")
    logger.info(f"  * End            : {record.endDatetime}")
    logger.info(f"  * Successful     : {record.successful}")
    logger.debug(f"  * Actions:")
    for a in record.actions:
        logger.debug(f"      + Name: {a.name}")
        logger.debug(f"        Start     : {a.startDatetime}")
        logger.debug(f"        End       : {a.endDatetime}")
        logger.debug(f"        Successful: {a.successful}")
    return record

def summarize_results(records: list[Record]) -> None:
    successful_count = len(list(filter(lambda r: r.successful, records)))
    failed_count = len(list(filter(lambda r: not r.successful, records)))
    logger = logging.getLogger("metgenc")
    logger.info("Processing Summary")
    logger.info("==================")
    logger.info(f"Granules  : {len(records)}")
    logger.info(f"Start     : {records[0].startDatetime}")
    logger.info(f"End       : {records[-1].endDatetime}")
    logger.info(f"Successful: {successful_count}")
    logger.info(f"Failed    : {failed_count}")

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

# -------------------------------------------------------------------

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

def initialize_template(file):
    with open(file) as template_file:
        template_str = template_file.read()

    return Template(template_str)
