import configparser

from pyfiglet import Figlet


def show_banner():
    f = Figlet(font='fraktur', width=160)
    print(f.renderText('Instameta'))


def configuration(configuration_file):
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
