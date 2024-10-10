import click

from nsidc.metgen import config
from nsidc.metgen import metgen
from nsidc.metgen import constants


@click.group(epilog="For detailed help on each command, run: instameta COMMAND --help")
def cli():
    """The instameta utility allows users to create granule-level
    metadata, stage granule files and their associated metadata to
    Cumulus, and post CNM messages."""
    pass

@cli.command()
@click.option('-c', '--config', help='Path to configuration file to create or replace')
def init(config):
    """Populates a configuration file based on user input."""
    click.echo(metgen.banner())
    config = metgen.init_config(config)
    click.echo(f'Initialized the metgen configuration file {config}')

@cli.command()
@click.option('-c', '--config', 'config_filename', help='Path to configuration file to display', required=True)
def info(config_filename):
    """Summarizes the contents of a configuration file."""
    click.echo(metgen.banner())
    configuration = config.configuration(config.config_parser_factory(config_filename), {})
    configuration.show()

@cli.command()
@click.option('-c', '--config', 'config_filename', help='Path to configuration file', required=True)
@click.option('-e', '--env', help='environment', default=constants.DEFAULT_CUMULUS_ENVIRONMENT, show_default=True)
@click.option('-n', '--number', help="Process at most 'count' granules.", metavar='count', required=False, default=-1)
@click.option('-wc', '--write-cnm', is_flag=True, help="Write CNM messages to files.")
def process(config_filename, env, write_cnm, number):
    """Processes science data files based on configuration file contents."""
    click.echo(metgen.banner())
    overrides = {
        'write_cnm_file': write_cnm,
        'number': number
    }
    configuration = config.configuration(config.config_parser_factory(config_filename), overrides, env)
    try:
        metgen.process(configuration)
    except Exception as e:
        print("\nUnable to process data: " + str(e))
        exit(1)
    click.echo(f'Processed granules using the configuration file {config_filename}')

if __name__ == "__main__":
    cli()
