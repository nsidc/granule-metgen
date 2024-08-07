import click

from nsidc import instameta


@click.group()
def cli():
    pass

@cli.command()
@click.option('--config', help='Instameta configuration file')
def init(config):
    instameta.show_banner()
    click.echo(f'Initialized the instameta configuration file {config}')

@cli.command()
@click.option('--config', help='Instameta configuration file')
def info(config):
    instameta.show_banner()
    configuration = instameta.configuration(config)
    instameta.show_config(configuration)

@cli.command()
@click.option('--config', help='Instameta configuration file')
def process(config):
    instameta.show_banner()
    click.echo(f'Processed granules using the configuration file {config}')


if __name__ == "__main__":
    cli()
