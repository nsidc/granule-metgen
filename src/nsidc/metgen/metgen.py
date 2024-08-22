import configparser
from dataclasses import dataclass
import os.path
from pathlib import Path
from pyfiglet import Figlet
from rich.prompt import Confirm, Prompt


@dataclass
class Config:
    source_data_dir: str
    destination_kinesis_arn: str
    destination_s3_url: str
    auth_id: str

def banner():
    f = Figlet(font='slant')
    return f.renderText('Instameta')

def config_parser(configuration_file):
    if configuration_file is None or not os.path.exists(configuration_file):
        raise ValueError(f'Unable to find configuration file {configuration_file}')
    cfg_parser = configparser.ConfigParser()
    cfg_parser.read(configuration_file)
    return cfg_parser

def configuration(config_parser):
    try:
        source_data_dir = config_parser.get('Source', 'data_dir')
        auth_id = config_parser.get('Collection', 'auth_id')
        destination_kinesis_arn = config_parser.get('Destination', 'kinesis_arn')
        destination_s3_url = config_parser.get('Destination', 's3_url')
        return Config(source_data_dir, auth_id, destination_kinesis_arn, destination_s3_url)
    except Exception as e:
        return Exception('Unable to read the configuration file', e)

def init_config(configuration_file):
    print("""This utility will create a granule metadata configuration file by prompting """
          """you for values for each of the configuration parameters.""")
    print()
    # if config file name is not blank
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
    cfg_parser.set("Source", "data_dir", Prompt.ask("Data directory"))
    print()

    print()
    print("Destination Data Parameters")
    print('--------------------------------------------------')
    # local dir
    # local subdir for ummg
    cfg_parser.add_section("Destination")
    cfg_parser.set("Destination", "local_staging_dir", Prompt.ask("Local output directory"))
    cfg_parser.set("Destination", "kinesis_arn", Prompt.ask("Kinesis Stream ARN"))
    cfg_parser.set("Destination", "s3_url", Prompt.ask("S3 Bucket URL"))

    print()
    print(f'Saving new configuration: {configuration_file}')
    with open(configuration_file, "tw") as file:
        cfg_parser.write(file)

    return cfg_parser

def show_config(configuration):
    print()
    # TODO add section headings
    for k,v in configuration.__dict__.items():
        print(f'  + {k}: {v}')

def process(configuration):
    # For each input file in `data_dir`:
    #   * create or find ummg file
    #   * stage data & ummg file
    #   * compose CNM-S
    #   * publish CNM-S
    #   * create audit entry
    # TODO:
    #   * Parallelize the operations
    show_config(configuration)
    print()
    print('--------------------------------------------------')

    source_data_path = Path(configuration.source_data_dir)

    source_data = list(source_data_path.glob('*.nc'))

    print(f'Found {len(source_data)} source files to process')
    print()

    for file in source_data:
        print('--------------------------------------------------')
        ummg_file = find_or_create_ummg(configuration, file)
        stage(configuration, file, ummg_file)
        cnm = cnms_message(configuration, file, ummg_file)
        publish_cnm(configuration, cnm)
        print()

def find_or_create_ummg(configuration, science_file):
    # look for ummg with same base name
    return 'generated ummg'

def stage(configuration, science_file, ummg_file):
    print(f'Staged file: {science_file}')
    print(f'Staged file: {ummg_file}')

def cnms_message(configuration, science_file, ummg_file):
    return '{ "CollectionReference": { "ShortName": "MODSCGDRF", "Version": "001" }}'

def publish_cnm(configuration, cnm_message):
    print(f'Published CNM message: {cnm_message}')
    # TODO write file for now, rather than post to Kinesis
