import configparser
import hashlib
import json
import os.path
from pathlib import Path
from string import Template

from pyfiglet import Figlet
from rich.prompt import Confirm, Prompt

from nsidc.metgen import aws
from nsidc.metgen import config
from nsidc.metgen import netcdf_reader


SOURCE_SECTION_NAME = 'Source'
COLLECTION_SECTION_NAME = 'Collection'
DESTINATION_SECTION_NAME = 'Destination'
SETTINGS_SECTION_NAME = 'Settings'
CNM_BODY_TEMPLATE = 'src/nsidc/metgen/templates/cnm_body_template.json'
CNM_FILES_TEMPLATE = 'src/nsidc/metgen/templates/cnm_files_template.json'
UMMG_BODY_TEMPLATE = 'src/nsidc/metgen/templates/ummg_body_template.json'
UMMG_TEMPORAL_SINGLE_TEMPLATE = 'src/nsidc/metgen/templates/ummg_temporal_single_template.json'
UMMG_TEMPORAL_RANGE_TEMPLATE = 'src/nsidc/metgen/templates/ummg_temporal_range_template.json'
UMMG_SPATIAL_GPOLYGON_TEMPLATE = 'src/nsidc/metgen/templates/ummg_horizontal_gpolygon_template.json'
UMMG_SPATIAL_POINT_TEMPLATE = 'src/nsidc/metgen/templates/ummg_horizontal_point_template.json'
UMMG_SPATIAL_RECTANGLE_TEMPLATE = 'src/nsidc/metgen/templates/ummg_horizontal_rectangle_template.json'

def banner():
    f = Figlet(font='slant')
    return f.renderText('Instameta')

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
    cfg_parser.set(DESTINATION_SECTION_NAME, "kinesis_stream_name", Prompt.ask("Kinesis stream name"))
    cfg_parser.set(DESTINATION_SECTION_NAME, "write_cnm_file", Prompt.ask("Write CNM messages to files (True/False)"))

    print()
    print(f'{SETTINGS_SECTION_NAME} Parameters')
    print('--------------------------------------------------')
    cfg_parser.add_section(SETTINGS_SECTION_NAME)
    cfg_parser.set(SETTINGS_SECTION_NAME, "checksum_type", Prompt.ask("Checksum type", default="SHA256"))

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

    # TODO: create local_output_dir, ummg_dir, and cnm subdir if they don't exist
    ummg_path = Path(configuration.local_output_dir, configuration.ummg_dir)
    all_existing_ummg = [os.path.basename(i) for i in ummg_path.glob('*.json')]

    # initialize template content common to all files
    cnms_template = cnms_body_template()
    processed_count = 0

    for producer_granule_id, granule_files in granules:
        print('--------------------------------------------------')
        print(f'Processing {producer_granule_id}...')

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
        publish_cnm(mapping, cnm_content)

    print()
    print('--------------------------------------------------')
    print()
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
    if mapping['write_cnm_file']:
        cnm_file = os.path.join(mapping['local_output_dir'], 'cnm', mapping['producer_granule_id'] + '.cnm.json')
        with open(cnm_file, "tw") as f:
            print(cnm_message, file=f)
        print(f'Saved CNM message {cnm_message} to {cnm_file}')
    #aws.post_to_kinesis(mapping['kinesis_stream_name'], cnm_message)

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

def ummg_temporal_single_template():
    return initialize_template(UMMG_TEMPORAL_SINGLE_TEMPLATE)

def ummg_temporal_range_template():
    return initialize_template(UMMG_TEMPORAL_RANGE_TEMPLATE)

def ummg_spatial_gpolygon_template():
    return initialize_template(UMMG_SPATIAL_GPOLYGON_TEMPLATE)

def cnms_body_template():
    return initialize_template(CNM_BODY_TEMPLATE)

def cnms_files_template():
    return initialize_template(CNM_FILES_TEMPLATE)

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
