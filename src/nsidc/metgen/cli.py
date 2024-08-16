import click

from nsidc.metgen import metgen


@click.group()
def main():
    pass

@main.command()
@click.option('--config', help='metgen configuration file')
def init(config):
    click.echo(metgen.banner())
    click.echo(f'Initialized the metgen configuration file {config}')

@main.command()
@click.option('--config', help='metgen configuration file')
def info(config):
    click.echo(metgen.banner())
    configuration = metgen.configuration(metgen.config_parser(config))
    metgen.show_config(configuration)

@main.command()
@click.option('--config', help='metgen configuration file')
def process(config):
    click.echo(metgen.banner())
    configuration = metgen.configuration(metgen.config_parser(config))
    metgen.process(configuration)
    click.echo(f'Processed granules using the configuration file {config}')