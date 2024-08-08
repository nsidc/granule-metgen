import configparser
from pathlib import Path

from pyfiglet import Figlet


def show_banner():
    f = Figlet(font='slant', width=160)
    print(f.renderText('Instameta'))


def configuration(configuration_file):
    # TODO: Put this into a more usable form like dataclass(es)
    config = configparser.ConfigParser()
    config.read(configuration_file)
    return config

def show_config(configuration):
    for section in configuration.sections():
        print()
        print(f'* {section}')
        for option in configuration.options(section):
            value = configuration.get(section, option)
            print(f'  + {option}: {value}')

def process(configuration):
    # For each input file pair in `data_dir` and `ummg_dir`:
    #   * stage data & ummg files
    #   * compose CNM-S
    #   * publish CNM-S
    #   * create audit entry
    # TODO:
    #   * Parallelize this
    # Questions:
    #   * Handle CNM-R or is that a distinct operation for
    #   `instameta`?
    show_config(configuration)
    print()
    print('--------------------------------------------------')

    source_data_path = Path(configuration.get('Source', 'data_dir'))
    source_ummg_path = Path(configuration.get('Source', 'ummg_dir'))

    source_data = list(source_data_path.glob('*.nc'))
    source_ummg = list(source_ummg_path.glob('*.json'))
    source_files = zip(source_data, source_ummg)

    print(f'Found {len(source_data)} source files to process')
    print()

    for source_pair in source_files:
        print('--------------------------------------------------')
        stage(configuration, source_pair)
        cnm = cnms_message(configuration, source_pair)
        publish_cnm(configuration, cnm)
        print()

def stage(configuration, source_pair):
    print(f'Staged files: {source_pair[0]} {source_pair[1]}')

def cnms_message(configuration, source_pair):
    return '{ "CollectionReference": { "ShortName": "MODSCGDRF", "Version": "001" }}'

def publish_cnm(configuration, cnm_message):
    print(f'Published CNM message: {cnm_message}')
