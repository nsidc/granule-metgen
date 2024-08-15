import click

from nsidc import instameta


@click.group()
def cli():
    pass

@cli.command()
@click.option('--config', help='Instameta configuration file')
def init(config):
    click.echo(instameta.banner())
    click.echo(f'Initialized the instameta configuration file {config}')

@cli.command()
@click.option('--config', help='Instameta configuration file')
def info(config):
    click.echo(instameta.banner())
    configuration = instameta.configuration(instameta.config_parser(config))
    instameta.show_config(configuration)

@cli.command()
@click.option('--config', help='Instameta configuration file')
def process(config):
    click.echo(instameta.banner())
    configuration = instameta.configuration(instameta.config_parser(config))
    instameta.process(configuration)
    click.echo(f'Processed granules using the configuration file {config}')


if __name__ == "__main__":
    cli()
