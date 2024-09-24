import configparser
from dataclasses import dataclass
import os.path
from pathlib import Path
from pyfiglet import Figlet
from rich.prompt import Confirm, Prompt
from datetime import datetime, timezone
import uuid
import hashlib
import json
from string import Template
from nsidc.metgen import constants
from nsidc.metgen import netcdf_to_ummg
from netCDF4 import Dataset
from cftime import num2date

SOURCE_SECTION_NAME = 'Source'
COLLECTION_SECTION_NAME = 'Collection'
DESTINATION_SECTION_NAME = 'Destination'
UMMG_BODY_TEMPLATE = 'src/nsidc/metgen/templates/ummg_body_template.json'
UMMG_TEMPORAL_TEMPLATE = 'src/nsidc/metgen/templates/ummg_temporal_single_template.json'
UMMG_SPATIAL_TEMPLATE = 'src/nsidc/metgen/templates/ummg_horizontal_rectangle_template.json'
CNM_BODY_TEMPLATE = 'src/nsidc/metgen/templates/cnm_body_template.json'
CNM_FILES_TEMPLATE = 'src/nsidc/metgen/templates/cnm_files_template.json'

@dataclass
class Config:
    environment: str
    data_dir: str
    auth_id: str
    version: str
    provider: str
    local_output_dir: str
    ummg_dir: str
    kinesis_arn: str

    def show(self):
        # TODO add section headings in the right spot (if we think we need them in the output)
        print()
        print('Using configuration:')
        for k,v in self.__dict__.items():
            print(f'  + {k}: {v}')

    def enhance(self, producer_granule_id):
        mapping = dict(self.__dict__)
        collection_details = self.collection_from_cmr(mapping)

        mapping['auth_id'] = collection_details['auth_id']
        mapping['version'] = collection_details['version']
        mapping['producer_granule_id'] = producer_granule_id
        mapping['submission_time'] = datetime.now(timezone.utc).isoformat()
        mapping['uuid'] = str(uuid.uuid4())

        print(f'mapping is now {mapping}')
        return mapping

    # Is the right place for this function?
    def collection_from_cmr(self, mapping):
        # TODO: Use auth_id and version from mapping object to retrieve collection
        # metadata from CMR, including formatted version number, temporal range, and
        # spatial coverage.
        return {
            'auth_id': mapping['auth_id'],
            'version': mapping['version']
        }


def banner():
    f = Figlet(font='slant')
    return f.renderText('Instameta')

def config_parser(configuration_file):
    if configuration_file is None or not os.path.exists(configuration_file):
        raise ValueError(f'Unable to find configuration file {configuration_file}')
    cfg_parser = configparser.ConfigParser()
    cfg_parser.read(configuration_file)
    return cfg_parser

def configuration(config_parser, environment=constants.DEFAULT_CUMULUS_ENVIRONMENT):
    try:
        # Look here for science files
        data_dir = config_parser.get('Source', 'data_dir')

        # Collection (dataset) information
        auth_id = config_parser.get(COLLECTION_SECTION_NAME, 'auth_id')
        version = config_parser.get(COLLECTION_SECTION_NAME, 'version')
        provider = config_parser.get(COLLECTION_SECTION_NAME, 'provider')

        local_output_dir = config_parser.get(DESTINATION_SECTION_NAME, 'local_output_dir')
        ummg_dir = config_parser.get(DESTINATION_SECTION_NAME, 'ummg_dir')
        kinesis_arn = config_parser.get(DESTINATION_SECTION_NAME, 'kinesis_arn')

        return Config(
            environment,
            data_dir,
            auth_id,
            version,
            provider,
            local_output_dir,
            ummg_dir,
            kinesis_arn)
    except Exception as e:
        return Exception('Unable to read the configuration file', e)

#
# TODO require a non-blank input for elements that have no default value
def init_config(configuration_file):
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
    print(f'{SOURCE_SECTION_NAME} Data Parameters')
    print('--------------------------------------------------')
    cfg_parser.add_section(SOURCE_SECTION_NAME)
    cfg_parser.set(SOURCE_SECTION_NAME, "data_dir", Prompt.ask("Data directory", default="data"))
    print()

    print()
    print(f'{COLLECTION_SECTION_NAME} Parameters')
    print('--------------------------------------------------')
    cfg_parser.add_section(COLLECTION_SECTION_NAME)
    cfg_parser.set(COLLECTION_SECTION_NAME, "auth_id", Prompt.ask("Authoritative ID"))
    cfg_parser.set(COLLECTION_SECTION_NAME, "version", Prompt.ask("Version"))
    cfg_parser.set(COLLECTION_SECTION_NAME, "provider", Prompt.ask("Provider"))
    print()

    print()
    print(f'{DESTINATION_SECTION_NAME} Parameters')
    print('--------------------------------------------------')
    cfg_parser.add_section(DESTINATION_SECTION_NAME)
    cfg_parser.set(DESTINATION_SECTION_NAME, "local_output_dir", Prompt.ask("Local output directory", default="output"))
    cfg_parser.set(DESTINATION_SECTION_NAME, "ummg_dir", Prompt.ask("Local UMM-G output directory (relative to local output directory)", default="ummg"))
    cfg_parser.set(DESTINATION_SECTION_NAME, "kinesis_arn", Prompt.ask("Kinesis Stream ARN"))

    print()
    print(f'Saving new configuration: {configuration_file}')
    with open(configuration_file, "tw") as file:
        cfg_parser.write(file)

    return configuration_file


def process(configuration):
    # For each granule in `data_dir`:
    #   * create or find ummg file
    #   * stage data & ummg files
    #   * compose CNM-S
    #   * publish CNM-S
    #   * create audit entry
    # TODO:
    #   * Parallelize the operations
    configuration.show()
    print()
    print('--------------------------------------------------')

    granules = granule_paths(Path(configuration.data_dir))
    print(f'Found {len(granules.items())} granules to process')
    print()

    ummg_path = Path(configuration.local_output_dir, configuration.ummg_dir)
    all_existing_ummg = [os.path.basename(i) for i in ummg_path.glob('*.json')]

    # initialize template content common to all files
    cnms_template = cnms_body_template()
    processed_count = 0

    for producer_granule_id, granule_files in granules.items():
        print()
        print('--------------------------------------------------')
        print(f'pgid: {producer_granule_id}')

        # Add producer_granule_id and information from CMR.
        mapping = configuration.enhance(producer_granule_id)

        ummg_file = find_or_create_ummg(mapping, granule_files['data'], ummg_path, all_existing_ummg)
        if not ummg_file:
            print(f'No UMM-G file for {producer_granule_id}, skipping.')
            continue

        granule_files['metadata'] = [ummg_file]
        print(f'granule paths: {granule_files}')

        processed_count += 1

        stage(mapping, granule_files=granule_files)
        cnm_content = cnms_message(mapping,
                                   body_template=cnms_template,
                                   granule_files=granule_files)
        publish_cnm(mapping, cnm_content)

    print()
    print('--------------------------------------------------')
    print()
    print(f'Processed {processed_count} source files')

def granule_paths(data_dir):
    granules = {}

    # This sets up a data structure to associate a "producer granule id" with
    # one or more files identified as part of the same granule. We still need
    # code to identify the common basename for the cases where more than one
    # file exists per granule (or the case where an ancillary file is associated
    # with the granule), and to add the correct "type" of the file. See the CNM
    # spec for a list of types. At the moment the assumption is one file per
    # granule, with a type of "data," plus a metadata (UMM-G) file.
    producer_granule_ids = [os.path.basename(i) for i in data_dir.glob('*.nc')]
    for pgid in producer_granule_ids:
        granules[pgid] = {'data': [os.path.join(data_dir, pgid)]}

    return granules

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
    # Open data files and retrieve metadata. Eventually need a way to hook in
    # custom code to read different data file types, or scrape metadata from
    # file names, etc.
    # metadata_details dict looks like:
    # {
    #   data_file: {
    #       'size_in_bytes' => integer,
    #       'production_date_time'  => iso datetime string,
    #       'begin_date_time' and 'end_date_time' OR 'date_time'
    #       'geometry' => {'west' => , 'north' => , 'east' => , 'south' => }
    #   }
    # }
    metadata_details = {}

    for data_file in data_file_paths:
        # Assumes netCDF!
        metadata_details[data_file] = netcdf_to_ummg.netcdf_to_ummg(data_file)

    print(f'metadata details : {metadata_details}')

    # Collapse information about (possibly) multiple files into a "granule" summary.
    summary = metadata_summary(metadata_details)
    print(f'summary: {summary}')

    # Populate the body template and convert to JSON
    body_json = json.loads(ummg_body_template().safe_substitute(mapping | summary))

    # Cram JSON for temporal and spatial coverage into the body of the metadata content.
    body_json['SpatialExtent']['HorizontalSpatialDomain'] = json.loads(ummg_spatial_template().safe_substitute(summary['geometry']))
    body_json['TemporalExtent'] = json.loads(ummg_temporal_template().safe_substitute(summary))

    # Save it all in a file
    with open(ummg_file_path, "tw") as f:
        print(json.dumps(body_json), file=f)

    print(f'Created ummg file {ummg_file_path}')
    return ummg_file_path

# size is a sum of all associated data file sizes.
# production datetime, temporal coverage, spatial coverage (geometry): simply use values from first data file entry
def metadata_summary(details):
    summary = {}
    default = list(details.values())[0]

    summary['size_in_bytes'] = sum([x['size_in_bytes'] for x in details.values()])
    summary['production_date_time'] = default['production_date_time']
    summary['date_time'] = default['date_time']
    summary['geometry'] = default['geometry']
    return summary

def stage(mapping, granule_files={}):
    """
    Stage all files related to a granule to a Cumulus location
    """

    print()
    for file_type, file_paths in granule_files.items():
        for file_path in file_paths:
            print(f'TODO: stage {file_type} file {file_path} to {s3_url(mapping, os.path.basename(file_path))}')
            print()

    print()

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

def publish_cnm(mapping, cnm_message):
    # TODO: add option to post to Kinesis rather than write an actual file
    cnm_file = os.path.join(mapping['local_output_dir'], 'cnm', mapping['producer_granule_id'] + '.cnm.json')
    with open(cnm_file, "tw") as f:
        print(cnm_message, file=f)
    print(f'Saved CNM message {cnm_message} to {cnm_file}')

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
    mapping['s3_name'] = name
    template = Template('s3://nsidc-cumulus-${environment}-ingest-staging/external/${auth_id}/${version}/${uuid}/${s3_name}')

    return(template.safe_substitute(mapping))

def ummg_body_template():
    return initialize_template(UMMG_BODY_TEMPLATE)

def ummg_temporal_template():
    return initialize_template(UMMG_TEMPORAL_TEMPLATE)

def ummg_spatial_template():
    return initialize_template(UMMG_SPATIAL_TEMPLATE)

def cnms_body_template():
    return initialize_template(CNM_BODY_TEMPLATE)

def cnms_files_template():
    return initialize_template(CNM_FILES_TEMPLATE)

def initialize_template(file):
    with open(file) as template_file:
        template_str = template_file.read()

    return Template(template_str)
