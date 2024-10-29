import configparser
import dataclasses
import functools
import hashlib
import json
import logging
import os.path
import sys
from typing import Callable
from pathlib import Path
from string import Template

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
    logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    logger.addHandler(console_handler)

    logfile_handler = logging.FileHandler("metgenc.log", "w")
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

def fn_process(configuration):
    gs = granules(Path(configuration.data_dir))
    work = [granule_work(g) for g in gs]
    results = [process_work(w) for w in work]
    summary = summarize_results(results)

# -------------------------------------------------------------------
# -------------------------------------------------------------------

@dataclasses.dataclass
class Result:
    success: bool
    message: str

@dataclasses.dataclass
class Action:
    name: str
    fn: Callable[[], Result]
    complete: bool

@dataclasses.dataclass
class Granule:
    id: str
    data_filenames: list[str]
    ummg_filename: str
    actions: list[Action]
    results: list[Result]

# -------------------------------------------------------------------

def process(configuration: config.Config) -> None:
    gs = granules(Path(configuration.data_dir))
    gs = [granule_actions(g) for g in gs]
    gs = [process_actions(g) for g in gs]
    summarize_results(gs)

def granules(data_dir: Path) -> list[Granule]:
    paths = data_dir.glob('*.nc')
    return [Granule(p.name, [str(p)], '', [], []) for p in paths]

def granule_actions(granule: Granule) -> Granule:
    return Granule(
            granule.id, 
            granule.data_filenames,
            granule.ummg_filename,
            [
                Action('create_ummg', lambda: Result(True, ''), False),
                Action('stage_files', lambda: Result(True, ''), False),
                Action('create_cnms', lambda: Result(True, ''), False),
                Action('publish_cnms', lambda: Result(True, ''), False),
            ],
            []
    )

def process_actions(granule: Granule) -> Granule:
    return Granule(
            granule.id,
            granule.data_filenames,
            granule.ummg_filename,
            granule.actions,
            [a.fn() for a in granule.actions]
    )

def summarize_results(granules: list[Granule]) -> None:
    logger = logging.getLogger("metgenc")
    for g in granules:
        print(f"{g.id}:")
        action_results = zip(g.actions, g.results)
        for action, result in action_results:
            logger.info(f"  Action: {action.name} Success: {result.success} Message: {result.message}")

# -------------------------------------------------------------------
# -------------------------------------------------------------------

def legacy_process(configuration):
    """
    Processes input files by creating UMM-G metadata, staging the science and
    metadata files, and publishing a CNM message.
    """
    configuration.show()
    print()

    print('--------------------------------------------------')

    valid, errors = config.validate(configuration)
    if not valid:
        print("The configuration is invalid:")
        for msg in errors:
            print(" * " + msg)
        raise Exception('Invalid configuration')

    granules = granule_paths(Path(configuration.data_dir))
    print(f'Found {len(granules)} granules to process')
    if configuration.number < 1 or configuration.number >= len(granules):
        print('Processing all available granules')
    else:
        print(f'Processing the first {configuration.number} granule(s)')
        granules = granules[:configuration.number]
    print()

    ummg_path, cnm_path = prepare_output_dirs(configuration)
    all_existing_ummg = [os.path.basename(i) for i in ummg_path.glob('*.json')]

    # initialize template content common to all files
    cnms_template = cnms_body_template()
    processed_count = 0

    for producer_granule_id, granule_files in granules:
        print('--------------------------------------------------')
        print(f'Processing {producer_granule_id}:')
        print()

        # Add producer_granule_id and information from CMR.
        mapping = configuration.enhance(producer_granule_id)

        ummg_file = find_or_create_ummg(mapping, granule_files['data'], ummg_path, all_existing_ummg)
        if not ummg_file:
            print(f'No UMM-G file for {producer_granule_id}, skipping.')
            continue

        granule_files['metadata'] = [ummg_file]

        processed_count += 1

        stage(mapping, granule_files=granule_files)
        cnm_content = cnms_message(mapping,
                                   body_template=cnms_template,
                                   granule_files=granule_files)
        publish_cnm(mapping, cnm_path, cnm_content)
        print()

    print('--------------------------------------------------')
    print(f'Processed {processed_count} source files')

def granule_paths(data_dir):
    # Returns a list of tuples containing the "producer granule id" and a dict
    # containing the key 'data' with a list of one or more files identified as 
    # part of the same granule. We still need code to identify the common
    # basename for the cases where more than one file exists per granule (or
    # the case where an ancillary file is associated with the granule), and to
    # add the correct "type" of the file. See the CNM spec for a list of types.
    # At the moment the assumption is one (netCDF!) file per granule, with a
    # type of "data," plus a metadata (UMM-G) file.
    producer_granule_ids = [os.path.basename(f) for f in data_dir.glob('*.nc')]
    granule_data_files = [{ 'data': [f] } for f in data_dir.glob('*.nc')]

    return list(zip(producer_granule_ids, granule_data_files))

def find_or_create_ummg(mapping, data_file_paths, ummg_path, all_existing_ummg):
    """
    Look for an existing UMM-G file. If nothing found, create a new one.

    Returns complete path to file.
    """
    ummg_file = mapping['producer_granule_id'] + '.json'
    ummg_file_path = os.path.join(ummg_path, ummg_file)
    if ummg_file in all_existing_ummg:
        return (ummg_file_path)
    else:
        return create_ummg(mapping, data_file_paths, ummg_file_path)

def create_ummg(mapping, data_file_paths, ummg_file_path):
    """
    Open data file(s) associated with one granule and retrieve metadata.
    """

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
    for data_file in data_file_paths:
        metadata_details[data_file] = netcdf_reader.extract_metadata(data_file)

    # Collapse information about (possibly) multiple files into a granule summary.
    summary = metadata_summary(metadata_details)
    summary['spatial_extent'] = populate_spatial(summary['geometry'])
    summary['temporal_extent'] = populate_temporal(summary['temporal'])

    # Populate the body template
    body = ummg_body_template().safe_substitute(mapping | summary)

    # Save it all in a file.
    with open(ummg_file_path, "tw") as f:
        print(body, file=f)

    print(f'Created ummg file {ummg_file_path}')
    return ummg_file_path

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

def stage(mapping, granule_files={}):
    """
    Stage all files related to a granule to a Cumulus location
    """
    for file_type, file_paths in granule_files.items():
        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            bucket_path = s3_object_path(mapping, file_name)
            with open(file_path, 'rb') as f:
                bucket_name = mapping['staging_bucket_name']
                aws.stage_file(bucket_name, bucket_path, file=f)
                print(f'Staged {file_name} to bucket {bucket_name}{bucket_path}')

def cnms_message(mapping, body_template='', granule_files={}):

    # Break up the JSON string into its components so information about multiple files is
    # easier to add.
    body_content = body_template.safe_substitute(mapping)
    body_json = json.loads(body_content)

    file_template = cnms_files_template()

    for type, files in granule_files.items():
        for file in files:
            file_json = file_template.safe_substitute(cnms_file_json_parts(mapping, file, type))
            body_json['product']['files'].append(json.loads(file_json))

    # Serialize the populated values back to JSON
    return json.dumps(body_json)

def cnms_file_json_parts(mapping, file, file_type):
    file_mapping = dict(mapping)
    file_name = os.path.basename(file)
    file_mapping['file_size'] = os.path.getsize(file)
    file_mapping['file_type'] = file_type
    file_mapping['checksum'] = checksum(file)
    file_mapping['file_name'] = file_name
    file_mapping['staging_uri'] = s3_url(mapping, file_name)
    return file_mapping

def publish_cnm(mapping, cnm_path, cnm_message):
    if mapping['write_cnm_file']:
        cnm_file = os.path.join(cnm_path, mapping['producer_granule_id'] + '.cnm.json')
        with open(cnm_file, "tw") as f:
            print(cnm_message, file=f)
        print(f'Saved CNM message {cnm_message} to {cnm_file}')
    stream_name = mapping['kinesis_stream_name']
    aws.post_to_kinesis(stream_name, cnm_message)
    print(f'Published CNM message to Kinesis stream {stream_name}')

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

def s3_url(mapping, name):
    """
    Returns the full s3 URL for the given file name.
    """
    bucket_name = mapping['staging_bucket_name']
    object_path = s3_object_path(mapping, name)
    return f's3://{bucket_name}/{object_path}'

def s3_object_path(mapping, name):
    """
    Returns the full s3 object path for the given file name.
    """
    template = Template('external/${auth_id}/${version}/${uuid}/')
    return(template.safe_substitute(mapping) + name)

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
