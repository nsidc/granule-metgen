import configparser
from dataclasses import dataclass
from pathlib import Path

from pyfiglet import Figlet


@dataclass
class Config:
    source_data_dir: str

def banner():
    f = Figlet(font='slant')
    return f.renderText('Instameta')

def config_parser(configuration_file):
    try:
        cfg_parser = configparser.ConfigParser()
        cfg_parser.read(configuration_file)
        return cfg_parser
    except Exception as e:
        raise ValueError(f'Unable to read configuration file {configuration_file}')

def configuration(config_parser):
    try:
        source_data_dir = config_parser.get('Source', 'data_dir')
        return Config(source_data_dir)
    except Exception as e:
        return Exception('Unable to read the configuration file', e)

def show_config(configuration):
    print()
    print(f'* Source')
    print(f'  + Data directory: {configuration.source_data_dir}')

def process(configuration):
    # For each input file pair in `data_dir` and `ummg_dir`:
    #   * stage data & ummg files
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
        stage(configuration, file)
        cnm = cnms_message(configuration, file)
        publish_cnm(configuration, cnm)
        print()

def stage(configuration, source_file):
    print(f'Staged file: {source_file}')

def cnms_message(configuration, source_file):
    return '{ "CollectionReference": { "ShortName": "MODSCGDRF", "Version": "001" }}'

def publish_cnm(configuration, cnm_message):
    print(f'Published CNM message: {cnm_message}')
