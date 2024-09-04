import click

from nsidc.metgen import metgen


@click.group(epilog="For detailed help on each command, run: instameta COMMAND --help")
def cli():
    """The instameta utility allows users to create granule-level metadata."""
    pass

@cli.command()
@click.option('--config', help='Path to configuration file to create or replace')
def init(config):
    """Populates a configuration file based on user input."""
    click.echo(metgen.banner())
    config = metgen.init_config(config)
    click.echo(f'Initialized the metgen configuration file {config}')

@cli.command()
@click.option('--config', help='Path to configuration file to display', required=True)
def info(config):
    """Summarizes the contents of a configuration file."""
    click.echo(metgen.banner())
    configuration = metgen.configuration(metgen.config_parser(config))
    metgen.show_config(configuration)

@cli.command()
@click.option('--config', help='Path to configuration file', required=True)
@click.option('--env', help='environment', default='int', show_default=True)
def process(config, env):
    """Processes science data files based on configuration file contents."""
    click.echo(metgen.banner())
    configuration = metgen.configuration(metgen.config_parser(config), env)
    metgen.process(configuration)
    click.echo(f'Processed granules using the configuration file {config}')

if __name__ == "__main__":
    cli()
