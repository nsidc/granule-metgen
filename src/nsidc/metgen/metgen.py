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


def banner():
    f = Figlet(font='slant')
    return f.renderText('Instameta')

def config_parser(configuration_file):
    if configuration_file is None or not os.path.exists(configuration_file):
        raise ValueError(f'Unable to find configuration file {configuration_file}')
    cfg_parser = configparser.ConfigParser()
    cfg_parser.read(configuration_file)
    return cfg_parser

def producer_granule_id(ummg_file):
    """Extract ProducerGranuleId value from an existing UMM-G file.
    """
    with open(ummg_file) as f:
        d = json.load(f)
        ids = d['DataGranule']['Identifiers']
        pgid = [d for d in ids if d['IdentifierType'] == 'ProducerGranuleId']
        id_str = pgid[0]['Identifier'] if pgid else ''
    return id_str

def configuration(config_parser, environment):
    try:
        # Look here for science files (and any ancillary files)
        data_dir = config_parser.get('Source', 'data_dir')

        # Collection (dataset) information
        auth_id = config_parser.get('Collection', 'auth_id')
        version = config_parser.get('Collection', 'version')
        provider = config_parser.get('Collection', 'provider')

        local_output_dir = config_parser.get('Destination', 'local_output_dir')
        ummg_dir = config_parser.get('Destination', 'ummg_dir')
        kinesis_arn = config_parser.get('Destination', 'kinesis_arn')

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
# TODO require a non-blank input for values without defaults
def init_config(configuration_file):
    print("""This utility will create a granule metadata configuration file by prompting """
          """you for values for each of the configuration parameters.""")
    print()
    # prompt for config file name if it doesn't exist
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
    print("Source Data Parameters")
    print('--------------------------------------------------')
    cfg_parser.add_section("Source")
    cfg_parser.set("Source", "data_dir", Prompt.ask("Data directory", default="data"))
    print()

    print()
    print("Collection Parameters")
    print('--------------------------------------------------')
    cfg_parser.add_section("Collection")
    cfg_parser.set("Collection", "auth_id", Prompt.ask("Authoritative ID"))
    cfg_parser.set("Collection", "version", Prompt.ask("Version"))
    cfg_parser.set("Collection", "provider", Prompt.ask("Provider"))
    print()

    print()
    print("Destination Parameters")
    print('--------------------------------------------------')
    cfg_parser.add_section("Destination")
    cfg_parser.set("Destination", "local_output_dir", Prompt.ask("Local output directory", default="output"))
    cfg_parser.set("Destination", "ummg_dir", Prompt.ask("Local UMM-G output directory (relative to local output directory)", default="ummg"))
    cfg_parser.set("Destination", "kinesis_arn", Prompt.ask("Kinesis Stream ARN"))

    print()
    print(f'Saving new configuration: {configuration_file}')
    with open(configuration_file, "tw") as file:
        cfg_parser.write(file)

    return configuration_file

def read_config(configuration):
    mapping = dict(configuration.__dict__)
    mapping['checksum_type'] = 'SHA256'
    return mapping

def show_config(configuration):
    # TODO add section headings in the right spot (if we think we need them in the output)
    print()
    print('Using configuration:')
    for k,v in configuration.__dict__.items():
        print(f'  + {k}: {v}')

def process(configuration):
    # For each input file in `data_dir`:
    #   * create or find ummg file
    #   * stage data & ummg files
    #   * compose CNM-S
    #   * publish CNM-S
    #   * create audit entry
    # TODO:
    #   * Parallelize the operations
    show_config(configuration)
    print()
    print('--------------------------------------------------')

    source_data_path = Path(configuration.data_dir)
    source_data = list(source_data_path.glob('*.nc'))
    ummg_path = Path(configuration.local_output_dir, configuration.ummg_dir)
    existing_ummg = {os.path.basename(i) for i in ummg_path.glob('*.json')}

    print(f'Found {len(source_data)} source files to process')
    print()

    # initialize template content common to all files
    template = body_template()
    mapping = read_config(configuration)

    for file in source_data:
        print()
        print('--------------------------------------------------')
        print()
        ummg_file = find_or_create_ummg(file, existing_ummg)
        if not ummg_file:
            print(f'No UMM-G file for {file}, skipping.')
            continue

        ummg_file = os.path.join(ummg_path, ummg_file)

        # generate uuid value (needed to generate path to S3 staging location)
        mapping['uuid'] = str(uuid.uuid4())

        mapping['producer_granule_id'] = producer_granule_id(ummg_file)

        stage(mapping, granule_files=[file], metadata_file=ummg_file)
        cnm = cnms_message(mapping, body_template=template, granule_files=[file], metadata_file=ummg_file)
        publish_cnm(mapping, cnm)

    print()
    print('--------------------------------------------------')
    print()
    print(f'Processed {len(source_data)} source files')

def find_or_create_ummg(science_file, existing_ummg):
    #
    # TODO: create ummg if one doesn't exist, saving it to ummg_path
    # For now: look for umm-g with same name as science file plus a '.json' suffix
    ummg_file = os.path.basename(science_file) + '.json'
    if ummg_file in existing_ummg:
        return ummg_file
    else:
        return ''

def stage(mapping, granule_files=[], metadata_file=''):
    print()
    for file in granule_files:
        print(f'TODO: stage file {file} to {s3_url(mapping, os.path.basename(file))}')
        print()

    print(f'TODO: stage file {metadata_file} to {s3_url(mapping, os.path.basename(metadata_file))}')
    print()

def cnms_message(mapping, body_template='', granule_files=[], metadata_file=''):
    mapping['submission_time'] = datetime.now(timezone.utc).isoformat()

    # Break up the JSON string into its components so information about multiple files is
    # easier to add.
    body_content = body_template.safe_substitute(mapping)
    body_json = json.loads(body_content)

    file_template = files_template()

    # Clunky first attempt at implementing a loop so we can eventually handle multiple
    # science/ancillary files in a sane way. Note! This gives all granule files the
    # identical type of "data".
    for file in granule_files:
        sub_mapping = dict(mapping)
        sub_mapping['file_size'] = os.path.getsize(file)
        sub_mapping['file_type'] = 'data'
        sub_mapping['checksum'] = generate_hash(file)
        sub_mapping['file_name'] = os.path.basename(file)
        sub_mapping['staging_uri'] = s3_url(mapping, sub_mapping['file_name'])

        new_content = file_template.safe_substitute(sub_mapping)
        body_json['product']['files'].append(json.loads(new_content))

    # Tack on the metadata file information
    sub_mapping = dict(mapping)
    sub_mapping['file_size'] = os.path.getsize(metadata_file)
    sub_mapping['file_type'] = 'metadata'
    sub_mapping['checksum'] = generate_hash(metadata_file)
    sub_mapping['file_name'] = os.path.basename(metadata_file)
    sub_mapping['staging_uri'] = s3_url(mapping, sub_mapping['file_name'])

    new_content = file_template.safe_substitute(sub_mapping)
    body_json['product']['files'].append(json.loads(new_content))

    # Serialize the populated values back to JSON
    return json.dumps(body_json)

def publish_cnm(mapping, cnm_message):
    # TODO write file to a hard-coded location for now, rather than post to Kinesis
    cnm_file = os.path.join(mapping['local_output_dir'], 'cnm', mapping['producer_granule_id'] + '.cnm.json')
    with open(cnm_file, "tw") as f:
        print(cnm_message, file=f)
    print(f'Saved CNM message {cnm_message} to {cnm_file}')

def generate_hash(file):
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
    s3_template = 's3://nsidc-cumulus-${environment}-ingest-staging/external/${auth_id}/${version}/${uuid}/${s3_name}'
    template = Template(s3_template)

    mapping['s3_name'] = name
    return(template.safe_substitute(mapping))

def body_template():
    return initialize_template('src/nsidc/metgen/templates/cnm_body_template.json')

def files_template():
    return initialize_template('src/nsidc/metgen/templates/cnm_files_template.json')

def initialize_template(file):
    with open(file) as template_file:
        template_str = template_file.read()

    return Template(template_str)
