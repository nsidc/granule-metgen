import click

from nsidc.metgen import metgen


@click.group()
def cli():
    """The instameta utility allows users to create granule-level metadata."""
    pass

@cli.command()
@click.option('--config', help='configuration file name to write')
def init(config):
    """Creates a new metgen config file based on user input."""
    click.echo(metgen.banner())
    config = metgen.init_config(config)
    click.echo(f'Initialized the metgen configuration file {config}')

@cli.command()
@click.option('--config', help='metgen configuration file', required=True)
def info(config):
    """Summarizes the values in a metgen configuration file."""
    click.echo(metgen.banner())
    configuration = metgen.configuration(metgen.config_parser(config))
    metgen.show_config(configuration)

@cli.command()
@click.option('--config', help='metgen configuration file', required=True)
@click.option('--env', help='environment', default='int', show_default=True)
def process(config, env):
    """Processes science data files based on a metgen configuration file."""
    click.echo(metgen.banner())
    configuration = metgen.configuration(metgen.config_parser(config), env)
    metgen.process(configuration)
    click.echo(f'Processed granules using the configuration file {config}')

if __name__ == "__main__":
    cli()
